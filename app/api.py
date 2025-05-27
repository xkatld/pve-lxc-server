from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from .database import get_db
from .auth import verify_api_key, log_operation
from .proxmox import proxmox_service
from .schemas import ContainerStatus, OperationResponse, ContainerList, ContainerCreate, ContainerRebuild

router = APIRouter()

@router.get("/containers", response_model=ContainerList, summary="获取容器列表",
            description="""
**功能**: 获取 Proxmox VE 节点上的 LXC 容器列表。可以指定节点，或获取所有在线节点上的容器。

**使用示例 (cURL)**:

```bash
# 获取所有节点的容器
curl -k -X 'GET' \
  'https://<你的服务器IP>:8000/api/v1/containers' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <你的_API_密钥>'

# 获取指定节点 (例如 'pve') 的容器
curl -k -X 'GET' \
  'https://<你的服务器IP>:8000/api/v1/containers?node=pve' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <你的_API_密钥>'
```

**参数**:
- `node` (可选): 指定要查询的 Proxmox 节点名称。

**认证**:
- 请求头中必须包含 `Authorization: Bearer <你的_API_密钥>`。
""")
async def get_containers(
    request: Request,
    node: str = None,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    try:
        containers_data = proxmox_service.get_containers(node)
        containers = []

        for container in containers_data:
            status_info = ContainerStatus(
                vmid=str(container['vmid']),
                name=container.get('name', f"CT-{container['vmid']}"),
                status=container.get('status', 'unknown'),
                uptime=container.get('uptime', 0),
                cpu=container.get('cpu', 0),
                mem=container.get('mem', 0),
                maxmem=container.get('maxmem', 0),
                node=container['node']
            )
            containers.append(status_info)

        log_operation(
            db, "获取容器列表",
            node or "所有节点", node or "所有节点", "成功",
            f"获取到 {len(containers)} 个容器",
            request.client.host
        )

        return ContainerList(containers=containers, total=len(containers))

    except Exception as e:
        log_operation(
            db, "获取容器列表",
            node or "所有节点", node or "所有节点", "失败",
            str(e), request.client.host
        )
        raise HTTPException(status_code=500, detail=f"获取容器列表失败: {str(e)}")

@router.post("/containers", response_model=OperationResponse, summary="创建LXC容器",
             description="""
**功能**: 在指定的 Proxmox 节点上创建一个新的 LXC 容器。

**使用示例 (cURL)**:

```bash
curl -k -X 'POST' \
  'https://<你的服务器IP>:8000/api/v1/containers' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <你的_API_密钥>' \
  -H 'Content-Type: application/json' \
  -d '{
  "node": "pve",
  "vmid": 105,
  "hostname": "my-new-ct",
  "password": "a_secure_password",
  "ostemplate": "local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.gz",
  "storage": "local-lvm",
  "disk_size": 8,
  "cores": 1,
  "memory": 512,
  "swap": 512,
  "network": {
    "name": "eth0",
    "bridge": "vmbr0",
    "ip": "dhcp"
  },
  "start": true
}'
```

**请求体**:
- 包含创建容器所需的所有配置信息，详情请参考 `ContainerCreate` 模型。

**认证**:
- 请求头中必须包含 `Authorization: Bearer <你的_API_密钥>`。
""")
async def create_container(
    container_data: ContainerCreate,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    try:
        result = proxmox_service.create_container(container_data)

        log_operation(
            db, "创建容器",
            str(container_data.vmid), container_data.node,
            "成功" if result['success'] else "失败",
            result['message'], request.client.host
        )

        if not result['success']:
            raise HTTPException(status_code=400, detail=result['message'])

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': result.get('task_id')} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "创建容器",
            str(container_data.vmid), container_data.node, "失败",
            str(e), request.client.host
        )
        raise HTTPException(status_code=500, detail=f"创建容器失败: {str(e)}")

@router.get("/containers/{node}/{vmid}/status", response_model=ContainerStatus, summary="获取容器状态",
             description="""
**功能**: 获取指定节点上特定 VMID 的 LXC 容器的当前状态和基本信息。

**使用示例 (cURL)**:

```bash
curl -k -X 'GET' \
  'https://<你的服务器IP>:8000/api/v1/containers/pve/105/status' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <你的_API_密钥>'
```

**参数**:
- `node`: 容器所在的 Proxmox 节点名称。
- `vmid`: 要查询的容器 ID。

**认证**:
- 请求头中必须包含 `Authorization: Bearer <你的_API_密钥>`。
""")
async def get_container_status(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    try:
        status_data = proxmox_service.get_container_status(node, vmid)

        log_operation(
            db, "获取容器状态",
            vmid, node, "成功",
            f"容器状态: {status_data['status']}",
            request.client.host
        )

        return ContainerStatus(**status_data)

    except Exception as e:
        log_operation(
            db, "获取容器状态",
            vmid, node, "失败",
            str(e), request.client.host
        )
        raise HTTPException(status_code=500, detail=f"获取容器状态失败: {str(e)}")

@router.post("/containers/{node}/{vmid}/start", response_model=OperationResponse, summary="启动容器",
             description="""
**功能**: 启动指定的 LXC 容器。

**使用示例 (cURL)**:

```bash
curl -k -X 'POST' \
  'https://<你的服务器IP>:8000/api/v1/containers/pve/105/start' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <你的_API_密钥>'
```

**参数**:
- `node`: 容器所在的 Proxmox 节点名称。
- `vmid`: 要启动的容器 ID。

**认证**:
- 请求头中必须包含 `Authorization: Bearer <你的_API_密钥>`。
""")
async def start_container(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    try:
        result = proxmox_service.start_container(node, vmid)

        log_operation(
            db, "启动容器",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host
        )

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': result.get('task_id')} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "启动容器",
            vmid, node, "失败",
            str(e), request.client.host
        )
        raise HTTPException(status_code=500, detail=f"启动容器失败: {str(e)}")

@router.post("/containers/{node}/{vmid}/stop", response_model=OperationResponse, summary="强制停止容器",
             description="""
**功能**: 强制停止指定的 LXC 容器 (相当于拔掉电源)。

**使用示例 (cURL)**:

```bash
curl -k -X 'POST' \
  'https://<你的服务器IP>:8000/api/v1/containers/pve/105/stop' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <你的_API_密钥>'
```

**参数**:
- `node`: 容器所在的 Proxmox 节点名称。
- `vmid`: 要停止的容器 ID。

**认证**:
- 请求头中必须包含 `Authorization: Bearer <你的_API_密钥>`。
""")
async def stop_container(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    try:
        result = proxmox_service.stop_container(node, vmid)

        log_operation(
            db, "强制停止容器",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host
        )

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': result.get('task_id')} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "强制停止容器",
            vmid, node, "失败",
            str(e), request.client.host
        )
        raise HTTPException(status_code=500, detail=f"强制停止容器失败: {str(e)}")

@router.post("/containers/{node}/{vmid}/shutdown", response_model=OperationResponse, summary="关闭容器",
             description="""
**功能**: 优雅地关闭指定的 LXC 容器 (向容器发送关机信号)。

**使用示例 (cURL)**:

```bash
curl -k -X 'POST' \
  'https://<你的服务器IP>:8000/api/v1/containers/pve/105/shutdown' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <你的_API_密钥>'
```

**参数**:
- `node`: 容器所在的 Proxmox 节点名称。
- `vmid`: 要关闭的容器 ID。

**认证**:
- 请求头中必须包含 `Authorization: Bearer <你的_API_密钥>`。
""")
async def shutdown_container(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    try:
        result = proxmox_service.shutdown_container(node, vmid)

        log_operation(
            db, "关闭容器",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host
        )

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': result.get('task_id')} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "关闭容器",
            vmid, node, "失败",
            str(e), request.client.host
        )
        raise HTTPException(status_code=500, detail=f"关闭容器失败: {str(e)}")

@router.post("/containers/{node}/{vmid}/reboot", response_model=OperationResponse, summary="重启容器",
             description="""
**功能**: 重启指定的 LXC 容器。

**使用示例 (cURL)**:

```bash
curl -k -X 'POST' \
  'https://<你的服务器IP>:8000/api/v1/containers/pve/105/reboot' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <你的_API_密钥>'
```

**参数**:
- `node`: 容器所在的 Proxmox 节点名称。
- `vmid`: 要重启的容器 ID。

**认证**:
- 请求头中必须包含 `Authorization: Bearer <你的_API_密钥>`。
""")
async def reboot_container(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    try:
        result = proxmox_service.reboot_container(node, vmid)

        log_operation(
            db, "重启容器",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host
        )

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': result.get('task_id')} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "重启容器",
            vmid, node, "失败",
            str(e), request.client.host
        )
        raise HTTPException(status_code=500, detail=f"重启容器失败: {str(e)}")

@router.delete("/containers/{node}/{vmid}", response_model=OperationResponse, summary="删除容器",
               description="""
**功能**: 删除指定的 LXC 容器。**这是一个危险操作，请谨慎使用！**

**使用示例 (cURL)**:

```bash
curl -k -X 'DELETE' \
  'https://<你的服务器IP>:8000/api/v1/containers/pve/105' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <你的_API_密钥>'
```

**参数**:
- `node`: 容器所在的 Proxmox 节点名称。
- `vmid`: 要删除的容器 ID。

**认证**:
- 请求头中必须包含 `Authorization: Bearer <你的_API_密钥>`。
""")
async def delete_container(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    try:
        result = proxmox_service.delete_container(node, vmid)

        log_operation(
            db, "删除容器",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host
        )

        if not result['success']:
             raise HTTPException(status_code=400, detail=result['message'])

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': result.get('task_id')} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "删除容器",
            vmid, node, "失败",
            str(e), request.client.host
        )
        raise HTTPException(status_code=500, detail=f"删除容器失败: {str(e)}")

@router.post("/containers/{node}/{vmid}/rebuild", response_model=OperationResponse, summary="重建容器",
             description="""
**功能**: 销毁并使用新的配置重新创建指定的 LXC 容器。**这是一个危险操作，会导致容器内数据丢失！**

**使用示例 (cURL)**:

```bash
curl -k -X 'POST' \
  'https://<你的服务器IP>:8000/api/v1/containers/pve/105/rebuild' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <你的_API_密钥>' \
  -H 'Content-Type: application/json' \
  -d '{
  "ostemplate": "local:vztmpl/debian-11-standard_11.7-1_amd64.tar.gz",
  "hostname": "rebuilt-ct",
  "password": "another_secure_password",
  "storage": "local-lvm",
  "disk_size": 10,
  "cores": 2,
  "memory": 1024,
  "swap": 512,
  "network": {
    "name": "eth0",
    "bridge": "vmbr0",
    "ip": "192.168.1.105/24",
    "gw": "192.168.1.1"
  },
  "start": true
}'
```

**参数**:
- `node`: 容器所在的 Proxmox 节点名称。
- `vmid`: 要重建的容器 ID。

**请求体**:
- 包含重建容器所需的所有新配置信息，详情请参考 `ContainerRebuild` 模型。

**认证**:
- 请求头中必须包含 `Authorization: Bearer <你的_API_密钥>`。
""")
async def rebuild_container_api(
    node: str,
    vmid: str,
    rebuild_data: ContainerRebuild,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    try:
        result = proxmox_service.rebuild_container(node, vmid, rebuild_data)

        log_operation(
            db, "重建容器",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host
        )

        if not result['success']:
             raise HTTPException(status_code=400, detail=result['message'])

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': result.get('task_id')} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "重建容器",
            vmid, node, "失败",
            str(e), request.client.host
        )
        raise HTTPException(status_code=500, detail=f"重建容器失败: {str(e)}")


@router.get("/tasks/{node}/{task_id}", response_model=OperationResponse, summary="获取任务状态",
            description="""
**功能**: 获取 Proxmox 中特定异步任务（如创建、启动、停止容器等）的状态。

**使用示例 (cURL)**:

```bash
curl -k -X 'GET' \
  'https://<你的服务器IP>:8000/api/v1/tasks/pve/UPID:pve:000ABCDE:12345678:...' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <你的_API_密钥>'
```

**参数**:
- `node`: 任务所在的 Proxmox 节点名称。
- `task_id`: 要查询的任务 ID (UPID)。

**认证**:
- 请求头中必须包含 `Authorization: Bearer <你的_API_密钥>`。
""")
async def get_task_status(
    node: str,
    task_id: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    try:
        task_status = proxmox_service.get_task_status(node, task_id)

        return OperationResponse(
            success=True,
            message="任务状态获取成功",
            data=task_status
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")
