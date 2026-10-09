@echo off
setlocal
cd /d "%~dp0"
if not exist backend\.env copy backend\.env.example backend\.env >nul
echo === Installing backend packages ===
cd backend
python -m pip install -r requirements.txt || goto :fail
rem The sample family (known password) is only created when you ask for it:  set CARELENS_SEED_DEMO=1
if "%CARELENS_SEED_DEMO%"=="1" if not exist instance\family.db python seed_demo.py
start "CareLens backend" cmd /k python app.py
cd ..\frontend
echo === Installing frontend packages ===
if not exist node_modules call npm install || goto :fail
start "CareLens frontend" cmd /k npm run dev
timeout /t 6 >nul
start http://localhost:5173
echo.
echo CareLens AI is running at http://localhost:5173  (choose Register to create your family)
if "%CARELENS_SEED_DEMO%"=="1" echo Demo login: meena / sample-pass-1  (sample data only - do not store real information in it)
echo AI: add a key in Settings - AI assistant inside the app.
exit /b 0
:fail
echo Setup failed - see the message above.
pause
exit /b 1
