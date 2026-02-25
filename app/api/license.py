from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sa_func
from app.core.database import get_db
from app.models.models import License, Device, Log
from app.schemas.schemas import VerifyRequest, VerifyResponse
from app.core.security import create_license_signature
from datetime import datetime, timezone, timedelta
from typing import List
import uuid

from app.schemas import schemas

router = APIRouter()

@router.get("/test-error")
async def test_error():
    try:
        payload = {
            "license_key": "test",
            "hwid": "test",
            "modules": {},
            "expiry": datetime.now(timezone.utc).isoformat()
        }
        token = create_license_signature(payload)
        return {"status": "ok", "token": token}
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}

@router.get("/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Tra ve thong ke thuc te cho Dashboard"""
    now = datetime.utcnow()  # SQLite luu datetime naive, phai dung naive de so sanh
    
    # 1. Dem key theo trang thai
    all_licenses = await db.execute(select(License))
    licenses = all_licenses.scalars().all()
    
    active_count = sum(1 for l in licenses if l.status == "active")
    revoked_count = sum(1 for l in licenses if l.status == "revoked")
    
    # 2. Key sap het han (trong 7 ngay toi)
    expiring_soon = 0
    for l in licenses:
        if l.status == "active" and l.expire_date:
            try:
                exp = l.expire_date.replace(tzinfo=None) if l.expire_date.tzinfo else l.expire_date
                if exp < now + timedelta(days=7):
                    expiring_soon += 1
            except:
                pass
    
    # 3. Dem thiet bi
    all_devices = await db.execute(select(Device))
    device_count = len(all_devices.scalars().all())
    
    # 4. Dem key da kich hoat (co HWID)
    activated_count = sum(1 for l in licenses if l.hwid)
    
    # 5. Logs 24h
    try:
        all_logs = await db.execute(select(Log))
        logs = all_logs.scalars().all()
        logs_24h = 0
        for log in logs:
            if log.created_at:
                try:
                    ct = log.created_at.replace(tzinfo=None) if log.created_at.tzinfo else log.created_at
                    if ct > now - timedelta(hours=24):
                        logs_24h += 1
                except:
                    pass
        total_logs = len(logs)
    except:
        logs_24h = 0
        total_logs = 0
    
    # 6. Phan bo goi
    plan_dist = {}
    for l in licenses:
        plan_dist[l.plan_type] = plan_dist.get(l.plan_type, 0) + 1
    
    plan_colors = {
        "Trial": "#94a3b8", "Monthly": "#6366f1", 
        "Yearly": "#8b5cf6", "Permanent": "#d946ef"
    }
    plan_data = [
        {"name": k, "value": v, "color": plan_colors.get(k, "#6366f1")} 
        for k, v in plan_dist.items()
    ]
    
    return {
        "active_licenses": active_count,
        "revoked_licenses": revoked_count,
        "total_licenses": len(licenses),
        "devices_online": device_count,
        "activated_keys": activated_count,
        "logs_24h": logs_24h,
        "total_logs": total_logs,
        "expiring_soon": expiring_soon,
        "plan_distribution": plan_data,
    }

@router.get("/", response_model=List[schemas.License])
async def list_licenses(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(License))
    return result.scalars().all()

@router.get("/logs")
async def get_logs(db: AsyncSession = Depends(get_db)):
    """Tra ve danh sach nhat ky hoat dong tu moi nhat"""
    result = await db.execute(select(Log).order_by(Log.created_at.desc()).limit(100))
    logs = result.scalars().all()
    
    # Join voi License de lay license_key
    output = []
    for log in logs:
        license_key = None
        customer_name = None
        if log.license_id:
            lic_result = await db.execute(select(License).where(License.id == log.license_id))
            lic = lic_result.scalar_one_or_none()
            if lic:
                license_key = lic.license_key
                customer_name = lic.customer_name
        
        output.append({
            "id": log.id,
            "event_type": log.event_type,
            "license_id": log.license_id,
            "license_key": license_key,
            "customer_name": customer_name,
            "hwid": log.hwid,
            "ip_address": log.ip_address,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })
    
    return output

@router.post("/", response_model=schemas.License)
async def create_license(data: schemas.LicenseCreate, db: AsyncSession = Depends(get_db)):
    # Format key: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX (8 groups of 4 hex chars)
    import secrets
    if data.license_key:
        key = data.license_key
    else:
        raw = secrets.token_hex(16).upper()  # 32 hex chars
        key = "-".join([raw[i:i+4] for i in range(0, 32, 4)])
    
    new_license = License(
        license_key=key,
        customer_name=data.customer_name,
        customer_email=data.customer_email,
        plan_type=data.plan_type,
        expire_date=data.expire_date,
        max_devices=1,  # Luon la 1 - khoa cung 1 key = 1 may
        status="active",
        enabled_modules=data.enabled_modules
    )
    db.add(new_license)
    await db.flush()
    
    # Ghi log tao key
    log = Log(event_type="tao_key", license_id=new_license.id, details={"action": f"Tao key cho {data.customer_name or 'N/A'}"})
    db.add(log)
    
    await db.commit()
    await db.refresh(new_license)
    return new_license

@router.patch("/{license_id}", response_model=schemas.License)
async def update_license(license_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(License).where(License.id == license_id))
    db_license = result.scalar_one_or_none()
    if not db_license:
        raise HTTPException(status_code=404, detail="License not found")
    
    old_status = db_license.status
    for key, value in data.items():
        if hasattr(db_license, key):
            setattr(db_license, key, value)
    
    # Ghi log thay doi trang thai
    new_status = data.get("status")
    if new_status and new_status != old_status:
        event = "thu_hoi" if new_status == "revoked" else "kich_hoat_lai"
        log = Log(event_type=event, license_id=license_id, details={"old_status": old_status, "new_status": new_status})
        db.add(log)
            
    await db.commit()
    await db.refresh(db_license)
    return db_license

@router.delete("/{license_id}")
async def delete_license(license_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(License).where(License.id == license_id))
    db_license = result.scalar_one_or_none()
    if not db_license:
        raise HTTPException(status_code=404, detail="License not found")
    
    # Ghi log xoa key (truoc khi xoa)
    log = Log(event_type="xoa_key", details={"deleted_key": db_license.license_key, "customer": db_license.customer_name or "N/A"})
    db.add(log)
    
    await db.delete(db_license)
    await db.commit()
    return {"message": "Deleted successfully"}


@router.post("/verify", response_model=VerifyResponse)
async def verify_license(request: VerifyRequest, db: AsyncSession = Depends(get_db)):
    # 1. Tìm license
    result = await db.execute(select(License).where(License.license_key == request.license_key))
    db_license = result.scalar_one_or_none()
    
    if not db_license:
        return VerifyResponse(status="fail", message="License không tồn tại")
    
    # 2. Kiểm tra trạng thái & hết hạn
    if db_license.status != "active":
        return VerifyResponse(status="fail", message="License đã bị vô hiệu hóa")
    
    exp = db_license.expire_date.replace(tzinfo=None) if db_license.expire_date.tzinfo else db_license.expire_date
    if exp < datetime.utcnow():
        return VerifyResponse(status="fail", message="License đã hết hạn")
    
    # 3. Kiểm tra thiết bị (HWID Binding)
    result = await db.execute(select(Device).where(Device.license_id == db_license.id))
    devices = result.scalars().all()
    
    current_device = next((d for d in devices if d.hwid == request.hwid), None)
    
    if not current_device:
        if len(devices) >= db_license.max_devices:
            return VerifyResponse(status="fail", message="Vượt quá số lượng thiết bị cho phép")
        
        # Đăng ký thiết bị mới
        new_device = Device(license_id=db_license.id, hwid=request.hwid)
        db.add(new_device)
        await db.flush()
    else:
        if current_device.status != "active":
            return VerifyResponse(status="fail", message="Thiết bị đã bị chặn")
    
    # 4. Ghi log thành công
    new_log = Log(event_type="verify_success", license_id=db_license.id, hwid=request.hwid)
    db.add(new_log)
    
    # 5. Ký Token cho Client
    payload = {
        "license_key": db_license.license_key,
        "hwid": request.hwid,
        "modules": db_license.enabled_modules,
        "expiry": db_license.expire_date.isoformat()
    }
    token = create_license_signature(payload)
    
    return VerifyResponse(
        status="success",
        token=token,
        message="Xác thực thành công",
        expiry=db_license.expire_date,
        modules=db_license.enabled_modules
    )
