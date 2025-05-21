<h2>执行命令</h2>
<p>在容器 <strong>{$container_name}</strong> 中执行命令。</p>

<form id="execCommandForm">
    <div class="form-group">
        <label for="command_input">命令:</label>
        <input type="text" class="form-control" id="command_input" name="command" placeholder="例如: ls -l /" required>
    </div>
    <button type="button" class="btn btn-primary" onclick="executeCommand()">执行</button>
</form>

<h3>输出:</h3>
<pre id="commandOutput" style="background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 10px; max-height: 300px; overflow-y: auto;"></pre>
<div id="commandResult" class="mt-3"></div>

<script>
const MODULE_CUSTOM_API_EXEC = '{$MODULE_CUSTOM_API}';
const CURRENT_HOST_ID_EXEC = '{$hostid}';

function executeCommand() {
    const form = document.getElementById('execCommandForm');
    const command = form.command_input.value;
    const outputPre = document.getElementById('commandOutput');
    const resultDiv = document.getElementById('commandResult');

    if (!command) {
        resultDiv.innerHTML = '<div class="alert alert-warning">命令不能为空。</div>';
        return;
    }

    outputPre.textContent = '正在执行命令...';
    resultDiv.innerHTML = '';

    const formData = new URLSearchParams();
    formData.append('func', 'ExecCommand');
    formData.append('command', command);
    formData.append('hostid', CURRENT_HOST_ID_EXEC);

    const jwtToken = 'YOUR_JWT_TOKEN_HERE';

    fetch(MODULE_CUSTOM_API_EXEC, {
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
            outputPre.textContent = data.output || '命令执行成功，无输出。';
            resultDiv.innerHTML = '<div class="alert alert-success">命令执行成功。</div>';
        } else {
            outputPre.textContent = data.output || '命令执行失败。';
            resultDiv.innerHTML = '<div class="alert alert-danger">' + (data.msg || '命令执行失败') + '</div>';
        }
        console.log('ExecCommand response:', data);
    })
    .catch((error) => {
        outputPre.textContent = '执行命令时发生错误。';
        resultDiv.innerHTML = '<div class="alert alert-danger">请求失败: ' + error + '</div>';
        console.error('Error calling ExecCommand:', error);
    });
}
</script>
