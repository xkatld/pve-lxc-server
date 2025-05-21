<h2>容器NAT规则</h2>

<h3>已有规则</h3>
{if $nat_rules}
<table class="table">
    <thead>
        <tr>
            <th>ID</th>
            <th>主机端口</th>
            <th>容器端口</th>
            <th>协议</th>
            <th>转发至IP</th>
            <th>创建时间</th>
            <th>操作</th>
        </tr>
    </thead>
    <tbody>
        {foreach from=$nat_rules item=rule}
        <tr>
            <td>{$rule.id}</td>
            <td>{$rule.host_port}</td>
            <td>{$rule.container_port}</td>
            <td>{$rule.protocol}</td>
            <td>{$rule.ip_at_creation}</td>
            <td>{$rule.created_at}</td>
            <td>
                <button class="btn btn-danger btn-sm" onclick="deleteNatRule({$rule.id})">删除</button>
            </td>
        </tr>
        {/foreach}
    </tbody>
</table>
{else}
<p>该容器当前没有NAT规则。</p>
{/if}

<h3>添加新规则</h3>
<form id="addNatRuleForm">
    <div class="form-group">
        <label for="host_port">主机端口:</label>
        <input type="number" class="form-control" id="host_port" name="host_port" min="1" max="65535" required>
    </div>
    <div class="form-group">
        <label for="container_port">容器端口:</label>
        <input type="number" class="form-control" id="container_port" name="container_port" min="1" max="65535" required>
    </div>
    <div class="form-group">
        <label for="protocol">协议:</label>
        <select class="form-control" id="protocol" name="protocol" required>
            <option value="tcp">TCP</option>
            <option value="udp">UDP</option>
        </select>
    </div>
    <button type="button" class="btn btn-primary" onclick="addNatRule()">添加规则</button>
</form>
<div id="addNatRuleResult" class="mt-3"></div>

<script>
const MODULE_CUSTOM_API = '{$MODULE_CUSTOM_API}';
const CURRENT_HOST_ID = '{$hostid}';

function addNatRule() {
    const form = document.getElementById('addNatRuleForm');
    const hostPort = form.host_port.value;
    const containerPort = form.container_port.value;
    const protocol = form.protocol.value;
    const resultDiv = document.getElementById('addNatRuleResult');
    resultDiv.innerHTML = '正在添加...';

    if (!hostPort || !containerPort || !protocol) {
        resultDiv.innerHTML = '<div class="alert alert-danger">所有字段都是必填项。</div>';
        return;
    }

    const formData = new URLSearchParams();
    formData.append('func', 'AddNatRule');
    formData.append('host_port', hostPort);
    formData.append('container_port', containerPort);
    formData.append('protocol', protocol);
    formData.append('hostid', CURRENT_HOST_ID);

    const jwtToken = 'YOUR_JWT_TOKEN_HERE';

    fetch(MODULE_CUSTOM_API, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Bearer ' + jwtToken
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            resultDiv.innerHTML = '<div class="alert alert-success">' + data.msg + '</div>';
            setTimeout(() => location.reload(), 2000);
        } else if (data.status === 'warning') {
             resultDiv.innerHTML = '<div class="alert alert-warning">' + data.msg + '</div>';
        }
        else {
            resultDiv.innerHTML = '<div class="alert alert-danger">' + (data.msg || JSON.stringify(data)) + '</div>';
        }
        console.log('AddNatRule response:', data);
    })
    .catch((error) => {
        resultDiv.innerHTML = '<div class="alert alert-danger">请求失败: ' + error + '</div>';
        console.error('Error calling AddNatRule:', error);
    });
}

function deleteNatRule(ruleId) {
     if (!confirm('确定要删除这条NAT规则吗？')) {
        return;
    }

    const resultDiv = document.getElementById('addNatRuleResult');
    resultDiv.innerHTML = '正在删除规则 ' + ruleId + '...';

     const formData = new URLSearchParams();
     formData.append('func', 'DeleteNatRule');
     formData.append('rule_id', ruleId);
     formData.append('hostid', CURRENT_HOST_ID);

     const jwtToken = 'YOUR_JWT_TOKEN_HERE';

     fetch(MODULE_CUSTOM_API, {
        method: 'POST',
        headers: {
             'Content-Type': 'application/x-www-form-urlencoded',
             'Authorization': 'Bearer ' + jwtToken
         },
        body: formData
     })
     .then(response => response.json())
     .then(data => {
        if (data.status === 'success' || data.status === 'warning') {
            resultDiv.innerHTML = '<div class="alert alert-success">' + data.msg + '</div>';
            setTimeout(() => location.reload(), 2000);
        } else {
            resultDiv.innerHTML = '<div class="alert alert-danger">' + (data.msg || JSON.stringify(data)) + '</div>';
        }
        console.log('DeleteNatRule response:', data);
     })
     .catch((error) => {
        resultDiv.innerHTML = '<div class="alert alert-danger">请求失败: ' + error + '</div>';
        console.error('Error calling DeleteNatRule:', error);
     });
}

</script>
