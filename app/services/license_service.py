import secrets
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import License

def generate_formatted_key() -> str:
    """Tạo License Key chuẩn dạng 8 nhóm 4 ký tự: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX"""
    raw = secrets.token_hex(16).upper()
    return "-".join([raw[i:i+4] for i in range(0, 32, 4)])

async def create_license_record(
    db: AsyncSession,
    customer_name: Optional[str] = None,
    customer_email: Optional[str] = None,
    plan_type: str = "Monthly",
    expire_date: Optional[datetime] = None,
    max_devices: int = 1,
    tool_type: str = "veo3_pro",
    note: Optional[str] = None,
    enabled_modules: Optional[dict] = None
) -> License:
    """Tạo mới một bản ghi License trong cơ sở dữ liệu"""
    key = generate_formatted_key()
    new_license = License(
        license_key=key,
        customer_name=customer_name,
        customer_email=customer_email,
        plan_type=plan_type,
        expire_date=expire_date,
        max_devices=max_devices,
        status="active",
        tool_type=tool_type,
        note=note,
        enabled_modules=enabled_modules or {}
    )
    db.add(new_license)
    await db.commit()
    await db.refresh(new_license)
    return new_license
