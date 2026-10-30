# HandoffGuard — Frontend startup script
# Run this from the project root: .\start-frontend.ps1

Set-Location "$PSScriptRoot\frontend"
Write-Host "Starting HandoffGuard frontend on http://localhost:5173 ..." -ForegroundColor Cyan
npm run dev
