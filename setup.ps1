param([string]$EnvironmentPath = (Join-Path $PSScriptRoot '.venv'), [string]$PythonExecutable = 'python')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force -Path $EnvironmentPath | Out-Null
# Resolve Windows package redirection before pip performs atomic same-directory renames.
$EnvironmentPath = (& $PythonExecutable -c "import os,sys; print(os.path.realpath(sys.argv[1]))" $EnvironmentPath).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the Python environment location.' }
$venvPython = Join-Path $EnvironmentPath 'Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    & $PythonExecutable -m venv $EnvironmentPath
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 or newer, then run setup.ps1 again.' }
}
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
$env:YOUAI_ALLOW_DOWNLOAD = '1'
& $venvPython -c "from app.main import speech; speech.load(); print('Whisper is ready.')"
Remove-Item Env:YOUAI_ALLOW_DOWNLOAD
if ($LASTEXITCODE -ne 0) { throw 'Speech model download failed. Check your connection and retry.' }
& $venvPython -m app.download_wake
if ($LASTEXITCODE -ne 0) { throw 'Wake model download failed. Check your connection and retry.' }
$ollamaPath = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if (-not (Test-Path $ollamaPath)) {
    Write-Host 'Install Ollama from https://ollama.com/download/windows, then run this script again.'
    exit 1
}
try { Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 | Out-Null }
catch {
    Start-Process -FilePath $ollamaPath -ArgumentList 'serve' -WindowStyle Hidden
    Start-Sleep -Seconds 3
}
$modelName = if ($env:YOUAI_MODEL) { $env:YOUAI_MODEL } else { 'qwen2.5:3b' }
& $ollamaPath pull $modelName
if ($LASTEXITCODE -ne 0) { throw 'Language model download failed. Check your connection and retry.' }
& $ollamaPath pull nomic-embed-text
if ($LASTEXITCODE -ne 0) { throw 'Embedding model download failed.' }
& (Join-Path $PSScriptRoot 'scripts\setup_ocr.ps1')
Write-Host 'Ready. Run .\start.ps1 to open YouAI.'
