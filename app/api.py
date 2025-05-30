from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from .database import get_db
from .auth import verify_api_key, log_operation
from .proxmox import proxmox_service
from .schemas import (
    ContainerStatus, OperationResponse, ContainerList, ContainerCreate,
    ContainerRebuild, ConsoleResponse, NodeResourceResponse, NodeInfo, NodeListResponse
)
from .logging_context import request_task_id_cv

router = APIRouter()

@router.get("/nodes", response_model=NodeListResponse, summary="获取节点列表",
            description="获取Proxmox VE集群中所有在线节点的基本信息。",
            tags=["节点管理"])
async def get_nodes(
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
    try:
        nodes_data = proxmox_service.get_nodes()
        nodes_info = [NodeInfo(**node) for node in nodes_data]

        log_operation(
            db, "获取节点列表",
            "集群", "所有节点", "成功",
            f"获取到 {len(nodes_info)} 个节点",
            request.client.host,
            task_id=request_id
        )

        return NodeListResponse(
            success=True,
            message="节点列表获取成功",
            data=nodes_info
        )

    except Exception as e:
        log_operation(
            db, "获取节点列表",
            "集群", "所有节点", "失败",
            str(e), request.client.host,
            task_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"获取节点列表失败: {str(e)}")


@router.get("/nodes/{node}/templates", response_model=NodeResourceResponse, summary="获取节点CT模板",
            description="获取指定Proxmox节点上可用的LXC容器模板列表。",
            tags=["节点管理"])
async def get_node_templates(
    node: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
    try:
        templates_data = proxmox_service.get_templates(node)
        log_operation(
            db, "获取节点模板",
            node, node, "成功",
            f"获取到 {len(templates_data)} 个模板",
            request.client.host,
            task_id=request_id
        )
        return NodeResourceResponse(
            success=True,
            message="节点模板获取成功",
            data=templates_data
        )
    except Exception as e:
        log_operation(
            db, "获取节点模板",
            node, node, "失败",
            str(e), request.client.host,
            task_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"获取节点模板失败: {str(e)}")


@router.get("/nodes/{node}/storages", response_model=NodeResourceResponse, summary="获取节点存储",
            description="获取指定Proxmox节点上的存储资源列表及其信息。",
            tags=["节点管理"])
async def get_node_storages(
    node: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
    try:
        storages_data = proxmox_service.get_storages(node)
        log_operation(
            db, "获取节点存储",
            node, node, "成功",
            f"获取到 {len(storages_data)} 个存储",
            request.client.host,
            task_id=request_id
        )
        return NodeResourceResponse(
            success=True,
            message="节点存储获取成功",
            data=storages_data
        )
    except Exception as e:
        log_operation(
            db, "获取节点存储",
            node, node, "失败",
            str(e), request.client.host,
            task_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"获取节点存储失败: {str(e)}")


@router.get("/nodes/{node}/networks", response_model=NodeResourceResponse, summary="获取节点网络",
            description="获取指定Proxmox节点上的网络（桥接）接口列表。",
            tags=["节点管理"])
async def get_node_networks(
    node: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
    try:
        networks_data = proxmox_service.get_networks(node)
        log_operation(
            db, "获取节点网络",
            node, node, "成功",
            f"获取到 {len(networks_data)} 个网络接口",
            request.client.host,
            task_id=request_id
        )
        return NodeResourceResponse(
            success=True,
            message="节点网络获取成功",
            data=networks_data
        )
    except Exception as e:
        log_operation(
            db, "获取节点网络",
            node, node, "失败",
            str(e), request.client.host,
            task_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"获取节点网络失败: {str(e)}")

@router.get("/containers", response_model=ContainerList, summary="获取容器列表",
            description="获取Proxmox VE节点上的LXC容器列表。可指定节点或获取所有在线节点的容器。",
            tags=["容器管理"])
async def get_containers(
    request: Request,
    node: str = None,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
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
            request.client.host,
            task_id=request_id
        )

        return ContainerList(containers=containers, total=len(containers))

    except Exception as e:
        log_operation(
            db, "获取容器列表",
            node or "所有节点", node or "所有节点", "失败",
            str(e), request.client.host,
            task_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"获取容器列表失败: {str(e)}")

@router.post("/containers", response_model=OperationResponse, summary="创建LXC容器",
             description="在指定的Proxmox节点上创建一个新的LXC容器。",
             tags=["容器管理"])
async def create_container(
    container_data: ContainerCreate,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
    pve_task_id = None
    try:
        result = proxmox_service.create_container(container_data)
        pve_task_id = result.get('task_id')
        effective_task_id = pve_task_id or request_id

        log_operation(
            db, "创建容器",
            str(container_data.vmid), container_data.node,
            "成功" if result['success'] else "失败",
            result['message'], request.client.host,
            task_id=effective_task_id
        )

        if not result['success']:
            raise HTTPException(status_code=400, detail=result['message'])

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': effective_task_id} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "创建容器",
            str(container_data.vmid), container_data.node, "失败",
            str(e), request.client.host,
            task_id=pve_task_id or request_id
        )
        raise HTTPException(status_code=500, detail=f"创建容器失败: {str(e)}")

@router.get("/containers/{node}/{vmid}/status", response_model=ContainerStatus, summary="获取容器状态",
             description="获取指定节点上特定VMID的LXC容器的当前状态和基本信息。",
             tags=["容器操作"])
async def get_container_status(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
    try:
        status_data = proxmox_service.get_container_status(node, vmid)

        log_operation(
            db, "获取容器状态",
            vmid, node, "成功",
            f"容器状态: {status_data['status']}",
            request.client.host,
            task_id=request_id
        )

        return ContainerStatus(**status_data)

    except Exception as e:
        log_operation(
            db, "获取容器状态",
            vmid, node, "失败",
            str(e), request.client.host,
            task_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"获取容器状态失败: {str(e)}")

@router.post("/containers/{node}/{vmid}/start", response_model=OperationResponse, summary="启动容器",
             description="启动指定的LXC容器。",
             tags=["容器操作"])
async def start_container(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
    pve_task_id = None
    try:
        result = proxmox_service.start_container(node, vmid)
        pve_task_id = result.get('task_id')
        effective_task_id = pve_task_id or request_id

        log_operation(
            db, "启动容器",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host,
            task_id=effective_task_id
        )

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': effective_task_id} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "启动容器",
            vmid, node, "失败",
            str(e), request.client.host,
            task_id=pve_task_id or request_id
        )
        raise HTTPException(status_code=500, detail=f"启动容器失败: {str(e)}")

@router.post("/containers/{node}/{vmid}/stop", response_model=OperationResponse, summary="强制停止容器",
             description="强制停止指定的LXC容器 (慎用)。",
             tags=["容器操作"])
async def stop_container(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
    pve_task_id = None
    try:
        result = proxmox_service.stop_container(node, vmid)
        pve_task_id = result.get('task_id')
        effective_task_id = pve_task_id or request_id

        log_operation(
            db, "强制停止容器",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host,
            task_id=effective_task_id
        )

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': effective_task_id} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "强制停止容器",
            vmid, node, "失败",
            str(e), request.client.host,
            task_id=pve_task_id or request_id
        )
        raise HTTPException(status_code=500, detail=f"强制停止容器失败: {str(e)}")

@router.post("/containers/{node}/{vmid}/shutdown", response_model=OperationResponse, summary="关闭容器",
             description="优雅地关闭指定的LXC容器。",
             tags=["容器操作"])
async def shutdown_container(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
    pve_task_id = None
    try:
        result = proxmox_service.shutdown_container(node, vmid)
        pve_task_id = result.get('task_id')
        effective_task_id = pve_task_id or request_id

        log_operation(
            db, "关闭容器",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host,
            task_id=effective_task_id
        )

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': effective_task_id} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "关闭容器",
            vmid, node, "失败",
            str(e), request.client.host,
            task_id=pve_task_id or request_id
        )
        raise HTTPException(status_code=500, detail=f"关闭容器失败: {str(e)}")

@router.post("/containers/{node}/{vmid}/reboot", response_model=OperationResponse, summary="重启容器",
             description="重启指定的LXC容器。",
             tags=["容器操作"])
async def reboot_container(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
    pve_task_id = None
    try:
        result = proxmox_service.reboot_container(node, vmid)
        pve_task_id = result.get('task_id')
        effective_task_id = pve_task_id or request_id

        log_operation(
            db, "重启容器",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host,
            task_id=effective_task_id
        )

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': effective_task_id} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "重启容器",
            vmid, node, "失败",
            str(e), request.client.host,
            task_id=pve_task_id or request_id
        )
        raise HTTPException(status_code=500, detail=f"重启容器失败: {str(e)}")

@router.delete("/containers/{node}/{vmid}", response_model=OperationResponse, summary="删除容器",
               description="删除指定的LXC容器。**危险操作，请谨慎使用！**",
               tags=["容器操作"])
async def delete_container(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
    pve_task_id = None
    try:
        result = proxmox_service.delete_container(node, vmid)
        pve_task_id = result.get('task_id')
        effective_task_id = pve_task_id or request_id

        log_operation(
            db, "删除容器",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host,
            task_id=effective_task_id
        )

        if not result['success']:
             raise HTTPException(status_code=400, detail=result['message'])

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': effective_task_id} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "删除容器",
            vmid, node, "失败",
            str(e), request.client.host,
            task_id=pve_task_id or request_id
        )
        raise HTTPException(status_code=500, detail=f"删除容器失败: {str(e)}")

@router.post("/containers/{node}/{vmid}/rebuild", response_model=OperationResponse, summary="重建容器",
             description="销毁并使用新的配置重新创建指定的LXC容器。**危险操作，数据会丢失！**",
             tags=["容器操作"])
async def rebuild_container_api(
    node: str,
    vmid: str,
    rebuild_data: ContainerRebuild,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
    pve_task_id = None
    try:
        result = proxmox_service.rebuild_container(node, vmid, rebuild_data)
        pve_task_id = result.get('task_id')
        effective_task_id = pve_task_id or request_id

        log_operation(
            db, "重建容器",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host,
            task_id=effective_task_id
        )

        if not result['success']:
             raise HTTPException(status_code=400, detail=result['message'])

        return OperationResponse(
            success=result['success'],
            message=result['message'],
            data={'task_id': effective_task_id} if result['success'] else None
        )

    except Exception as e:
        log_operation(
            db, "重建容器",
            vmid, node, "失败",
            str(e), request.client.host,
            task_id=pve_task_id or request_id
        )
        raise HTTPException(status_code=500, detail=f"重建容器失败: {str(e)}")

@router.get("/tasks/{node}/{task_id}", response_model=OperationResponse, summary="获取任务状态",
            description="获取Proxmox中特定异步任务的状态。",
            tags=["任务管理"])
async def get_task_status(
    node: str,
    task_id: str, 
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db) 
):
    request_tracking_id = request_task_id_cv.get() 
    try:
        task_status = proxmox_service.get_task_status(node, task_id)
        return OperationResponse(
            success=True,
            message="任务状态获取成功",
            data=task_status 
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")

@router.post("/containers/{node}/{vmid}/console", response_model=ConsoleResponse, summary="获取容器控制台票据",
             description="获取用于连接到LXC容器控制台的票据和连接信息。",
             tags=["容器操作"])
async def get_container_console(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    request_id = request_task_id_cv.get()
    try:
        result = proxmox_service.get_container_console(node, vmid)

        log_operation(
            db, "获取控制台",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host,
            task_id=request_id 
        )

        if not result['success']:
            raise HTTPException(status_code=500, detail=result['message'])
        
        return ConsoleResponse(
            success=result['success'],
            message=result['message'],
            data=result.get('data')
        )

    except Exception as e:
        log_operation(
            db, "获取控制台",
            vmid, node, "失败",
            str(e), request.client.host,
            task_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"获取控制台失败: {str(e)}")
