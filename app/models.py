from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from .database import Base

class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    operation = Column(String(50), index=True)
    container_id = Column(String(20), index=True)
    node_name = Column(String(50))
    status = Column(String(20))
    message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45))
    task_id = Column(String(255), nullable=True, index=True)
