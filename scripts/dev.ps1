$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$logs = Join-Path $root ".logs"
$python = Join-Path $backend "venv\Scripts\python.exe"
$backendUrl = "http://127.0.0.1:8000"
$frontendUrl = "http://127.0.0.1:3000"

function Test-PortListening($port) {
  $connection = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  return $null -ne $connection
}

function Wait-HttpOk($url, $name) {
  for ($attempt = 1; $attempt -le 30; $attempt++) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        Write-Host "$name pronto em $url"
        return
      }
    }
    catch {
      Start-Sleep -Milliseconds 700
    }
  }
  throw "$name nao respondeu em $url. Veja .logs\backend.log."
}

if (-not (Test-Path $python)) {
  Write-Host "Backend venv nao encontrado em backend\venv." -ForegroundColor Yellow
  Write-Host "Rode: backend\venv\Scripts\pip.exe install -r backend\requirements.txt"
  exit 1
}

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
  Write-Host "Dependencias do frontend nao encontradas." -ForegroundColor Yellow
  Write-Host "Rode: npm --prefix frontend install"
  exit 1
}

New-Item -ItemType Directory -Force -Path $logs | Out-Null

if (Test-PortListening 3000) {
  Write-Host "A porta 3000 ja esta em uso. Feche o outro Next.js antes de rodar npm run dev." -ForegroundColor Yellow
  exit 1
}

$startedBackend = $false
$backendProcess = $null
$frontendLocationPushed = $false

Push-Location $backend
try {
  Write-Host "Aplicando migracoes do backend..."
  & $python manage.py migrate --noinput
}
finally {
  Pop-Location
}

if (Test-PortListening 8000) {
  Write-Host "Backend ja esta ouvindo em $backendUrl. Vou reutilizar esse processo."
}
else {
  Write-Host "Subindo backend em $backendUrl"
  $backendLog = Join-Path $logs "backend.log"
  $backendErr = Join-Path $logs "backend.err.log"
  $backendProcess = Start-Process -FilePath $python -ArgumentList "manage.py", "runserver", "127.0.0.1:8000", "--noreload" -WorkingDirectory $backend -RedirectStandardOutput $backendLog -RedirectStandardError $backendErr -PassThru -WindowStyle Hidden
  $startedBackend = $true
}

try {
  Wait-HttpOk "$backendUrl/api/health/" "Backend"
  Write-Host "Subindo frontend em $frontendUrl"
  Write-Host "Cloudflare Tunnel: aponte para http://127.0.0.1:3000"
  Write-Host "Pressione Ctrl+C uma vez para encerrar o Next e o backend iniciado por este script."
  Push-Location $frontend
  $frontendLocationPushed = $true
  $env:NEXT_TELEMETRY_DISABLED = "1"
  $env:BACKEND_ORIGIN = $backendUrl
  npm.cmd run dev -- -H 0.0.0.0 -p 3000
}
finally {
  if ($frontendLocationPushed) {
    Pop-Location
  }
  if ($startedBackend -and $backendProcess -and -not $backendProcess.HasExited) {
    Stop-Process -Id $backendProcess.Id -Force
  }
}
