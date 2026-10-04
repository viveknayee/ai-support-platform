from datetime import datetime, timezone
from app.core.redis_client import redis_client

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError

from app.core.database import async_session_factory, auth_session_factory
from app.core.config import settings
from app.core.security import PasswordManager, create_access_token, create_refresh_token
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import TenantCreate, UserCreate, UserResponse, LoginRequest, RefreshRequest, LogoutRequest
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.api.deps import get_current_tenant_user


router = APIRouter()


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(tenant_data: TenantCreate, user_data: UserCreate):
    async with async_session_factory() as session:
        try:
            async with session.begin():
                tenant = Tenant(name=tenant_data.name)
                session.add(tenant)
                await session.flush()

                await session.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant.id)},
                )

                hashed_pw = PasswordManager.hash_password(user_data.password)
                user = User(
                    tenant_id=tenant.id,
                    email=user_data.email,
                    hashed_password=hashed_pw,
                )
                session.add(user)
                await session.flush()
                await session.refresh(user)

            return user

        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered.",
            )


@router.post("/login")
async def login(credentials: LoginRequest):
    async with auth_session_factory() as session:
        result = await session.execute(
            select(User).where(User.email == credentials.email)
        )
        user = result.scalar_one_or_none()

        if not user or not PasswordManager.verify_password(
            credentials.password, user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        token_data = {"sub": user.email, "tenant_id": str(user.tenant_id)}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }


@router.post("/refresh")
async def refresh(payload: RefreshRequest):
    if await redis_client.get(f"blacklist:{payload.refresh_token}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
        )
    try:
        decoded =  jwt.decode(
            payload.refresh_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again.",
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )
    if decoded.get("type") != "refresh":
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Token is not a refresh token.",
        )

    token_data = {"sub": decoded["sub"], "tenant_id": decoded["tenant_id"]}
    new_access_token = create_access_token(token_data)

    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout(payload: LogoutRequest):
    for token in (payload.access_token, payload.refresh_token):
        try:
            decoded = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except ExpiredSignatureError:
            continue
        except InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token.",
            )

        ttl_seconds = int(decoded["exp"] - datetime.now(timezone.utc).timestamp())
        if ttl_seconds > 0:
            await redis_client.set(f"blacklist:{token}", "true", ex=ttl_seconds)

    return {"message": "Logged out successfully."}

@router.get("/me")
async def read_current_user(current_user: dict = Depends(get_current_tenant_user)):
    return current_user