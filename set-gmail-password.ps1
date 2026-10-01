# Pide la contrasena de aplicacion de Gmail de forma oculta y la agrega a D:\BOTTRADER\.env
# Conserva las llaves de Alpaca que ya esten en el archivo. Claude no ve lo que escribes aqui.
$ErrorActionPreference = 'Stop'

function Read-Secret($prompt) {
    $s = Read-Host -Prompt $prompt -AsSecureString
    $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
}

Write-Host "=== Configuracion de correo (Gmail) ===" -ForegroundColor Cyan
$user = Read-Host "Correo Gmail (Enter = ricomonsalvedelavega@gmail.com)"
if (-not $user) { $user = 'ricomonsalvedelavega@gmail.com' }
$clave  = (Read-Secret "Contrasena de aplicacion (16 letras, oculto)") -replace '\s', ''

$envPath = Join-Path $PSScriptRoot '.env'
$lineas = @()
if (Test-Path $envPath) {
    $lineas = @(Get-Content $envPath | Where-Object { $_ -notmatch '^(GMAIL_USER|GMAIL_APP_PASSWORD|EMAIL_TO)=' })
}
$lineas += "GMAIL_USER=$user"
$lineas += "GMAIL_APP_PASSWORD=$clave"
$lineas += "EMAIL_TO=$user"
$lineas | Set-Content -Path $envPath -Encoding ascii

# Solo tu usuario puede leer el archivo
icacls $envPath /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null

$clave = $null
Write-Host "`nGuardado en $envPath" -ForegroundColor Green
Write-Host "Prueba el envio con:  python D:\BOTTRADER\bot_alpaca.py correo" -ForegroundColor Green
Read-Host "Pulsa Enter para cerrar"
