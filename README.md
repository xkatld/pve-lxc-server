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

---

## 项目部署与运行 (Debian 12)

本指南将引导你在 Debian 12 系统上直接部署和运行 `zjmf-server-pve-lxc` 项目。

### 1. 环境准备

* **Proxmox VE**: 确保你有一个正在运行的 Proxmox VE 服务器，并准备好其 API 访问凭据。
* **Debian 12 系统**: 一个干净的 Debian 12 系统环境。

### 2. 系统更新与依赖安装

首先，我们需要更新系统并安装必要的软件包，包括 Python 3.9+、pip 以及构建 Python 包所需的工具。

1.  **更新软件包列表并升级系统**：
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```
2.  **安装 Python 和 Pip** (Debian 12 通常自带 Python 3.11，满足要求)：
    ```bash
    sudo apt install python3 python3-pip python3-venv -y
    ```
3.  **安装构建工具** (某些 Python 包在安装时可能需要编译)：
    ```bash
    sudo apt install build-essential python3-dev -y
    ```

### 3. 获取项目代码

如果你还没有项目代码，可以使用 `git` 克隆仓库。如果 `git` 未安装，请先安装：

```bash
sudo apt install git -y
git clone <你的项目仓库地址> # 或者将代码上传到服务器
cd zjmf-server-pve-lxc
```

### 4. 配置环境

接下来，配置项目的环境变量。

1.  **复制环境变量示例文件**：
    ```bash
    cp .env.example .env
    ```
2.  **编辑 `.env` 文件**，使用 `nano` 或你喜欢的编辑器，填入你的 Proxmox 服务器信息和自定义配置：
    ```bash
    nano .env
    ```
    修改以下内容：
    ```dotenv
    PROXMOX_HOST=你的Proxmox服务器IP
    PROXMOX_PORT=8006
    PROXMOX_USER=你的Proxmox用户名@pam
    PROXMOX_PASSWORD=你的Proxmox密码
    PROXMOX_VERIFY_SSL=False # 如果你的 PVE 没有有效证书，请设为 False

    DATABASE_URL="sqlite:///./lxc_api.db" # 默认使用 SQLite

    SECRET_KEY="这是一个强密码请务必修改" # 用于 API Key 加密等，请务必修改
    ```
    编辑完成后，按 `Ctrl+X`，然后按 `Y` 保存并退出 `nano`。

### 5. 创建虚拟环境并安装项目依赖

使用虚拟环境是一个好习惯，可以隔离项目依赖，避免与系统 Python 环境冲突。

1.  **创建虚拟环境**：
    ```bash
    python3 -m venv venv
    ```
2.  **激活虚拟环境**：
    ```bash
    source venv/bin/activate
    ```
    激活后，你的命令行提示符前会显示 `(venv)`。
3.  **安装项目依赖**：
    ```bash
    pip install -r requirements.txt
    ```

### 6. 运行项目

现在，你可以启动 FastAPI 应用服务了。

1.  **启动服务**：
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    ```
    * `--host 0.0.0.0` 允许从任何网络接口访问服务。
    * `--port 8000` 指定服务监听的端口。
    * 如果你在开发环境中，可以添加 `--reload` 参数，这样代码变更后服务会自动重启。

### 7. 访问服务

服务启动后，你可以通过浏览器或 API 工具访问：

* **API 根目录**: `http://<你的Debian服务器IP>:8000/`
* **API 文档 (Swagger UI)**: `http://<你的Debian服务器IP>:8000/docs`
* **API 文档 (ReDoc)**: `http://<你的Debian服务器IP>:8000/redoc`

### 8. 创建与使用 API 密钥

为了安全访问 API，你需要创建并使用 API 密钥。

1.  **创建密钥**: 访问 `http://<你的Debian服务器IP>:8000/docs`，找到并使用 `POST /admin/api-keys` 端点来创建你的第一个密钥。**请务必保存好返回的 `key_value`**。
2.  **使用密钥**: 在访问需要认证的 API 端点时，在请求头中添加 `Authorization: Bearer <你的_key_value>`。

### 9. (可选) 保持服务后台运行

如果你希望服务在关闭终端后仍然运行，可以使用 `systemd` 或 `supervisor` 等工具进行管理，或者简单地使用 `nohup` 或 `screen`/`tmux`。

**使用 `nohup`**：

```bash
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > lxc_api_run.log 2>&1 &
```

这将使服务在后台运行，并将日志输出到 `lxc_api_run.log` 文件。
