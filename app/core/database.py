import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True)

async_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def get_tenant_db_session(tenant_id: uuid.UUID) -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            await session.execute(
                text("SET LOCAL app.current_tenant_id = :tenant_id"),
                {"tenant_id": str(tenant_id)},
            )
            yield session
        finally:
            await session.close()