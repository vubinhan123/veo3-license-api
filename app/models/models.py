from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="viewer")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class License(Base):
    __tablename__ = "licenses"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    license_key = Column(String, unique=True, index=True, nullable=False)
    customer_name = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    plan_type = Column(String, nullable=False)
    expire_date = Column(DateTime(timezone=True), nullable=False)
    max_devices = Column(Integer, default=1)
    status = Column(String, default="active")
    hwid = Column(String, nullable=True)  # HWID cua may dau tien kich hoat
    enabled_modules = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    devices = relationship("Device", back_populates="license", cascade="all, delete-orphan")

class Device(Base):
    __tablename__ = "devices"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    license_id = Column(String, ForeignKey("licenses.id", ondelete="CASCADE"))
    hwid = Column(String, index=True, nullable=False)
    ip_address = Column(String)
    first_activation = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    status = Column(String, default="active")
    
    license = relationship("License", back_populates="devices")

class Log(Base):
    __tablename__ = "logs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String, index=True, nullable=False)
    license_id = Column(String, ForeignKey("licenses.id", ondelete="SET NULL"), nullable=True)
    hwid = Column(String)
    ip_address = Column(String)
    details = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
