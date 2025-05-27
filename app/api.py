from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from fastapi.responses import HTMLResponse
from .database import get_db
from .auth import verify_api_key, log_operation
from .proxmox import proxmox_service
from .schemas import ContainerStatus, OperationResponse, ContainerList, ContainerCreate, ContainerRebuild, ConsoleResponse, ConsoleTicket

router = APIRouter()

HTML_CONSOLE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Proxmox LXC 控制台 - {node}/{vmid}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
    <style>
        body, html {{ 
            height: 100%; 
            margin: 0; 
            overflow: hidden; 
            background-color: #000; 
            font-family: monospace; 
        }}
        #terminal {{ 
            width: 100%; 
            height: 100%; 
        }}
        #status {{ 
            position: absolute; 
            top: 10px; 
            left: 10px; 
            color: #fff; 
            background-color: rgba(0, 0, 0, 0.5); 
            padding: 5px 10px; 
            border-radius: 3px; 
            font-size: 12px; 
            z-index: 100; 
        }}
        #error {{ 
            color: #ff6347; 
            padding: 20px; 
            font-size: 16px; 
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background-color: #333;
            border: 1px solid #ff6347;
            border-radius: 5px;
            text-align: center;
         }}
    </style>
</head>
<body>
    <div id="status">正在初始化...</div>
    <div id="terminal"></div>
    <div id="error" style="display: none;"></div>

    <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"></script>

    <script>
        const terminalDiv = document.getElementById('terminal');
        const statusDiv = document.getElementById('status');
        const errorDiv = document.getElementById('error');

        const PVE_PARAMS = {{
            host: "{host}",
            port: "{port}",
            node: "{node}",
            vmid: "{vmid}",
            ticket: "{ticket}"
        }};

        function updateStatus(message) {{ statusDiv.textContent = message; }}
        function displayError(message) {{
            terminalDiv.style.display = 'none';
            statusDiv.style.display = 'none';
            errorDiv.textContent = '错误：' + message;
            errorDiv.style.display = 'block';
        }}

        function initConsole() {{
            const params = PVE_PARAMS;

            if (!params.host || !params.port || !params.node || !params.vmid || !params.ticket || params.host === '{{host}}') {{
                displayError('无法获取有效的连接参数。请检查API响应或服务器配置 (特别是 PROXMOX_HOST)。');
                return;
            }}

            const term = new Terminal({{ 
                cursorBlink: true, 
                fontSize: 14, 
                fontFamily: 'Consolas, "Courier New", monospace', 
                theme: {{ 
                    background: '#000000', 
                    foreground: '#FFFFFF', 
                    cursor: '#FFFFFF' 
                }} 
            }});
            const fitAddon = new FitAddon.FitAddon();
            term.loadAddon(fitAddon);
            term.open(terminalDiv);
            fitAddon.fit();
            window.addEventListener('resize', () => {{ fitAddon.fit(); }});

            const wsUrl = `wss://${{params.host}}:${{params.port}}/api2/json/nodes/${{params.node}}/lxc/${{params.vmid}}/vncwebsocket?port=${{params.port}}&vncticket=${{encodeURIComponent(params.ticket)}}`;

            updateStatus(`正在连接到 ${{params.host}}:${{params.port}}...`);
            term.writeln(`\\x1b[1;33m正在尝试连接到 ${{params.node}}/${{params.vmid}}...\\x1b[0m`);

            try {{
                const socket = new WebSocket(wsUrl);
                socket.binaryType = 'arraybuffer'; 

                socket.onopen = function () {{
                    updateStatus(`已连接 - ${{params.node}}/${{params.vmid}}`);
                    term.writeln('\\x1b[1;32mWebSocket 连接已建立。\\x1b[0m');
                    term.focus();
                }};
                socket.onmessage = function (event) {{
                    const data = new Uint8Array(event.data);
                    term.write(data);
                }};
                socket.onerror = function (event) {{
                    updateStatus('连接错误');
                    term.writeln(`\\x1b[1;31mWebSocket 发生错误。请检查网络和 SSL 证书设置 (浏览器需信任 Proxmox 证书)。\\x1b[0m`);
                    console.error("WebSocket Error: ", event);
                }};
                socket.onclose = function (event) {{
                    updateStatus(`连接已关闭 (代码: ${{event.code}})`);
                    term.writeln(`\\x1b[1;31mWebSocket 连接已关闭 (代码: ${{event.code}})。票据可能已失效或连接中断。\\x1b[0m`);
                    console.log("WebSocket Closed: ", event);
                    term.writeln('\\x1b[1;33m请关闭此窗口并重新获取链接。\\x1b[0m');
                    term.blur();
                }};
                term.onData(function (data) {{
                    if (socket.readyState === WebSocket.OPEN) {{ 
                       socket.send(data); 
                    }}
                }});
            }} catch (e) {{
                displayError('创建 WebSocket 连接失败: ' + e.message);
                console.error("WebSocket Creation Failed: ", e);
            }}
        }}
        initConsole();
    </script>
