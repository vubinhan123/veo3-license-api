from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func as sa_func
from app.core.database import get_db
from app.models.models import License, Device, Log
from app.schemas.schemas import VerifyRequest, VerifyResponse
from app.core.security import create_license_signature
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import uuid

from app.schemas import schemas

router = APIRouter()

@router.get("/debug-db")
async def debug_db(db: AsyncSession = Depends(get_db)):
    try:
        from app.models.models import License, User
        from sqlalchemy import text
        res = await db.execute(text("SELECT 1;"))
        u_res = await db.execute(select(User).limit(1))
        user = u_res.scalar_one_or_none()
        l_res = await db.execute(select(License).limit(1))
        lic = l_res.scalar_one_or_none()
        return {"status": "ok", "db_connected": True, "has_user": user is not None, "has_lic": lic is not None}
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}

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
    """Tra ve thong ke thuc te cho Dashboard voi 4 trang thai ro rang"""
    now = datetime.utcnow()
    
    # 1. Dem key theo trang thai
    all_licenses = await db.execute(select(License))
    licenses = all_licenses.scalars().all()
    
    active_count = 0
    expired_count = 0
    revoked_count = 0
    expiring_soon = 0
    tool_dist = {}
    
    for l in licenses:
        tool_key = l.tool_type or "veo3_pro"
        tool_dist[tool_key] = tool_dist.get(tool_key, 0) + 1
        
        if l.status == "revoked":
            revoked_count += 1
            continue
        
        if l.expire_date:
            try:
                exp = l.expire_date.replace(tzinfo=None) if l.expire_date.tzinfo else l.expire_date
                if exp < now:
                    expired_count += 1
                else:
                    active_count += 1
                    if exp <= now + timedelta(days=7):
                        expiring_soon += 1
            except Exception:
                active_count += 1
        else:
            active_count += 1
    
    # 2. Dem thiet bi & key da gan HWID
    all_devices = await db.execute(select(Device))
    device_count = len(all_devices.scalars().all())
    activated_count = sum(1 for l in licenses if l.hwid)
    
    # 3. Logs 24h
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
    
    # 4. Phan bo goi
    plan_dist = {}
    for l in licenses:
        plan_dist[l.plan_type] = plan_dist.get(l.plan_type, 0) + 1
    
    plan_colors = {
        "Trial": "#94a3b8", "Monthly": "#6366f1", 
        "Yearly": "#8b5cf6", "Permanent": "#d946ef", "Custom": "#06b6d4"
    }
    plan_data = [
        {"name": k, "value": v, "color": plan_colors.get(k, "#6366f1")} 
        for k, v in plan_dist.items()
    ]
    
    # 5. Phan bo Tool
    tool_names_map = {
        "veo3_pro": "VEO3 PRO",
        "image_pro": "IMAGE PRO",
        "tool_voice": "TOOL VOICE",
        "combo_all": "KEY TEST"
    }
    tool_colors = {
        "veo3_pro": "#3b82f6",
        "image_pro": "#a855f7",
        "tool_voice": "#10b981",
        "combo_all": "#f59e0b"
    }
    tool_data = [
        {"tool_type": k, "name": tool_names_map.get(k, k), "count": v, "color": tool_colors.get(k, "#3b82f6")}
        for k, v in tool_dist.items()
    ]
    
    return {
        "active_licenses": active_count,
        "expired_licenses": expired_count,
        "revoked_licenses": revoked_count,
        "total_licenses": len(licenses),
        "devices_online": device_count,
        "activated_keys": activated_count,
        "logs_24h": logs_24h,
        "total_logs": total_logs,
        "expiring_soon": expiring_soon,
        "plan_distribution": plan_data,
        "tool_distribution": tool_data,
    }

