<?php

define('INCUS_MODULE_NAME', 'incusmanager');

function incusmanager_MetaData()
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, [], null, null, null);
    return [
        'DisplayName' => 'Incus Manager (via Flask)',
        'APIVersion' => '1.1',
        'HelpDoc' => 'https://your-mofang-url.com/modules/servers/incusmanager/docs/'
    ];
}

function incusmanager_ConfigOptions()
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, [], null, null, null);
    return [
        1 => [
            'type' => 'text',
            'name' => 'Container Name Prefix',
            'placeholder' => '例如: whmcs-{hostid}',
            'description' => '用于自动生成 Incus 容器名称的前缀 (建议包含 {hostid})',
            'default' => 'whmcs-{hostid}',
            'key' => 'container_name_prefix',
        ],
        2 => [
            'type' => 'text',
            'name' => 'Image Identifier',
            'placeholder' => '例如: ubuntu/20.04',
            'description' => '用于创建容器的 Incus 镜像名称或别名 (如 ubuntu/20.04, images:centos/7)',
            'default' => 'ubuntu/20.04',
            'key' => 'image_identifier',
        ],
    ];
}

function incusmanager_generateContainerName(array $params)
{
    $prefix_template = $params['configoptions']['container_name_prefix'];
    $hostid = $params['hostid'];
    $productid = $params['productid'];
    $uid = $params['uid'];

    $name = str_replace(['{hostid}', '{productid}', '{uid}'], [$hostid, $productid, $uid], $prefix_template);

    $name = strtolower($name);
    $name = preg_replace('/[^a-z0-9-]/', '', $name);
    $name = trim($name, '-');
    if (empty($name)) {
         $name = 'container-' . $hostid;
    }
    if (!preg_match('/^[a-z]/', $name)) {
         $name = 'c' . $name;
    }

    return $name;
}

function incusmanager_callFlaskApi(array $params, string $endpoint, string $method = 'GET', array $data = [], int $timeout = 60)
{
    $flask_base_url = rtrim($params['server_host'], '/');

    if (empty($flask_base_url)) {
        return ['success' => false, 'data' => 'Flask 应用的基础 URL 未在接口设置中配置 (server_host)。'];
    }

    $url = $flask_base_url . $endpoint;
    $ch = curl_init();

    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);

    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);

    $headers = [];

    if ($method === 'POST') {
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($data));
        $headers[] = 'Content-Type: application/x-www-form-urlencoded';
    } elseif ($method === 'DELETE') {
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'DELETE');
        if (!empty($data)) {
            curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($data));
             $headers[] = 'Content-Type: application/x-www-form-urlencoded';
        }
    }

    if (!empty($headers)) {
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    }

    logModuleCall(INCUS_MODULE_NAME, "Flask API Call: {$method} {$url}", $data, null, null, null);

    $response = curl_exec($ch);
    $curl_error = curl_error($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);

    curl_close($ch);

    if ($curl_error) {
        logModuleCall(INCUS_MODULE_NAME, "Flask API Error: {$method} {$url}", $data, "Curl Error: " . $curl_error, $response, null);
        return ['success' => false, 'data' => 'CURL 错误: ' . $curl_error];
    }

     logModuleCall(INCUS_MODULE_NAME, "Flask API Response: {$method} {$url}", $data, ['http_code' => $http_code, 'response' => $response], null, null);

    if ($response === false) {
         return ['success' => false, 'data' => '未收到响应或响应为空。'];
    }

    $decoded_response = json_decode($response, true);

    if (isset($decoded_response['status']) && ($decoded_response['status'] === 'success' || $decoded_response['status'] === 'warning')) {
         return ['success' => true, 'data' => $decoded_response];
    } elseif (isset($decoded_response['status']) && $decoded_response['status'] === 'error') {
         return ['success' => false, 'data' => $decoded_response['message'] ?? 'Flask API 内部错误但无详细消息。'];
    } else {
         if ($http_code >= 400) {
             return ['success' => false, 'data' => "HTTP 错误 {$http_code}: " . ($decoded_response['message'] ?? $response)];
         } else {
             return ['success' => false, 'data' => "Flask API 返回了未知格式或空响应 (HTTP状态码 {$http_code}): " . $response];
         }
    }
}

function incusmanager_CreateAccount(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);

    $container_name = incusmanager_generateContainerName($params);
    $image_identifier = $params['configoptions']['image_identifier'];

    if (empty($container_name) || empty($image_identifier)) {
        return ['status' => 'error', 'msg' => '模块配置错误: 容器名称或镜像标识符未设置。'];
    }

    $api_endpoint = '/container/create';
    $request_data = [
        'name' => $container_name,
        'image' => $image_identifier,
    ];

    $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'POST', $request_data, 180);

    if ($api_response['success']) {
        return 'success';
    } else {
        return ['status' => 'error', 'msg' => 'Flask API Error: ' . $api_response['data']];
    }
}