</body>
</html>
"""

@router.get("/containers", response_model=ContainerList, summary="获取容器列表",
            description="获取Proxmox VE节点上的LXC容器列表。可指定节点或获取所有在线节点的容器。")
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
             description="在指定的Proxmox节点上创建一个新的LXC容器。")
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
             description="获取指定节点上特定VMID的LXC容器的当前状态和基本信息。")
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
             description="启动指定的LXC容器。")
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
             description="强制停止指定的LXC容器 (慎用)。")
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
             description="优雅地关闭指定的LXC容器。")
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
             description="重启指定的LXC容器。")
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
               description="删除指定的LXC容器。**危险操作，请谨慎使用！**")
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
             description="销毁并使用新的配置重新创建指定的LXC容器。**危险操作，数据会丢失！**")
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
            description="获取Proxmox中特定异步任务的状态。")
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

@router.post("/containers/{node}/{vmid}/console", response_model=ConsoleResponse, summary="获取容器控制台票据 (JSON)",
             description="获取用于连接到LXC容器控制台的票据和连接信息 (返回 JSON 数据)。")
async def get_container_console(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    try:
        result = proxmox_service.get_container_console(node, vmid)

        log_operation(
            db, "获取控制台票据",
            vmid, node, "成功" if result['success'] else "失败",
            result['message'], request.client.host
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
            db, "获取控制台票据",
            vmid, node, "失败",
            str(e), request.client.host
        )
        raise HTTPException(status_code=500, detail=f"获取控制台失败: {str(e)}")


@router.get("/containers/{node}/{vmid}/console_page", response_class=HTMLResponse, summary="获取容器控制台网页",
             description="直接返回一个内嵌连接信息的HTML控制台页面，可在浏览器中打开访问。 **此链接本身是临时的，依赖于内部票据的有效期**。")
async def get_container_console_page(
    node: str,
    vmid: str,
    request: Request,
    _: bool = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    try:
        result = proxmox_service.get_container_console(node, vmid)

        log_operation(
            db, "获取控制台网页",
            vmid, node, "成功" if result['success'] else "失败",
            "请求生成控制台网页", request.client.host
        )

        if not result['success']:
            error_html = HTML_CONSOLE_TEMPLATE.format(
                host="", port="", node=node, vmid=vmid, ticket="",
            ).replace(
                "正在初始化...", 
                f"错误: 无法获取控制台票据 - {result['message']}"
            )
            return HTMLResponse(content=error_html, status_code=500)

        console_data = result.get('data')
        
        ticket = console_data['ticket'].replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

        html_content = HTML_CONSOLE_TEMPLATE.format(
            host=console_data['host'],
            port=console_data['port'],
            node=console_data['node'],
            vmid=vmid,
            ticket=ticket
        )

        return HTMLResponse(content=html_content)

    except Exception as e:
        log_operation(
            db, "获取控制台网页",
            vmid, node, "失败",
            str(e), request.client.host
        )
        error_html = HTML_CONSOLE_TEMPLATE.format(
            host="", port="", node=node, vmid=vmid, ticket="",
        ).replace(
            "正在初始化...", 
            f"内部错误: {str(e)}"
        )
        return HTMLResponse(content=error_html, status_code=500)
