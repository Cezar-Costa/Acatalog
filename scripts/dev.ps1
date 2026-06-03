$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend "venv\Scripts\python.exe"

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

Write-Host "Aplicando migracoes do backend..."
Push-Location $backend
& $python manage.py migrate --noinput
Pop-Location

Write-Host "Subindo backend em http://127.0.0.1:8000"
$backendProcess = Start-Process -FilePath $python -ArgumentList "manage.py", "runserver", "127.0.0.1:8000", "--noreload" -WorkingDirectory $backend -PassThru -WindowStyle Hidden

try {
  Write-Host "Subindo frontend em http://127.0.0.1:3000"
  Write-Host "Pressione Ctrl+C para encerrar os servidores."
  Push-Location $frontend
  npm.cmd run dev
}
finally {
  Pop-Location
  if ($backendProcess -and -not $backendProcess.HasExited) {
    Stop-Process -Id $backendProcess.Id -Force
  }
}
