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
    tool_type: str = "veo3_pro"
    enabled_modules: dict = {}

class LicenseCreate(LicenseBase):
    license_key: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    note: Optional[str] = None

class LicenseRenew(BaseModel):
    days: int = 30
    plan_type: Optional[str] = None

class BatchLicenseCreate(BaseModel):
    count: int = Field(default=5, ge=1, le=100)
    plan_type: str = "Monthly"
    expire_days: int = 30
    tool_type: str = "veo3_pro"
    customer_prefix: Optional[str] = "Khách Sỉ"
    note: Optional[str] = None

class License(LicenseBase):
    id: str
    license_key: str
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    hwid: Optional[str] = None
    status: str
    reset_count: Optional[int] = 0
    last_heartbeat: Optional[datetime] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

# Verification & Anti-Crack
class VerifyRequest(BaseModel):
    license_key: str
    hwid: str
    tool_type: Optional[str] = "veo3_pro"
    tool_version: Optional[str] = "1.0.0"

class VerifyResponse(BaseModel):
    status: str
    token: Optional[str] = None
    message: str
    tool_type: Optional[str] = None
    expiry: Optional[datetime] = None
    modules: Optional[dict] = {}

class HeartbeatRequest(BaseModel):
    license_key: str
    hwid: str
    tool_type: Optional[str] = "veo3_pro"

class HeartbeatResponse(BaseModel):
    status: str  # "active" | "revoked" | "expired" | "invalid"
    message: str
    days_remaining: Optional[int] = 0
    server_time: Optional[datetime] = None
