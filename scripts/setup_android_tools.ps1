$ErrorActionPreference = 'Stop'
$root = Join-Path $env:LOCALAPPDATA 'YouAI\devtools'
New-Item -ItemType Directory -Force $root | Out-Null
if (-not (Test-Path "$root\jdk\bin\java.exe")) {
    $releases = Invoke-RestMethod 'https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=x64&image_type=jdk&os=windows'
    $package = $releases[0].binary.package
    Invoke-WebRequest -UseBasicParsing $package.link -OutFile "$root\jdk.zip"
    if ((Get-FileHash "$root\jdk.zip" -Algorithm SHA256).Hash -ne $package.checksum) { throw 'JDK checksum mismatch' }
    Expand-Archive -LiteralPath "$root\jdk.zip" -DestinationPath "$root\jdk-unpacked" -Force
    $jdk = Get-ChildItem "$root\jdk-unpacked" -Directory | Select-Object -First 1
    New-Item -ItemType Junction -Path "$root\jdk" -Target $jdk.FullName | Out-Null
}
if (-not (Test-Path "$root\sdk19\cmdline-tools\bin\sdkmanager.bat")) {
    [xml]$repository = (Invoke-WebRequest -UseBasicParsing 'https://dl.google.com/android/repository/repository2-1.xml').Content
    $entry = $repository.SelectNodes("//*[local-name()='remotePackage']") | Where-Object { $_.path -eq 'cmdline-tools;19.0' }
    $archive = ($entry.archives.archive | Where-Object { $_.'host-os' -eq 'windows' }).complete
    & curl.exe -L --fail --silent --show-error ("https://dl.google.com/android/repository/" + $archive.url) -o "$root\sdk19.zip"
    if ($LASTEXITCODE -ne 0) { throw 'SDK download failed' }
    if ((Get-FileHash "$root\sdk19.zip" -Algorithm SHA1).Hash -ne $archive.checksum) { throw 'SDK checksum mismatch' }
    Expand-Archive -LiteralPath "$root\sdk19.zip" -DestinationPath "$root\sdk19" -Force
}
if (-not (Test-Path "$root\gradle-8.11.1\bin\gradle.bat")) {
    if (-not (Test-Path "$root\gradle.zip")) {
        & curl.exe -L --fail --silent --show-error 'https://services.gradle.org/distributions/gradle-8.11.1-bin.zip' -o "$root\gradle.zip"
        if ($LASTEXITCODE -ne 0) { throw 'Gradle download failed' }
    }
    $checksum = (& curl.exe -L --fail --silent --show-error 'https://services.gradle.org/distributions/gradle-8.11.1-bin.zip.sha256').Trim()
    if ((Get-FileHash "$root\gradle.zip" -Algorithm SHA256).Hash -ne $checksum) { throw 'Gradle checksum mismatch' }
    Expand-Archive -LiteralPath "$root\gradle.zip" -DestinationPath $root -Force
}
$env:JAVA_HOME = (Get-ChildItem "$root\jdk-unpacked" -Directory | Select-Object -First 1).FullName
$env:ANDROID_HOME = "$root\sdk"
1..15 | ForEach-Object { 'y' } | & "$root\sdk19\cmdline-tools\bin\sdkmanager.bat" "--sdk_root=$root\sdk" --licenses | Out-Null
& "$root\sdk19\cmdline-tools\bin\sdkmanager.bat" "--sdk_root=$root\sdk" 'platform-tools' 'platforms;android-35' 'build-tools;35.0.0'
if ($LASTEXITCODE -ne 0) { throw 'Android SDK install failed.' }
Write-Host 'Android build tools installed.'
