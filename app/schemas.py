from pydantic import BaseModel
from typing import Optional, Dict, Any, List

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
    containers: List[ContainerStatus]
    total: int

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[int] = None

class NetworkInterface(BaseModel):
    name: str = "eth0"
    bridge: str = "vmbr0"
    ip: str = "dhcp"
    gw: Optional[str] = None
    vlan: Optional[int] = None

class ContainerCreate(BaseModel):
    node: str
    vmid: int
    ostemplate: str
    hostname: str
    password: str
    cores: int = 1
    memory: int = 512
    swap: int = 512
    storage: str
    network: NetworkInterface
    unprivileged: Optional[bool] = True
    start: Optional[bool] = False
    features: Optional[str] = None

class ContainerRebuild(BaseModel):
    ostemplate: str
    hostname: str
    password: str
    cores: int = 1
    memory: int = 512
    swap: int = 512
    storage: str
    network: NetworkInterface
    unprivileged: Optional[bool] = True
    start: Optional[bool] = False
    features: Optional[str] = None
