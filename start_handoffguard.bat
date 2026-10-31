@echo off
TITLE HandoffGuard Full-Stack Launcher
echo ============================================================
echo   Starting HandoffGuard Cold-Chain Custody Platform
echo   Team Deadhead Detectives (Lakshmi V ^& Bala Ashwin S)
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] Verifying Exasol / Database Connection...
docker ps | findstr "8563" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo     Exasol container detected on port 8563.
) else (
    echo     Notice: Exasol container not detected on 8563.
    echo     If you are using SQLite fallback, ensure DATABASE_ENGINE=sqlite in backend/.env
)

echo.
echo [2/3] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "HandoffGuard Backend (FastAPI)" cmd /k "cd /d "%~dp0backend" && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo.
echo [3/3] Launching React Frontend Dashboard on http://localhost:5173 ...
start "HandoffGuard Frontend (Vite)" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ============================================================
echo   Both services launched in separate windows!
echo   - Frontend: http://localhost:5173
echo   - Backend API Docs: http://127.0.0.1:8000/docs
echo ============================================================
echo.
pause
