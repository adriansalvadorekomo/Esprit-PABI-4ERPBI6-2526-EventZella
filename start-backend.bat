@echo off
cd /d "%~dp0backend"
echo Starting EventZilla FastAPI backend...
echo.
echo Routes available:
echo   http://localhost:8000/docs
echo   http://localhost:8000/health
echo   http://localhost:8000/categories
echo   http://localhost:8000/predict/fidelisation
echo.
venv\Scripts\uvicorn.exe api.main:app --host 0.0.0.0 --port 8000 --reload
