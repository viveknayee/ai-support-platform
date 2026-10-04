from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str
    ENVIRONMENT: str = "development"
    DATABASE_URL: str
    ALEMBIC_DATABASE_URL: str
    AUTH_DATABASE_URL: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15    
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7    
    REDIS_URL: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()