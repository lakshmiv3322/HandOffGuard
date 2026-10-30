# HandoffGuard — Backend startup script
# Run this from the project root: .\start-backend.ps1

Set-Location "$PSScriptRoot\backend"
Write-Host "Starting HandoffGuard backend on http://localhost:8000 ..." -ForegroundColor Cyan
Write-Host "API docs: http://localhost:8000/docs" -ForegroundColor Green
python -m uvicorn app.main:app --reload --port 8000
