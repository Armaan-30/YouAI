param([Parameter(Mandatory=$true)][string]$BackendRoot, [Parameter(Mandatory=$true)][string]$RuntimeRoot)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
$pythonDir = Join-Path $RuntimeRoot 'python'
$pythonExe = Join-Path $pythonDir 'python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $existing = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($existing -and $existing.Source -notmatch 'WindowsApps') {
        & $existing.Source -c "import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,14) else 1)"
        if ($LASTEXITCODE -eq 0) { $pythonExe = $existing.Source }
    }
}
if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Output 'Downloading Python (official python.org installer)...'
    $installer = Join-Path $RuntimeRoot 'python-setup.exe'
    & curl.exe -L --fail --silent --show-error 'https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.exe' -o $installer
    if ($LASTEXITCODE -ne 0) { throw 'Python download failed. Restart YouAI to retry.' }
    if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne '9d9eb2709ef81bf5cd30db3c2096bdbc4ea10087c22e62f27d356b36f6ae9649') { throw 'Python download checksum mismatch.' }
    $process = Start-Process -FilePath $installer -ArgumentList @('/quiet','InstallAllUsers=0','Include_launcher=0','Include_test=0','PrependPath=0',"TargetDir=`"$pythonDir`"") -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -notin @(0,3010)) { throw "Python installation failed: $($process.ExitCode)" }
}
$ollamaExe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $ollamaExe)) {
    Write-Output 'Downloading Ollama from ollama.com...'
    $installer = Join-Path $RuntimeRoot 'OllamaSetup.exe'
    & curl.exe -L --fail --silent --show-error 'https://ollama.com/download/OllamaSetup.exe' -o $installer
    if ($LASTEXITCODE -ne 0) { throw 'Ollama download failed. Restart YouAI to retry.' }
    $signature = Get-AuthenticodeSignature -LiteralPath $installer
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Ollama') { throw 'Ollama installer signature could not be verified.' }
    $process = Start-Process -FilePath $installer -ArgumentList @('/VERYSILENT','/NORESTART') -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -notin @(0,3010)) { throw "Ollama installation failed: $($process.ExitCode)" }
}
Write-Output 'Installing backend dependencies and downloading voice, chat, embeddings and OCR models. This can take several minutes.'
& (Join-Path $BackendRoot 'setup.ps1') -EnvironmentPath (Join-Path $RuntimeRoot '.venv') -PythonExecutable $pythonExe
if ($LASTEXITCODE -ne 0) { throw 'Backend setup failed. Restart YouAI to retry.' }
Set-Content -LiteralPath (Join-Path $RuntimeRoot 'ready.txt') -Value '0.4.0'
