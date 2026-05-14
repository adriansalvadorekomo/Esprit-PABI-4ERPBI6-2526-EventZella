@echo off
REM Build script for EventZilla backend Docker image

echo Building EventZilla backend Docker image...
docker build -f backend.Dockerfile -t eventzilla-fastapi:latest .

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✓ Backend image built successfully!
    echo.
    echo To run the services:
    echo   docker-compose up -d
    echo.
    echo To view logs:
    echo   docker-compose logs -f
    echo.
    echo To stop services:
    echo   docker-compose down
) else (
    echo.
    echo ✗ Build failed. Please check the error messages above.
    exit /b 1
)