function incusmanager_SuspendAccount(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);

    $container_name = incusmanager_generateContainerName($params);

    $api_endpoint = "/container/{$container_name}/action";
    $request_data = ['action' => 'stop'];

    $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'POST', $request_data);

    if ($api_response['success']) {
        return 'success';
    } else {
        return ['status' => 'error', 'msg' => 'Flask API Error: ' . $api_response['data']];
    }
}

function incusmanager_UnsuspendAccount(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);

    $container_name = incusmanager_generateContainerName($params);

    $api_endpoint = "/container/{$container_name}/action";
    $request_data = ['action' => 'start'];

    $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'POST', $request_data);

    if ($api_response['success']) {
        return 'success';
    } else {
        return ['status' => 'error', 'msg' => 'Flask API Error: ' . $api_response['data']];
    }
}

function incusmanager_TerminateAccount(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);

    $container_name = incusmanager_generateContainerName($params);

    $api_endpoint = "/container/{$container_name}/action";
    $request_data = ['action' => 'delete'];

    $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'POST', $request_data, 180);

    if ($api_response['success']) {
        return 'success';
    } else {
        return ['status' => 'error', 'msg' => 'Flask API Error: ' . $api_response['data']];
    }
}

function incusmanager_Renew(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);
    return 'success';
}

function incusmanager_ChangePackage(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);
    $container_name = incusmanager_generateContainerName($params);

    $old_image = $params['old_configoptions']['image_identifier'];
    $new_image = $params['configoptions']['image_identifier'];

    $message = "容器 {$container_name} 的升降级操作。旧镜像: {$old_image}, 新镜像: {$new_image}. Flask 应用当前不支持直接升降级修改资源或更换镜像。";
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, "Warning: " . $message, null, null);

    return ['status' => 'success', 'msg' => $message . ' 请手动检查 Incus 容器状态。'];
}

function incusmanager_CreateTicket($params) {
     // Flask app does not have this functionality
     logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, "CreateTicket not implemented", null);
     return ['status' => 'error', 'msg' => '此功能未实现'];
}

function incusmanager_ReplyTicket($params) {
     // Flask app does not have this functionality
     logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, "ReplyTicket not implemented", null);
     return ['status' => 'error', 'msg' => '此功能未实现'];
}


function incusmanager_On(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);
    $container_name = incusmanager_generateContainerName($params);
    $api_endpoint = "/container/{$container_name}/action";
    $request_data = ['action' => 'start'];

    $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'POST', $request_data);

    if ($api_response['success']) {
        return 'success';
    } else {
        return ['status' => 'error', 'msg' => 'Flask API Error: ' . $api_response['data']];
    }
}

function incusmanager_Off(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);
    $container_name = incusmanager_generateContainerName($params);
    $api_endpoint = "/container/{$container_name}/action";
    $request_data = ['action' => 'stop'];

    $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'POST', $request_data);

    if ($api_response['success']) {
        return 'success';
    } else {
        return ['status' => 'error', 'msg' => 'Flask API Error: ' . $api_response['data']];
    }
}

function incusmanager_Reboot(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);
    $container_name = incusmanager_generateContainerName($params);
    $api_endpoint = "/container/{$container_name}/action";
    $request_data = ['action' => 'restart'];

    $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'POST', $request_data);

    if ($api_response['success']) {
        return 'success';
    } else {
        return ['status' => 'error', 'msg' => 'Flask API Error: ' . $api_response['data']];
    }
}

function incusmanager_HardOff(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);
    return incusmanager_Off($params);
}

function incusmanager_HardReboot(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);
    return incusmanager_Reboot($params);
}

function incusmanager_Reinstall($params) {
     // Flask app does not have this functionality
     logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, "Reinstall not implemented", null);
     return ['status' => 'error', 'msg' => '重装系统功能未实现'];
}

function incusmanager_CrackPassword($params) {
     // Flask app does not have this functionality
     logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, "CrackPassword not implemented", null);
     return ['status' => 'error', 'msg' => '破解密码功能未实现'];
}

function incusmanager_RescueSystem($params) {
     // Flask app does not have this functionality
     logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, "RescueSystem not implemented", null);
     return ['status' => 'error', 'msg' => '救援系统功能未实现'];
}

function incusmanager_Vnc(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, "VNC function not implemented in Flask app", null);
    return ['status' => 'error', 'msg' => 'VNC 功能未在后端的 Flask 应用中实现。'];
}

