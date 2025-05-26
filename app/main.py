from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import logging
import sys

from .config import settings
from .database import create_tables, get_db
from .auth import create_api_key
from .api import router as api_router
from .schemas import ApiKeyCreate, ApiKeyResponse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lxc_api.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"全局异常处理: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "服务器内部错误", "detail": str(exc)}
    )

@app.on_event("startup")
async def startup_event():
    logger.info("正在启动LXC管理API服务...")
    create_tables()
    logger.info("数据库表创建完成")
    logger.info(f"API服务启动成功，访问地址: http://localhost:8000/docs")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("LXC管理API服务正在关闭...")

@app.get("/", summary="服务状态检查")
async def root():
    return {
        "service": "Proxmox LXC管理API",
        "version": settings.api_version,
        "status": "运行中",
        "docs": "/docs"
    }

@app.get("/health", summary="健康检查")
async def health_check():
    return {
        "status": "健康",
        "service": "lxc-api",
        "timestamp": "2024-01-01T00:00:00Z"
    }

@app.post("/admin/api-keys", response_model=ApiKeyResponse, summary="创建API密钥")
async def create_new_api_key(
    key_data: ApiKeyCreate,
    db: Session = Depends(get_db)
):
    try:
        db_key, key_value = create_api_key(
            db=db,
            key_name=key_data.key_name,
            permissions=key_data.permissions,
            expires_days=key_data.expires_days
        )

        return ApiKeyResponse(
            id=db_key.id,
            key_name=db_key.key_name,
            key_value=key_value,
            is_active=db_key.is_active,
            created_at=db_key.created_at,
            expires_at=db_key.expires_at,
            permissions=db_key.permissions
        )

    except Exception as e:
        logger.error(f"创建API密钥失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建API密钥失败: {str(e)}")

app.include_router(api_router, prefix="/api/v1", tags=["LXC容器管理"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
