from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import async_session_factory
from app.core.security import PasswordManager
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import TenantCreate, UserCreate, UserResponse

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