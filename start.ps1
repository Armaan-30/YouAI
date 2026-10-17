$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) { throw 'Run .\setup.ps1 first.' }
New-Item -ItemType Directory -Force -Path "$PSScriptRoot\.runtime" | Out-Null
$ollamaPath = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
try { Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 | Out-Null }
catch {
    if (Test-Path $ollamaPath) {
        Start-Process -FilePath $ollamaPath -ArgumentList 'serve' -WindowStyle Hidden
    }
}
try {
    Invoke-RestMethod 'http://127.0.0.1:8765/api/status' -TimeoutSec 3 | Out-Null
} catch {
    $server = Start-Process -FilePath "$PSScriptRoot\.venv\Scripts\python.exe" -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8765' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$PSScriptRoot\.runtime\server.log" -RedirectStandardError "$PSScriptRoot\.runtime\server-error.log"
    $server.Id | Set-Content "$PSScriptRoot\.runtime\server.pid"
    $online = $false
    for ($i=0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        try { Invoke-WebRequest 'http://127.0.0.1:8765/' -UseBasicParsing -TimeoutSec 2 | Out-Null; $online=$true; break } catch {}
    }
    if (-not $online) { throw 'App did not start. See .runtime\server-error.log.' }
}
Start-Process 'http://127.0.0.1:8765'
Write-Host 'YouAI is running at http://127.0.0.1:8765. Close it with .\stop.ps1.'
