from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

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
    STORAGE_DIR: str = "storage/uploads"
    MAX_UPLOAD_SIZE_MB: int = 20
    CHUNK_SIZE_TOKENS: int = 400
    CHUNK_OVERLAP_TOKENS: int = 50

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    @model_validator(mode="after")
    def check_chunk_settings(self) -> "Settings":
        if self.CHUNK_SIZE_TOKENS <= 0:
            raise ValueError("CHUNK_SIZE_TOKENS must be greater than 0")
        if self.CHUNK_OVERLAP_TOKENS < 0:
            raise ValueError("CHUNK_OVERLAP_TOKENS cannot be negative")
        if self.CHUNK_OVERLAP_TOKENS >= self.CHUNK_SIZE_TOKENS:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_SIZE_TOKENS")
        return self


settings = Settings()