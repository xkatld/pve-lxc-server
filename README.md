# Proxmox LXC 管理接口 (zjmf-server-pve-lxc)

## 项目目录结构

```
zjmf-server-pve-lxc/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI应用程序入口
│   ├── config.py                   # 配置文件
│   ├── database.py                 # 数据库连接配置
│   ├── models.py                   # 数据库模型
│   ├── schemas.py                  # Pydantic模式定义
│   ├── auth.py                     # API Key认证
│   ├── proxmox.py                  # Proxmox LXC服务
│   └── api.py                      # API路由
├── migrations/                     # 数据库迁移文件
│   └── init.sql
├── requirements.txt                # 项目依赖
├── .env.example                    # 环境变量示例
├── .env                           # 环境变量配置
├── Dockerfile                      # Docker镜像构建文件
├── docker-compose.yml              # Docker部署配置
└── README.md                       # 项目说明
```

## 项目部署与运行

本项目提供了两种运行方式：使用 Docker (推荐) 或直接在本地环境运行。

### 1. 环境准备

* **Python**: 确保你已安装 Python 3.9 或更高版本。
* **Docker & Docker Compose**: 如果你选择使用 Docker 部署，请确保已安装 Docker 和 Docker Compose。
* **Proxmox VE**: 你需要一个正在运行的 Proxmox VE 服务器，并准备好其 API 访问凭据。

### 2. 配置环境

首先，你需要配置项目的环境变量。

1.  复制环境变量示例文件：
    ```bash
    cp .env.example .env
    ```
2.  编辑 `.env` 文件，填入你的 Proxmox 服务器信息和自定义配置：
    ```dotenv
    PROXMOX_HOST=你的Proxmox服务器IP
    PROXMOX_PORT=8006
    PROXMOX_USER=你的Proxmox用户名@pam
    PROXMOX_PASSWORD=你的Proxmox密码
    PROXMOX_VERIFY_SSL=False # 如果你的 PVE 没有有效证书，请设为 False

    DATABASE_URL="sqlite:///./lxc_api.db" # 默认使用 SQLite

    SECRET_KEY="这是一个强密码请务必修改" # 用于 API Key 加密等，请务必修改
    ```

### 3. 运行项目

#### 方式一：使用 Docker (推荐)

这是最简单、最推荐的部署方式，可以确保环境一致性。

1.  **构建并启动服务**: 在项目根目录下运行：
    ```bash
    docker-compose up --build -d
    ```
    * `--build` 会强制重新构建镜像，确保代码更新生效。
    * `-d` 会让容器在后台运行。

2.  **查看日志**: 如果需要查看服务运行日志，可以使用：
    ```bash
    docker-compose logs -f
    ```

3.  **停止服务**: 如果需要停止服务，可以使用：
    ```bash
    docker-compose down
    ```

#### 方式二：本地运行

如果你不想使用 Docker，也可以直接在本地 Python 环境中运行。

1.  **创建并激活虚拟环境** (推荐):
    ```bash
    python -m venv venv
    ```
    * **Linux/macOS**: `source venv/bin/activate`
    * **Windows**: `venv\Scripts\activate`

2.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **启动服务**:
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    * `--reload` 参数会在代码变更时自动重启服务，适合开发环境。

### 4. 访问服务

服务启动后，你可以通过以下地址访问：

* **API 根目录**: `http://127.0.0.1:8000/`
* **API 文档 (Swagger UI)**: `http://127.0.0.1:8000/docs`
* **API 文档 (ReDoc)**: `http://127.0.0.1:8000/redoc`

### 5. 创建 API 密钥

为了能够访问受保护的 API 端点，你需要创建一个 API 密钥。你可以通过访问 API 文档 (`/docs`) 并使用 `/admin/api-keys` 端点来创建。

1.  访问 `http://127.0.0.1:8000/docs`。
2.  找到 `POST /admin/api-keys` 端点并展开。
3.  点击 "Try it out"。
4.  在请求体中输入 `key_name` (例如: "my_first_key") 和可选的 `permissions`、`expires_days`。
5.  点击 "Execute"。
6.  **请务必保存响应中返回的 `key_value`**，这是你访问 API 时需要使用的密钥，它**只会出现一次**。

### 6. 使用 API 密钥

在访问需要认证的 API 端点时，你需要在请求头中添加 `Authorization` 字段，格式为 `Bearer <你的_key_value>`。

例如，使用 `curl` 获取容器列表：

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/containers" \
     -H "Authorization: Bearer <你的_key_value>" \
     -H "accept: application/json"
```
