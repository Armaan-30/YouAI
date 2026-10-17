# Run once in an Administrator PowerShell if the phone cannot connect.
$ErrorActionPreference = 'Stop'
if (-not (Get-NetFirewallRule -Name 'YouAI-Private-LAN' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name 'YouAI-Private-LAN' -DisplayName 'YouAI paired Android access' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8768 -Profile Private -RemoteAddress LocalSubnet | Out-Null
}
Write-Host 'YouAI TCP 8768 is allowed only from the local subnet on Private networks.'