function incusmanager_Sync(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);
    $container_name = incusmanager_generateContainerName($params);

    $api_endpoint = "/container/{$container_name}/info";
    $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'GET', [], 10);

    if ($api_response['success']) {
        $container_info = $api_response['data'];
        $flask_status = $container_info['status'] ?? 'Unknown';
        $flask_ip = $container_info['ip'] ?? '';

        $whmcs_status_map = [
            'Running' => 'Active', // 魔方产品状态，非状态标识
            'Stopped' => 'Suspended',
            'Error' => 'Terminated',
            'Pending' => 'Pending',
            'Starting' => 'Active',
            'Stopping' => 'Suspended',
            'Unknown' => 'Pending',
        ];
        $whmcs_domainstatus = $whmcs_status_map[$flask_status] ?? 'Pending';

        $update_data = [
            'domainstatus' => $whmcs_domainstatus,
            'dedicatedip' => $flask_ip,
        ];

        return array_merge(['status' => 'success'], $update_data);

    } else {
        logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, "Failed to get live info, attempting DB fallback: " . $api_response['data'], null, null);
        return ['status' => 'error', 'msg' => '同步失败: 无法从 Flask 应用获取容器信息。' . $api_response['data']];
    }
}

function incusmanager_ClientArea(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);
    return [
        'container_info_tab' => [
            'name' => '容器信息',
        ],
        'nat_rules_tab' => [
            'name' => 'NAT规则',
        ],
        'exec_command_tab' => [
            'name' => '执行命令',
        ],
    ];
}

function incusmanager_ClientAreaOutput(array $params, string $key)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, "ClientAreaOutput key: " . $key, null, null);
    $container_name = incusmanager_generateContainerName($params);

    if ($key === 'container_info_tab') {
        $api_endpoint = "/container/{$container_name}/info";
        $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'GET');

        if ($api_response['success']) {
            $container_info = $api_response['data'];
            return [
                'template' => 'templates/container_info.tpl',
                'vars' => [
                    'module_params' => $params,
                    'container_info' => $container_info,
                    'container_name' => $container_name,
                     'MODULE_CUSTOM_API' => '', // 该模板不使用自定义API调用，但为了安全也置空
                     'hostid' => $params['hostid'],
                ]
            ];
        } else {
            return "<h3>无法获取容器信息</h3><p>错误: " . $api_response['data'] . "</p>";
        }

    } elseif ($key === 'nat_rules_tab') {
        $api_endpoint = "/container/{$container_name}/nat_rules";
        $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'GET');

        if ($api_response['success']) {
            $nat_rules = $api_response['data']['rules'] ?? [];
            return [
                'template' => 'templates/nat_rules.tpl',
                'vars' => [
                    'module_params' => $params,
                    'container_name' => $container_name,
                    'nat_rules' => $nat_rules,
                    'MODULE_CUSTOM_API' => '/serverapi.php', // 假设魔方前台调用模块方法走这个入口
                    'hostid' => $params['hostid'],
                ]
            ];
        } else {
            return "<h3>无法获取NAT规则</h3><p>错误: " . $api_response['data'] . "</p>";
        }

    } elseif ($key === 'exec_command_tab') {
        return [
             'template' => 'templates/exec_command.tpl',
             'vars' => [
                 'module_params' => $params,
                 'container_name' => $container_name,
                 'MODULE_CUSTOM_API' => '/serverapi.php', // 假设魔方前台调用模块方法走这个入口
                 'hostid' => $params['hostid'],
             ]
        ];
    }

    return "<h3>未知选项卡</h3><p>请求的选项卡内容不存在。</p>";
}

function incusmanager_AllowFunction()
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, [], null, null, null);
    return [
        'client' => [
            'ExecCommand',
            'AddNatRule',
            'DeleteNatRule',
        ],
        'admin' => [
            'ExecCommand',
            'AddNatRule',
            'DeleteNatRule',
        ]
    ];
}

function incusmanager_ExecCommand(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);
    $container_name = incusmanager_generateContainerName($params);
    $command_to_exec = $params['command'] ?? ($params['post_data']['command'] ?? '');

    if (empty($command_to_exec)) {
        return ['status' => 'error', 'msg' => '执行的命令不能为空。'];
    }

    $api_endpoint = "/container/{$container_name}/exec";
    $request_data = ['command' => $command_to_exec];

    $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'POST', $request_data, 180);

    if ($api_response['success']) {
        if (($api_response['data']['status'] ?? 'error') === 'success') {
             return ['status' => 'success', 'output' => $api_response['data']['output'] ?? ''];
        } else {
             return ['status' => 'error', 'msg' => $api_response['data']['message'] ?? '命令执行失败', 'output' => $api_response['data']['output'] ?? ''];
        }
    } else {
        return ['status' => 'error', 'msg' => '调用 Flask API 执行命令失败: ' . $api_response['data']];
    }
}

