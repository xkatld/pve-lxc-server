<h2>容器信息</h2>
<p>名称: {$container_name}</p>
<p>状态: {$container_info.status}</p>
<p>IP地址: {$container_info.ip}</p>
<p>镜像: {$container_info.description} ({$container_info.image_source})</p>
<p>创建时间: {$container_info.created_at}</p>
<p>消息: {$container_info.message}</p>
<pre>{$container_info|json_encode:JSON_PRETTY_PRINT}</pre>