@router.get("/", response_model=List[schemas.License])
async def list_licenses(tool_type: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    query = select(License)
    if tool_type and tool_type != "all":
        query = query.where(License.tool_type == tool_type)
    result = await db.execute(query.order_by(License.created_at.desc()))
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
        tool_type=data.tool_type or "veo3_pro",
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

@router.post("/batch", response_model=List[schemas.License])
async def create_batch_licenses(data: schemas.BatchLicenseCreate, db: AsyncSession = Depends(get_db)):
    """Tao nhieu key cung luc (Batch Generator)"""
    import secrets
    created_list = []
    exp_date = datetime.now(timezone.utc) + timedelta(days=data.expire_days)
    
    for i in range(data.count):
        raw = secrets.token_hex(16).upper()
        key = "-".join([raw[j:j+4] for j in range(0, 32, 4)])
        name = f"{data.customer_prefix} #{i+1}" if data.customer_prefix else None
        
        new_lic = License(
            license_key=key,
            customer_name=name,
            customer_email=None,
            plan_type=data.plan_type,
            expire_date=exp_date,
            max_devices=1,
            status="active",
            tool_type=data.tool_type or "veo3_pro",
            note=data.note,
            enabled_modules={}
        )
        db.add(new_lic)
        created_list.append(new_lic)
        
    await db.flush()
    
    log = Log(
        event_type="tao_key_hang_loat", 
        details={"count": data.count, "tool_type": data.tool_type, "plan_type": data.plan_type}
    )
    db.add(log)
    
    await db.commit()
    for lic in created_list:
        await db.refresh(lic)
    return created_list

@router.post("/renew/{license_id}", response_model=schemas.License)
async def renew_license(license_id: str, data: schemas.LicenseRenew, db: AsyncSession = Depends(get_db)):
    """Gia han nhanh 1-Click (+30 ngay, +90 ngay, +1 nam)"""
    result = await db.execute(select(License).where(License.id == license_id))
    db_license = result.scalar_one_or_none()
    if not db_license:
        raise HTTPException(status_code=404, detail="License not found")
        
    now = datetime.now(timezone.utc)
    current_exp = db_license.expire_date
    if current_exp.tzinfo is None:
        current_exp = current_exp.replace(tzinfo=timezone.utc)
        
    base_date = max(now, current_exp)
    db_license.expire_date = base_date + timedelta(days=data.days)
    db_license.status = "active"
    if data.plan_type:
        db_license.plan_type = data.plan_type
        
    log = Log(
        event_type="gia_han", 
        license_id=license_id, 
        details={"extended_days": data.days, "new_expiry": db_license.expire_date.isoformat()}
    )
    db.add(log)
    
    await db.commit()
    await db.refresh(db_license)
    return db_license

@router.post("/reset-hwid/{license_id}", response_model=schemas.License)
async def reset_hwid(license_id: str, db: AsyncSession = Depends(get_db)):
    """Reset ma may HWID de khach doi sang may tinh khac"""
    result = await db.execute(select(License).where(License.id == license_id))
    db_license = result.scalar_one_or_none()
    if not db_license:
        raise HTTPException(status_code=404, detail="License not found")
        
    old_hwid = db_license.hwid
    db_license.hwid = None
    db_license.reset_count = (db_license.reset_count or 0) + 1
    
    await db.execute(delete(Device).where(Device.license_id == license_id))
    
    log = Log(
        event_type="reset_hwid", 
        license_id=license_id, 
        details={"old_hwid": old_hwid, "total_resets": db_license.reset_count}
    )
    db.add(log)
    
    await db.commit()
    await db.refresh(db_license)
    return db_license

@router.post("/heartbeat", response_model=schemas.HeartbeatResponse)
async def license_heartbeat(request: schemas.HeartbeatRequest, db: AsyncSession = Depends(get_db)):
    """Kiem tra online dinh ky (Heartbeat) tu Client Tool de thu hoi tuc thi neu can"""
    result = await db.execute(select(License).where(License.license_key == request.license_key))
    db_license = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    
    if not db_license:
        return schemas.HeartbeatResponse(status="invalid", message="License không tồn tại", server_time=now)
        
    if db_license.status == "revoked":
        return schemas.HeartbeatResponse(status="revoked", message="License đã bị thu hồi bởi quản trị viên!", server_time=now)
        
    exp = db_license.expire_date
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
        
    diff = exp - now
    days_left = max(0, diff.days)
    if diff.total_seconds() <= 0:
        return schemas.HeartbeatResponse(status="expired", message="License đã hết hạn!", days_remaining=0, server_time=now)
        
    db_license.last_heartbeat = now
    await db.commit()
    
    return schemas.HeartbeatResponse(
        status="active", 
        message="OK", 
        days_remaining=days_left,
        server_time=now
    )

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
    try:
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
        
        # 3. Kiểm tra phân quyền Tool (Tool Isolation)
        req_tool = request.tool_type or "veo3_pro"
        lic_tool = db_license.tool_type or "veo3_pro"
        
        # Cho phép nếu đúng tool hoặc key là gói combo_all / all / key_test
        if lic_tool not in [req_tool, "combo_all", "all", "key_test"]:
            tool_names = {
                "veo3_pro": "VEO3 PRO",
                "image_pro": "IMAGE PRO",
                "tool_voice": "TOOL VOICE",
                "combo_all": "KEY TEST (TẤT CẢ TOOL)",
                "key_test": "KEY TEST (TẤT CẢ TOOL)"
            }
            lic_name = tool_names.get(lic_tool, lic_tool)
            req_name = tool_names.get(req_tool, req_tool)
            return VerifyResponse(
                status="fail", 
                message=f"Key này chỉ thuộc bản quyền của '{lic_name}', không thể dùng cho '{req_name}'!"
            )
        
        # 4. Kiểm tra thiết bị (HWID Binding)
        result = await db.execute(select(Device).where(Device.license_id == db_license.id))
        devices = result.scalars().all()
        
        current_device = next((d for d in devices if d.hwid == request.hwid), None)
        
        if not current_device:
            if len(devices) >= db_license.max_devices:
                return VerifyResponse(status="fail", message="Vượt quá số lượng thiết bị cho phép")
            
            # Đăng ký thiết bị mới
            new_device = Device(license_id=db_license.id, hwid=request.hwid)
            db.add(new_device)
            
            # Dong bo HWID sang ban ghi License chinh de Frontend hien thi trang thai Da kich hoat
            if not db_license.hwid:
                db_license.hwid = request.hwid
                
            await db.flush()
        else:
            if current_device.status != "active":
                return VerifyResponse(status="fail", message="Thiết bị đã bị chặn")
        
        # 5. Ghi log thành công
        try:
            new_log = Log(
                event_type="verify_success", 
                license_id=db_license.id, 
                hwid=request.hwid,
                details={"tool_requested": req_tool, "license_tool": lic_tool}
            )
            db.add(new_log)
            await db.flush()
        except Exception:
            pass
        
        # 6. Ký Token cho Client
        try:
            payload = {
                "license_key": db_license.license_key,
                "hwid": request.hwid,
                "tool_type": db_license.tool_type,
                "modules": db_license.enabled_modules,
                "expiry": db_license.expire_date.isoformat()
            }
            token = create_license_signature(payload)
        except Exception as sig_err:
            print("Sign token error:", sig_err)
            token = "ACTIVE_VALIDATED"
        
        return VerifyResponse(
            status="success",
            token=token,
            message="Xác thực thành công",
            tool_type=db_license.tool_type,
            expiry=db_license.expire_date,
            modules=db_license.enabled_modules
        )
    except Exception as e:
        import traceback
        print("Verify exception:", traceback.format_exc())
        return VerifyResponse(status="fail", message=f"Lỗi xác thực hệ thống: {str(e)}")
