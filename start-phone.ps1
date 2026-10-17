$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
try { Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 | Out-Null }
catch {
    $ollamaPath = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path $ollamaPath) { Start-Process -FilePath $ollamaPath -ArgumentList 'serve' -WindowStyle Hidden }
    else { throw 'Ollama is missing. Run setup.ps1 first.' }
}
& "$PSScriptRoot\stop.ps1"
New-Item -ItemType Directory -Force .runtime | Out-Null
$server = Start-Process -FilePath "$PSScriptRoot\.venv\Scripts\python.exe" -ArgumentList '-m','app.serve' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$PSScriptRoot\.runtime\server.log" -RedirectStandardError "$PSScriptRoot\.runtime\server-error.log"
$server.Id | Set-Content .runtime/server.pid
$online = $false
for ($i=0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    try { Invoke-WebRequest 'http://127.0.0.1:8765/' -UseBasicParsing -TimeoutSec 2 | Out-Null; $online=$true; break } catch {}
}
if (-not $online) { throw 'Server did not start. See .runtime/server-error.log.' }
Write-Host 'Open http://127.0.0.1:8765 and use Conversation > Pair Android phone.'
Write-Host 'Windows Firewall must allow TCP 8768 on your private home network for phone access.'
