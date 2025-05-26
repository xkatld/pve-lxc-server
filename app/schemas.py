from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class ContainerStatus(BaseModel):
    vmid: str
    name: Optional[str] = None
    status: str
    uptime: Optional[int] = None
    cpu: Optional[float] = None
    mem: Optional[int] = None
    maxmem: Optional[int] = None
    node: str

class ContainerOperation(BaseModel):
    vmid: str
    node: str

class OperationResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class ContainerList(BaseModel):
    containers: list[ContainerStatus]
    total: int

class ApiKeyCreate(BaseModel):
    key_name: str
    permissions: str = "read,write"
    expires_days: Optional[int] = None

class ApiKeyResponse(BaseModel):
    id: int
    key_name: str
    key_value: str
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    permissions: str

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[int] = None
