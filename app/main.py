from fastapi import FastAPI
from app.api.v1.health import router as health_router
from app.api.v1.documents import router as documents_router
app = FastAPI(title="AI Support Platform")

app.include_router(health_router, prefix="/api/v1")

from app.api.v1.auth import router as auth_router

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])