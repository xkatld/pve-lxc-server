from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import sys
import datetime

from .config import settings
from .database import create_tables
from .api import router as api_router

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
    logger.info("正在启动 LXC 管理 API 服务...")
    create_tables()
    logger.info("数据库表创建完成")
    logger.info(f"API 服务启动成功，请通过 http://<您的IP>:8000/docs 访问")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("LXC 管理 API 服务正在关闭...")

@app.get("/", summary="服务状态检查")
async def root():
    return {
        "service": "Proxmox LXC 管理 API",
        "version": settings.api_version,
        "status": "运行中",
        "docs": "/docs"
    }

@app.get("/health", summary="健康检查")
async def health_check():
    return {
        "status": "健康",
        "service": "lxc-api",
        "timestamp": datetime.datetime.now().isoformat()
    }

app.include_router(api_router, prefix="/api/v1", tags=["LXC 容器管理", "节点资源管理"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
