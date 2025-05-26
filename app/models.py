from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from .database import Base

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_name = Column(String(100), unique=True, index=True)
    key_hash = Column(String(255), unique=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    permissions = Column(String(500), default="read,write")

class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    api_key_name = Column(String(100), index=True)
    operation = Column(String(50), index=True)
    container_id = Column(String(20), index=True)
    node_name = Column(String(50))
    status = Column(String(20))
    message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45))
