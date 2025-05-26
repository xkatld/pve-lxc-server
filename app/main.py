from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import sys
import os
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from .config import settings
from .database import create_tables
from .api import router as api_router

CERT_FILE = "cert.pem"
KEY_FILE = "key.pem"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lxc_api.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def generate_self_signed_cert_if_not_exists(cert_path, key_path):
    if not os.path.exists(key_path) or not os.path.exists(cert_path):
        logger.info("未找到证书或密钥，正在生成自签名证书...")

        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u"CN"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Guangdong"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, u"Shenzhen"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"ZjmfServer LTD"),
            x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
        ])

        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=3650)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName(u"localhost"), x509.DNSName(u"127.0.0.1")]),
            critical=False,
        ).sign(key, hashes.SHA256(), default_backend())

        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        logger.info(f"证书 '{cert_path}' 和密钥 '{key_path}' 已成功生成。")
    else:
        logger.info("证书和密钥已存在，跳过生成。")

generate_self_signed_cert_if_not_exists(CERT_FILE, KEY_FILE)

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
    logger.info(f"API 服务启动成功，请通过 https://<您的IP>:8000/docs 访问")

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

app.include_router(api_router, prefix="/api/v1", tags=["LXC 容器管理"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        ssl_keyfile=KEY_FILE,
        ssl_certfile=CERT_FILE
    )
