import uuid

from pydantic import BaseModel, EmailStr


class TenantCreate(BaseModel):
    name: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    tenant_id: uuid.UUID
    is_active: bool

    class Config:
        from_attributes = True