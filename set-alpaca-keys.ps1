# Pide las credenciales de Alpaca de forma oculta y las guarda en D:\BOTTRADER\.env
# Claude no ve lo que escribes aqui.
$ErrorActionPreference = 'Stop'

function Read-Secret($prompt) {
    $s = Read-Host -Prompt $prompt -AsSecureString
    $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
}

Write-Host "=== Configuracion de credenciales Alpaca ===" -ForegroundColor Cyan
$key    = Read-Secret "ALPACA_API_KEY (oculto)"
$secret = Read-Secret "ALPACA_SECRET_KEY (oculto)"
$mode   = Read-Host "Cuenta: [P]aper o [L]ive? (Enter = Paper)"
$url    = if ($mode -match '^[Ll]') { 'https://api.alpaca.markets' } else { 'https://paper-api.alpaca.markets' }

$envPath = Join-Path $PSScriptRoot '.env'
@(
    "ALPACA_API_KEY=$key"
    "ALPACA_SECRET_KEY=$secret"
    "ALPACA_BASE_URL=$url"
) | Set-Content -Path $envPath -Encoding ascii

# Solo tu usuario puede leer el archivo
icacls $envPath /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null

$key = $null; $secret = $null
Write-Host "`nGuardado en $envPath ($url)" -ForegroundColor Green
Read-Host "Pulsa Enter para cerrar"
