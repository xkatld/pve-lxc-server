from proxmoxer import ProxmoxAPI
from proxmoxer.core import ProxmoxResourceException
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
                verify_ssl=settings.proxmox_verify_ssl # 使用配置中的verify_ssl
            )
            logger.info("成功连接到 Proxmox 服务器")
        except Exception as e:
            logger.error(f"连接 Proxmox 服务器失败: {str(e)}")
            # 在初始化失败时，self.proxmox 将保持 None，后续调用会通过 _do_request 进一步处理
            raise Exception(f"无法连接到 Proxmox 服务器: {str(e)}")

    def _do_request(self, api_call_func, *args, **kwargs):
        if self.proxmox is None: # 如果初始连接就失败了
            logger.error("Proxmox API 实例未初始化，尝试重新连接。")
            self._connect() # 尝试再次连接
            if self.proxmox is None: # 如果还是失败
                 raise Exception("Proxmox API 实例无法初始化，请检查连接配置。")

        max_retries = 1
        for attempt in range(max_retries + 1):
            try:
                return api_call_func(*args, **kwargs)
            except (HTTPError, ConnectionError, ProxmoxResourceException) as e:
                is_auth_error = False
                if isinstance(e, HTTPError) and e.response is not None and e.response.status_code == 401:
                    is_auth_error = True
                elif "authenticate" in str(e).lower() or "ticket" in str(e).lower():
                    is_auth_error = True

                if is_auth_error and attempt < max_retries:
                    logger.warning(f"Proxmox API 请求认证失败 (尝试 {attempt + 1}/{max_retries + 1})，尝试重新连接: {str(e)}")
                    try:
                        self._connect()
                        if self.proxmox is None: # 确保连接成功更新了实例
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
                node_containers = self._do_request(self.proxmox.nodes(node_name).lxc.get)
                for container in node_containers:
                    container['node'] = node_name
                    containers.append(container)
            return containers
        except Exception as e:
            logger.error(f"获取容器列表失败: {str(e)}")
            raise Exception(f"获取容器列表失败: {str(e)}")

    def get_container_status(self, node: str, vmid: str) -> Dict[str, Any]:
        try:
            status = self._do_request(self.proxmox.nodes(node).lxc(vmid).status.current.get)
            config = self._do_request(self.proxmox.nodes(node).lxc(vmid).config.get)

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
            result = self._do_request(self.proxmox.nodes(node).lxc(vmid).status.start.post)
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
            result = self._do_request(self.proxmox.nodes(node).lxc(vmid).status.stop.post)
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
            result = self._do_request(self.proxmox.nodes(node).lxc(vmid).status.shutdown.post)
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
            result = self._do_request(self.proxmox.nodes(node).lxc(vmid).status.reboot.post)
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
        node = data.node # 提前获取，避免在异常处理中访问不到
        vmid = data.vmid # 提前获取
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

            result = self._do_request(self.proxmox.nodes(node).lxc.post, **params)

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
            result = self._do_request(self.proxmox.nodes(node).lxc(vmid).delete)
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
                status = self.get_task_status(node, task_id) # get_task_status 内部已使用 _do_request
                if status.get('status') == 'stopped':
                    return status.get('exitstatus') == 'OK'
                elif status.get('status') == 'error':
                    logger.error(f"任务 {task_id} 在节点 {node} 上执行失败: {status.get('exitstatus')}")
                    return False
            except Exception as e:
                logger.warning(f"等待任务 {task_id} 时发生错误: {str(e)}")
                return False # 出现获取状态的错误，也认为任务等待失败
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
                 logger.info(f"容器 {vmid} 可能不存在或获取状态失败 ({str(e)})，继续执行删除。")

            logger.info(f"正在删除容器 {vmid}...")
            delete_result = self.delete_container(node, vmid)
            if not delete_result['success']:
                 # 检查是否因为容器不存在而“失败”
                 if 'does not exist' in delete_result.get('message', '').lower() or \
                    (isinstance(delete_result.get('raw_response'), Exception) and \
                     '404' in str(delete_result.get('raw_response'))): # 假设message包含原始错误
                     logger.warning(f"删除容器 {vmid} 时返回 'does not exist' 或类似404错误，可能已被删除或不存在，继续执行创建。")
                 else:
                     return {'success': False, 'message': f"重建失败: 删除旧容器失败 - {delete_result['message']}"}
            else:
                if not self._wait_for_task(node, delete_result['task_id']):
                    # 如果删除任务本身失败（非容器不存在），则报错
                    task_status_info = self.get_task_status(node, delete_result['task_id'])
                    if not (task_status_info.get('exitstatus') == 'OK' and task_status_info.get('status') == 'stopped'):
                        # 有些情况下，即使PVE API返回成功，任务也可能因为 "does not exist" 而结束。
                        # 对于删除操作，如果容器一开始就不存在，PVE API的删除调用可能直接返回400/404错误，
                        # delete_container 方法已经处理了这种情况并返回 success:False。
                        # 如果delete_container返回success:True但_wait_for_task是False，则任务确实失败。
                        # 但是，更常见的是delete_container直接因404而success:False。
                        # 这里的逻辑需要小心处理 "成功删除一个不存在的容器" vs "删除任务失败"
                        logger.warning(f"删除容器 {vmid} 任务 ({delete_result['task_id']}) 未成功完成或超时，但继续尝试创建。任务状态: {task_status_info}")
                        # return {'success': False, 'message': f"重建失败: 删除容器任务 ({delete_result['task_id']}) 失败或超时。状态: {task_status_info}"}
                    # else:
                    # logger.info(f"容器 {vmid} 已删除 (任务 {delete_result['task_id']} 完成)。")

            logger.info(f"正在使用新配置创建容器 {vmid}...")
            create_data = ContainerCreate(
                node=node,
                vmid=int(vmid), # vmid 在这里已经是 str，转为 int
                ostemplate=data.ostemplate,
                hostname=data.hostname,
                password=data.password,
                cores=data.cores,
                cpulimit=data.cpulimit,
                memory=data.memory,
                swap=data.swap,
                storage=data.storage,
                disk_size=data.disk_size,
                network=NetworkInterface(**data.network.model_dump()), # 确保 network 是 NetworkInterface 实例
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
            console_info = self._do_request(self.proxmox.nodes(node).lxc(vmid).vncproxy.post)
            return {
                'success': True,
                'message': f'控制台票据获取成功',
                'data': {
                    'ticket': console_info['ticket'],
                    'port': console_info['port'],
                    'user': console_info['user'],
                    'node': node, # node 应该在 console_info 中，或者从参数传入
                    'host': settings.proxmox_host # PVE 主机 IP
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
            task = self._do_request(self.proxmox.nodes(node).tasks(task_id).status.get)
            return {
                'status': task.get('status'),
                'exitstatus': task.get('exitstatus'),
                'type': task.get('type'),
                'id': task.get('id'),
                'starttime': task.get('starttime'),
                'endtime': task.get('endtime'),
                'upid': task.get('upid') # 添加 UPID
            }
        except Exception as e:
            logger.error(f"获取任务 {task_id} 状态失败: {str(e)}")
            # 返回一个指示错误的数据结构，而不是直接抛出，以便调用方可以处理
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
                if 'vztmpl' in storage.get('content', ''): # 确保 storage 是字典且有 'content' 键
                    content = self._do_request(self.proxmox.nodes(node).storage(storage['storage']).content.get, content='vztmpl')
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
            networks = self._do_request(self.proxmox.nodes(node).network.get, type='bridge')
            return networks
        except Exception as e:
            logger.error(f"获取节点 {node} 网络失败: {str(e)}")
            raise Exception(f"获取节点网络失败: {str(e)}")

proxmox_service = ProxmoxService()
