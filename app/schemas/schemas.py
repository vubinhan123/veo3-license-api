from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any

# Authentication
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    role: str = "viewer"

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class User(UserBase):
    id: str
    role: str
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

# License Management
class LicenseBase(BaseModel):
    plan_type: str
    expire_date: datetime
    max_devices: int = 1
    enabled_modules: dict = {}

class LicenseCreate(LicenseBase):
    license_key: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None

class License(LicenseBase):
    id: str
    license_key: str
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    hwid: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

# Verification
class VerifyRequest(BaseModel):
    license_key: str
    hwid: str
    tool_version: Optional[str] = "1.0.0"

class VerifyResponse(BaseModel):
    status: str
    token: Optional[str] = None
    message: str
    expiry: Optional[datetime] = None
    modules: Optional[dict] = {}
