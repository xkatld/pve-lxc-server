from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from .database import get_db
from .auth import verify_api_key, log_operation
from .proxmox import proxmox_service
from .schemas import ContainerStatus, OperationResponse, ContainerList, ContainerCreate

router = APIRouter()

@router.get("/containers", response_model=ContainerList, summary="获取容器列表")
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

@router.post("/containers", response_model=OperationResponse, summary="创建LXC容器")
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


@router.get("/containers/{node}/{vmid}/status", response_model=ContainerStatus, summary="获取容器状态")
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

@router.post("/containers/{node}/{vmid}/start", response_model=OperationResponse, summary="启动容器")
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

@router.post("/containers/{node}/{vmid}/stop", response_model=OperationResponse, summary="强制停止容器")
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

@router.post("/containers/{node}/{vmid}/shutdown", response_model=OperationResponse, summary="关闭容器")
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

@router.post("/containers/{node}/{vmid}/reboot", response_model=OperationResponse, summary="重启容器")
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

@router.get("/tasks/{node}/{task_id}", response_model=OperationResponse, summary="获取任务状态")
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
