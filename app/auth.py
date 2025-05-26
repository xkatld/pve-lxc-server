import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .database import get_db
from .models import ApiKey, OperationLog

security = HTTPBearer()

def generate_api_key() -> str:
    return secrets.token_urlsafe(32)

def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()

def create_api_key(db: Session, key_name: str, permissions: str = "read,write", expires_days: Optional[int] = None) -> tuple[ApiKey, str]:
    api_key_value = generate_api_key()
    key_hash = hash_api_key(api_key_value)

    expires_at = None
    if expires_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_days)

    db_api_key = ApiKey(
        key_name=key_name,
        key_hash=key_hash,
        permissions=permissions,
        expires_at=expires_at
    )

    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)

    return db_api_key, api_key_value

def verify_api_key(db: Session, api_key: str) -> Optional[ApiKey]:
    key_hash = hash_api_key(api_key)
    db_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True).first()

    if not db_key:
        return None

    if db_key.expires_at and db_key.expires_at < datetime.utcnow():
        return None

    db_key.last_used = datetime.utcnow()
    db.commit()

    return db_key

def get_current_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> ApiKey:
    api_key = verify_api_key(db, credentials.credentials)
    if not api_key:
        raise HTTPException(status_code=401, detail="无效的API密钥")

    return api_key

def log_operation(
    db: Session,
    api_key_name: str,
    operation: str,
    container_id: str,
    node_name: str,
    status: str,
    message: str,
    ip_address: str = None
):
    log_entry = OperationLog(
        api_key_name=api_key_name,
        operation=operation,
        container_id=container_id,
        node_name=node_name,
        status=status,
        message=message,
        ip_address=ip_address
    )

    db.add(log_entry)
    db.commit()

def check_permissions(api_key: ApiKey, required_permission: str) -> bool:
    permissions = api_key.permissions.split(",")
    return required_permission in permissions or "admin" in permissions