function incusmanager_AddNatRule(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);
    $container_name = incusmanager_generateContainerName($params);

    $host_port = $params['host_port'] ?? ($params['post_data']['host_port'] ?? null);
    $container_port = $params['container_port'] ?? ($params['post_data']['container_port'] ?? null);
    $protocol = $params['protocol'] ?? ($params['post_data']['protocol'] ?? null);

    if (empty($host_port) || empty($container_port) || empty($protocol)) {
         return ['status' => 'error', 'msg' => '主机端口、容器端口和协议不能为空。'];
    }

    $api_endpoint = "/container/{$container_name}/add_nat_rule";
    $request_data = [
        'host_port' => $host_port,
        'container_port' => $container_port,
        'protocol' => $protocol,
    ];

    $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'POST', $request_data);

    if ($api_response['success']) {
        return ['status' => 'success', 'msg' => $api_response['data']['message'] ?? 'NAT规则添加成功，但无详细信息。'];
    } else {
        return ['status' => 'error', 'msg' => '调用 Flask API 添加 NAT 规则失败: ' . $api_response['data']];
    }
}

function incusmanager_DeleteNatRule(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);

    $rule_id = $params['rule_id'] ?? ($params['post_data']['rule_id'] ?? null);

    if (empty($rule_id)) {
        return ['status' => 'error', 'msg' => 'NAT 规则 ID 不能为空。'];
    }

    $api_endpoint = "/container/nat_rule/{$rule_id}";

    $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'DELETE');

    if ($api_response['success']) {
        return ['status' => 'success', 'msg' => $api_response['data']['message'] ?? 'NAT规则删除成功，但无详细信息。'];
    } else {
        return ['status' => 'error', 'msg' => '调用 Flask API 删除 NAT 规则失败: ' . $api_response['data']];
    }
}


function incusmanager_Status(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);
    $container_name = incusmanager_generateContainerName($params);

    $api_endpoint = "/container/{$container_name}/info";
    $api_response = incusmanager_callFlaskApi($params, $api_endpoint, 'GET', [], 10);

    if ($api_response['success']) {
        $container_info = $api_response['data'];
        $flask_status = $container_info['status'] ?? 'Unknown';

        $mofang_status_flag_map = [
            'Running' => 'on',
            'Stopped' => 'off',
            'Error' => 'unknown',
            'Pending' => 'waiting',
            'Starting' => 'process',
            'Stopping' => 'process',
            'Unknown' => 'unknown',
        ];
        $mofang_status_flag = $mofang_status_flag_map[$flask_status] ?? 'unknown';

        $mofang_status_des_map = [
            'Running' => '开机',
            'Stopped' => '关机',
            'Error' => '错误',
            'Pending' => '创建中',
            'Starting' => '启动中',
            'Stopping' => '停止中',
            'Unknown' => '未知状态',
        ];
        $mofang_status_des = $mofang_status_des_map[$flask_status] ?? '未知状态';

        return [
            'status' => 'success',
            'data' => [
                'status' => $mofang_status_flag,
                'des' => $mofang_status_des,
            ]
        ];

    } else {
        logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, "Failed to get live status: " . $api_response['data'], null, null);
        return [
            'status' => 'success',
            'data' => [
                'status' => 'unknown',
                'des' => '无法获取实时状态 (' . (substr($api_response['data'], 0, 50)) . '...)',
            ]
        ];
    }
}

function incusmanager_UsageUpdate(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, "UsageUpdate called, but Flask app does not expose usage data.", null);
    return 'success';
}

function incusmanager_ClientButton(array $params)
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, null, null);
    return [];
}

function incusmanager_Chart()
{
    logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, [], null, "Chart definition called, but Flask app does not provide chart data.", null);
    return [];
}

function incusmanager_ChartData(array $params)
{
     logModuleCall(INCUS_MODULE_NAME, __FUNCTION__, $params, null, "ChartData called, but Flask app does not provide chart data.", null);
    return ['status' => 'error', 'msg' => '图表数据功能未在后端的 Flask 应用中实现。'];
}

if (!function_exists('logModuleCall')) {
    function logModuleCall($module, $action, $request, $response, $responsedata, $processeddata) {
        $log_message = sprintf(
            "[%s] Module: %s, Action: %s, Request: %s, Response: %s\n",
            date('Y-m-d H:i:s'),
            $module,
            $action,
            json_encode($request, JSON_UNESCAPED_UNICODE),
            json_encode($response, JSON_UNESCAPED_UNICODE),
            json_encode($responsedata, JSON_UNESCAPED_UNICODE)
        );
        error_log($log_message);
    }
}
