from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True)

async_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)