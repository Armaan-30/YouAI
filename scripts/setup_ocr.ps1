param([ValidateSet('eng','hin','spa','fra','deu')][string[]]$Languages = @('eng','hin','spa','fra','deu'))
$ErrorActionPreference = 'Stop'
$destination = Join-Path $env:LOCALAPPDATA 'YouAI\models\tessdata'
New-Item -ItemType Directory -Force $destination | Out-Null
foreach ($language in $Languages) {
    $target = Join-Path $destination "$language.traineddata"
    if (Test-Path -LiteralPath $target) { continue }
    & curl.exe -L --fail --silent --show-error "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/$language.traineddata" -o "$target.partial"
    if ($LASTEXITCODE -ne 0) { throw "OCR download failed: $language. Run setup again to retry." }
    Move-Item -LiteralPath "$target.partial" -Destination $target -Force
}
Write-Host 'Local OCR languages ready.'
