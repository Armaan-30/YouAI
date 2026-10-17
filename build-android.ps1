$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$toolsRoot = Join-Path $env:LOCALAPPDATA 'YouAI\devtools'
if (-not (Test-Path "$toolsRoot\gradle-8.11.1\bin\gradle.bat") -or -not (Test-Path "$toolsRoot\sdk\platforms\android-35\android.jar")) { & "$PSScriptRoot\scripts\setup_android_tools.ps1" }
$env:JAVA_HOME = (Get-ChildItem "$toolsRoot\jdk-unpacked" -Directory | Select-Object -First 1).FullName
$env:ANDROID_HOME = "$toolsRoot\sdk"
@'
from app.main import DATA
from app.mobile import prepare
prepare(DATA / 'mobile')
import shutil
from pathlib import Path
target = Path('android/app/src/main/res/raw')
target.mkdir(parents=True, exist_ok=True)
shutil.copyfile(DATA / 'mobile' / 'ca.pem', target / 'laptop_ca.pem')
'@ | & .venv/Scripts/python -
if ($LASTEXITCODE -ne 0) { throw 'Certificate preparation failed' }
& "$toolsRoot\gradle-8.11.1\bin\gradle.bat" -p android assembleDebug lintDebug --console=plain
if ($LASTEXITCODE -ne 0) { throw 'Android build failed' }
Write-Host 'APK: android\app\build\outputs\apk\debug\app-debug.apk'
