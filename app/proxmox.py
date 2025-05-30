from proxmoxer import ProxmoxAPI
from proxmoxer.proxmoxer import ProxmoxResourceException
from requests.exceptions import HTTPError, ConnectionError
from .config import settings
from .schemas import ContainerCreate, ContainerRebuild, NetworkInterface
from typing import List, Dict, Any, Optional
import logging
import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class ProxmoxService:
    def __init__(self):
        self.proxmox: Optional[ProxmoxAPI] = None
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
            self.proxmox = None
            raise Exception(f"无法连接到 Proxmox 服务器: {str(e)}")

    def _do_request(self, api_call_func, *args, **kwargs):
        if self.proxmox is None:
            logger.error("Proxmox API 实例未初始化，尝试重新连接。")
            try:
                self._connect()
            except Exception as connect_initial_exc:
                 logger.error(f"Proxmox API _do_request中的初始连接尝试失败: {str(connect_initial_exc)}")
                 raise Exception(f"Proxmox API 实例无法初始化，请检查连接配置: {str(connect_initial_exc)}")

            if self.proxmox is None:
                 raise Exception("Proxmox API 实例无法在 _do_request 中初始化。")

        max_retries = 1
        for attempt in range(max_retries + 1):
            try:
                return api_call_func(*args, **kwargs)
            except (HTTPError, ConnectionError, ProxmoxResourceException) as e:
                is_auth_error = False
                if isinstance(e, HTTPError) and e.response is not None and e.response.status_code == 401:
                    is_auth_error = True
                elif "authenticate" in str(e).lower() or "ticket" in str(e).lower() or (isinstance(e, ProxmoxResourceException) and "401" in str(e)):
                    is_auth_error = True

                if is_auth_error and attempt < max_retries:
                    logger.warning(f"Proxmox API 请求认证失败 (尝试 {attempt + 1}/{max_retries + 1})，尝试重新连接: {str(e)}")
                    try:
                        self._connect()
                        if self.proxmox is None:
                            raise Exception("重新连接后 Proxmox API 实例仍未初始化。")
                    except Exception as connect_exc:
                        logger.error(f"重新连接 Proxmox 时失败: {str(connect_exc)}")
                        raise connect_exc
                else:
                    logger.error(f"Proxmox API 请求失败 (尝试 {attempt + 1}/{max_retries + 1}): {str(e)}")
                    raise e
            except Exception as e:
                logger.error(f"执行 Proxmox API 调用时发生未知错误: {str(e)}")
                raise

    def get_nodes(self) -> List[Dict[str, Any]]:
        try:
            nodes = self._do_request(self.proxmox.nodes.get)
            return [node for node in nodes if node.get('status') == 'online']
        except Exception as e:
            logger.error(f"获取节点列表失败: {str(e)}")
            raise Exception(f"获取节点列表失败: {str(e)}")

    def get_containers(self, node: str = None) -> List[Dict[str, Any]]:
        try:
            containers = []
            nodes_to_check = [node] if node else [n['node'] for n in self.get_nodes()]

            for node_name in nodes_to_check:
                get_lxc_func = self.proxmox.nodes(node_name).lxc.get
                node_containers = self._do_request(get_lxc_func)
                for container in node_containers:
                    container['node'] = node_name
                    containers.append(container)
            return containers
        except Exception as e:
            logger.error(f"获取容器列表失败: {str(e)}")
            raise Exception(f"获取容器列表失败: {str(e)}")

    def get_container_status(self, node: str, vmid: str) -> Dict[str, Any]:
        try:
            status_func = self.proxmox.nodes(node).lxc(vmid).status.current.get
            config_func = self.proxmox.nodes(node).lxc(vmid).config.get
            status = self._do_request(status_func)
            config = self._do_request(config_func)

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
            start_func = self.proxmox.nodes(node).lxc(vmid).status.start.post
            result = self._do_request(start_func)
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
            stop_func = self.proxmox.nodes(node).lxc(vmid).status.stop.post
            result = self._do_request(stop_func)
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
            shutdown_func = self.proxmox.nodes(node).lxc(vmid).status.shutdown.post
            result = self._do_request(shutdown_func)
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
            reboot_func = self.proxmox.nodes(node).lxc(vmid).status.reboot.post
            result = self._do_request(reboot_func)
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
        node = data.node
        vmid = data.vmid
        try:
            net_config = f"name={data.network.name},bridge={data.network.bridge},ip={data.network.ip}"
            if data.network.gw:
                net_config += f",gw={data.network.gw}"
            if data.network.vlan:
                net_config += f",tag={data.network.vlan}"
            if data.network.rate:
                net_config += f",rate={data.network.rate}"

            params = {
                'vmid': vmid,
                'ostemplate': data.ostemplate,
                'hostname': data.hostname,
                'password': data.password,
                'cores': data.cores,
                'memory': data.memory,
                'swap': data.swap,
                'rootfs': f"{data.storage}:{data.disk_size}",
                'net0': net_config,
                'unprivileged': 1 if data.unprivileged else 0,
                'start': 1 if data.start else 0,
            }

            if data.cpulimit is not None:
                params['cpulimit'] = data.cpulimit

            current_features = data.features or ""
            feature_list = [f.strip() for f in current_features.split(',') if f.strip()]

            if data.nesting:
                if 'nesting=1' not in feature_list:
                    feature_list.append('nesting=1')

            if feature_list:
                params['features'] = ",".join(feature_list)

            create_lxc_func = self.proxmox.nodes(node).lxc.post
            result = self._do_request(create_lxc_func, **params)

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

    def delete_container(self, node: str, vmid: str) -> Dict[str, Any]:
        try:
            delete_func = self.proxmox.nodes(node).lxc(vmid).delete
            result = self._do_request(delete_func)
            return {
                'success': True,
                'message': f'容器 {vmid} 删除任务已启动',
                'task_id': result
            }
        except Exception as e:
            logger.error(f"删除容器 {vmid} 失败: {str(e)}")
            return {
                'success': False,
                'message': f'删除容器失败: {str(e)}'
            }

    def _wait_for_task(self, node: str, task_id: str, timeout: int = 300) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                status = self.get_task_status(node, task_id)
                if status.get('status') == 'stopped':
                    return status.get('exitstatus') == 'OK'
                elif status.get('status') == 'error' or status.get('message'):
                    logger.error(f"任务 {task_id} 在节点 {node} 上执行失败: {status.get('exitstatus') or status.get('message')}")
                    return False
            except Exception as e:
                logger.warning(f"等待任务 {task_id} 时获取状态发生错误: {str(e)}")
                return False
            time.sleep(2)
        logger.error(f"等待任务 {task_id} 超时")
        return False

    def rebuild_container(self, node: str, vmid: str, data: ContainerRebuild) -> Dict[str, Any]:
        try:
            logger.info(f"开始重建容器 {vmid} on {node}...")
            try:
                status_info = self.get_container_status(node, vmid)
                if status_info['status'] == 'running':
                    logger.info(f"容器 {vmid} 正在运行，尝试停止...")
                    stop_result = self.stop_container(node, vmid)
                    if not stop_result['success']:
                        return {'success': False, 'message': f"重建失败: 停止容器失败 - {stop_result['message']}"}
                    if not self._wait_for_task(node, stop_result['task_id']):
                         return {'success': False, 'message': f"重建失败: 停止容器任务失败或超时 ({stop_result.get('task_id')})"}
                    logger.info(f"容器 {vmid} 已停止。")
            except Exception as e:
                 logger.info(f"检查容器 {vmid} 状态或停止容器时出现问题 ({str(e)})，继续执行删除。")

            logger.info(f"正在删除容器 {vmid}...")
            delete_result = self.delete_container(node, vmid)

            delete_failed_critically = False
            if not delete_result['success']:
                msg_lower = delete_result.get('message', '').lower()
                if 'does not exist' in msg_lower or 'not found' in msg_lower or '404' in msg_lower:
                    logger.warning(f"删除容器 {vmid} 时报告容器不存在或未找到，将继续重建。消息: {delete_result['message']}")
                else:
                    delete_failed_critically = True

            if delete_failed_critically:
                 return {'success': False, 'message': f"重建失败: 删除旧容器失败 - {delete_result['message']}"}

            if delete_result['success'] and delete_result.get('task_id'):
                if not self._wait_for_task(node, delete_result['task_id']):
                    task_status_info = self.get_task_status(node, delete_result['task_id'])
                    logger.warning(f"删除容器 {vmid} 任务 ({delete_result['task_id']}) 未成功完成或超时，但继续尝试创建。任务状态: {task_status_info}")

            logger.info(f"正在使用新配置创建容器 {vmid}...")
            create_data = ContainerCreate(
                node=node,
                vmid=int(vmid),
                ostemplate=data.ostemplate,
                hostname=data.hostname,
                password=data.password,
                cores=data.cores,
                cpulimit=data.cpulimit,
                memory=data.memory,
                swap=data.swap,
                storage=data.storage,
                disk_size=data.disk_size,
                network=NetworkInterface(**data.network.model_dump()),
                nesting=data.nesting,
                unprivileged=data.unprivileged,
                start=data.start,
                features=data.features
            )
            create_result = self.create_container(create_data)

            if create_result['success']:
                logger.info(f"容器 {vmid} 重建任务已启动。 Task ID: {create_result.get('task_id')}")
                return {
                    'success': True,
                    'message': f'容器 {vmid} 重建任务已启动',
                    'task_id': create_result.get('task_id')
                }
            else:
                logger.error(f"重建容器 {vmid} 的创建步骤失败: {create_result['message']}")
                return {
                    'success': False,
                    'message': f"重建失败 (创建步骤): {create_result['message']}"
                }
        except Exception as e:
            logger.error(f"重建容器 {vmid} 失败: {str(e)}")
            return {
                'success': False,
                'message': f'重建容器失败: {str(e)}'
            }

    def get_container_console(self, node: str, vmid: str) -> Dict[str, Any]:
        try:
            console_func = self.proxmox.nodes(node).lxc(vmid).vncproxy.post
            console_info = self._do_request(console_func)
            return {
                'success': True,
                'message': f'控制台票据获取成功',
                'data': {
                    'ticket': console_info['ticket'],
                    'port': console_info['port'],
                    'user': console_info['user'],
                    'node': node,
                    'host': settings.proxmox_host
                }
            }
        except Exception as e:
            logger.error(f"获取容器 {vmid} 控制台失败: {str(e)}")
            return {
                'success': False,
                'message': f'获取控制台失败: {str(e)}'
            }

    def get_task_status(self, node: str, task_id: str) -> Dict[str, Any]:
        try:
            status_func = self.proxmox.nodes(node).tasks(task_id).status.get
            task = self._do_request(status_func)
            return {
                'status': task.get('status'),
                'exitstatus': task.get('exitstatus'),
                'type': task.get('type'),
                'id': task.get('id'),
                'starttime': task.get('starttime'),
                'endtime': task.get('endtime'),
                'upid': task.get('upid')
            }
        except Exception as e:
            logger.error(f"获取任务 {task_id} 状态失败: {str(e)}")
            return {
                'status': 'error',
                'message': f'获取任务状态失败: {str(e)}',
                'task_id': task_id,
                'node': node
            }

    def get_templates(self, node: str) -> List[Dict[str, Any]]:
        try:
            storages = self._do_request(self.proxmox.nodes(node).storage.get)
            templates = []
            for storage in storages:
                if 'vztmpl' in storage.get('content', ''):
                    content_func = self.proxmox.nodes(node).storage(storage['storage']).content.get
                    content = self._do_request(content_func, content='vztmpl')
                    templates.extend(content)
            return templates
        except Exception as e:
            logger.error(f"获取节点 {node} 模板失败: {str(e)}")
            raise Exception(f"获取节点模板失败: {str(e)}")

    def get_storages(self, node: str) -> List[Dict[str, Any]]:
        try:
            storages = self._do_request(self.proxmox.nodes(node).storage.get)
            return storages
        except Exception as e:
            logger.error(f"获取节点 {node} 存储失败: {str(e)}")
            raise Exception(f"获取节点存储失败: {str(e)}")

    def get_networks(self, node: str) -> List[Dict[str, Any]]:
        try:
            networks_func = self.proxmox.nodes(node).network.get
            networks = self._do_request(networks_func, type='bridge')
            return networks
        except Exception as e:
            logger.error(f"获取节点 {node} 网络失败: {str(e)}")
            raise Exception(f"获取节点网络失败: {str(e)}")

proxmox_service = ProxmoxService()
