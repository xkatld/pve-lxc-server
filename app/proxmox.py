from proxmoxer import ProxmoxAPI
from .config import settings
from .schemas import ContainerCreate
from typing import List, Dict, Any, Optional
import logging
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class ProxmoxService:
    def __init__(self):
        self.proxmox = None
        self._connect()

    def _connect(self):
        try:
            self.proxmox = ProxmoxAPI(
                settings.proxmox_host,
                port=settings.proxmox_port,
                user=settings.proxmox_user,
                password=settings.proxmox_password,
                verify_ssl=settings.proxmox_verify_ssl
            )
            logger.info("成功连接到 Proxmox 服务器")
        except Exception as e:
            logger.error(f"连接 Proxmox 服务器失败: {str(e)}")
            raise Exception(f"无法连接到 Proxmox 服务器: {str(e)}")

    def get_nodes(self) -> List[str]:
        try:
            nodes = self.proxmox.nodes.get()
            return [node['node'] for node in nodes if node['status'] == 'online']
        except Exception as e:
            logger.error(f"获取节点列表失败: {str(e)}")
            raise Exception(f"获取节点列表失败: {str(e)}")

    def get_containers(self, node: str = None) -> List[Dict[str, Any]]:
        try:
            containers = []
            nodes_to_check = [node] if node else self.get_nodes()

            for node_name in nodes_to_check:
                node_containers = self.proxmox.nodes(node_name).lxc.get()
                for container in node_containers:
                    container['node'] = node_name
                    containers.append(container)

            return containers
        except Exception as e:
            logger.error(f"获取容器列表失败: {str(e)}")
            raise Exception(f"获取容器列表失败: {str(e)}")

    def get_container_status(self, node: str, vmid: str) -> Dict[str, Any]:
        try:
            status = self.proxmox.nodes(node).lxc(vmid).status.current.get()
            config = self.proxmox.nodes(node).lxc(vmid).config.get()

            result = {
                'vmid': vmid,
                'node': node,
                'status': status.get('status', '未知'),
                'name': config.get('hostname', f'CT-{vmid}'),
                'uptime': status.get('uptime', 0),
                'cpu': status.get('cpu', 0),
                'mem': status.get('mem', 0),
                'maxmem': status.get('maxmem', 0),
                'template': config.get('template', '0') == '1'
            }

            return result
        except Exception as e:
            logger.error(f"获取容器 {vmid} 状态失败: {str(e)}")
            raise Exception(f"获取容器状态失败: {str(e)}")

    def start_container(self, node: str, vmid: str) -> Dict[str, Any]:
        try:
            result = self.proxmox.nodes(node).lxc(vmid).status.start.post()
            return {
                'success': True,
                'message': f'容器 {vmid} 启动命令已发送',
                'task_id': result
            }
        except Exception as e:
            logger.error(f"启动容器 {vmid} 失败: {str(e)}")
            return {
                'success': False,
                'message': f'启动容器失败: {str(e)}'
            }

    def stop_container(self, node: str, vmid: str) -> Dict[str, Any]:
        try:
            result = self.proxmox.nodes(node).lxc(vmid).status.stop.post()
            return {
                'success': True,
                'message': f'容器 {vmid} 停止命令已发送',
                'task_id': result
            }
        except Exception as e:
            logger.error(f"停止容器 {vmid} 失败: {str(e)}")
            return {
                'success': False,
                'message': f'停止容器失败: {str(e)}'
            }

    def shutdown_container(self, node: str, vmid: str) -> Dict[str, Any]:
        try:
            result = self.proxmox.nodes(node).lxc(vmid).status.shutdown.post()
            return {
                'success': True,
                'message': f'容器 {vmid} 关机命令已发送',
                'task_id': result
            }
        except Exception as e:
            logger.error(f"关机容器 {vmid} 失败: {str(e)}")
            return {
                'success': False,
                'message': f'关机容器失败: {str(e)}'
            }

    def reboot_container(self, node: str, vmid: str) -> Dict[str, Any]:
        try:
            result = self.proxmox.nodes(node).lxc(vmid).status.reboot.post()
            return {
                'success': True,
                'message': f'容器 {vmid} 重启命令已发送',
                'task_id': result
            }
        except Exception as e:
            logger.error(f"重启容器 {vmid} 失败: {str(e)}")
            return {
                'success': False,
                'message': f'重启容器失败: {str(e)}'
            }

    def create_container(self, data: ContainerCreate) -> Dict[str, Any]:
        try:
            node = data.node
            vmid = data.vmid

            net_config = f"name={data.network.name},bridge={data.network.bridge},ip={data.network.ip}"
            if data.network.gw:
                net_config += f",gw={data.network.gw}"
            if data.network.vlan:
                net_config += f",tag={data.network.vlan}"

            params = {
                'vmid': vmid,
                'ostemplate': data.ostemplate,
                'hostname': data.hostname,
                'password': data.password,
                'cores': data.cores,
                'memory': data.memory,
                'swap': data.swap,
                'rootfs': data.storage,
                'net0': net_config,
                'unprivileged': 1 if data.unprivileged else 0,
                'start': 1 if data.start else 0,
            }

            if data.features:
                params['features'] = data.features

            result = self.proxmox.nodes(node).lxc.post(**params)

            return {
                'success': True,
                'message': f'容器 {vmid} 创建任务已启动',
                'task_id': result
            }

        except Exception as e:
            logger.error(f"创建容器 {vmid} 失败: {str(e)}")
            return {
                'success': False,
                'message': f'创建容器失败: {str(e)}'
            }

    def get_task_status(self, node: str, task_id: str) -> Dict[str, Any]:
        try:
            task = self.proxmox.nodes(node).tasks(task_id).status.get()
            return {
                'status': task.get('status'),
                'exitstatus': task.get('exitstatus'),
                'type': task.get('type'),
                'id': task.get('id'),
                'starttime': task.get('starttime'),
                'endtime': task.get('endtime')
            }
        except Exception as e:
            logger.error(f"获取任务 {task_id} 状态失败: {str(e)}")
            return {
                'status': 'error',
                'message': f'获取任务状态失败: {str(e)}'
            }

proxmox_service = ProxmoxService()
