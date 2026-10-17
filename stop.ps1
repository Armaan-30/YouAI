$pidFile = Join-Path $PSScriptRoot '.runtime\server.pid'
if (Test-Path $pidFile) {
    $serverId = [int](Get-Content $pidFile)
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $serverId" -ErrorAction SilentlyContinue
    if ($process -and $process.ExecutablePath -eq "$PSScriptRoot\.venv\Scripts\python.exe" -and $process.CommandLine -match '(uvicorn.*app.main:app|app\.serve)') {
        # The Windows venv launcher can own a separate Python child process.
        # Stop only the verified YouAI process tree, leaving Ollama alone.
        & "$env:WINDIR\System32\taskkill.exe" /PID $serverId /T /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not stop the verified YouAI process tree.' }
        Remove-Item -LiteralPath $pidFile
        Write-Host 'YouAI stopped. Ollama is managed separately.'
    }
}
