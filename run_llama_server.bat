@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title llama-server (WSL / Local LLM)

cd /d "%~dp0"

echo ========================================================
echo   Starting llama-server for local LLM (WSL)
echo ========================================================

set WSL_DISTRO=Ubuntu
set PORT=8080
set NGL=18
set CTX=8192
set MODEL_PATH=

REM 1. Command-line argument
if not "%~1"=="" (
    set "MODEL_PATH=%~1"
)

REM 2. Read from .env
if exist .env (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if "%%A"=="LOCAL_MODEL" if "!MODEL_PATH!"=="" set "MODEL_PATH=%%B"
        if "%%A"=="LLM_GPU_LAYERS" set "NGL=%%B"
        if "%%A"=="LLM_CTX" set "CTX=%%B"
    )
)

REM 3. Default models priority
if "!MODEL_PATH!"=="" (
    if exist "models\YandexGPT-5-Lite-8B-instruct-Q4_K_M.gguf" (
        set "MODEL_PATH=models\YandexGPT-5-Lite-8B-instruct-Q4_K_M.gguf"
    ) else if exist "models\Qwen2.5-7B-Instruct-Q4_K_M.gguf" (
        set "MODEL_PATH=models\Qwen2.5-7B-Instruct-Q4_K_M.gguf"
    ) else if exist "models\Qwen2.5-3B-Instruct-Q5_K_M.gguf" (
        set "MODEL_PATH=models\Qwen2.5-3B-Instruct-Q5_K_M.gguf"
    ) else if exist "models\Qwen2.5-3B-Instruct-Q4_K_M.gguf" (
        set "MODEL_PATH=models\Qwen2.5-3B-Instruct-Q4_K_M.gguf"
    )
)

if not exist "!MODEL_PATH!" (
    echo [ERROR] Model file not found: !MODEL_PATH!
    echo Please make sure the model exists in the models\ folder.
    pause
    exit /b 1
)

set "LINUX_MODEL=!MODEL_PATH:\=/!"

echo Model:       !MODEL_PATH!
echo Target Port: !PORT!
echo GPU Layers:  !NGL!
echo Context:     !CTX!
echo Host:        0.0.0.0 (Accessible from Windows at http://127.0.0.1:!PORT!)
echo.

REM 4. Check llama-server in WSL
set "WSL_BIN=wsl.exe"
%WSL_BIN% -d %WSL_DISTRO% -u root -e which llama-server >nul 2>nul
if %ERRORLEVEL% equ 0 goto run_wsl
goto run_windows

:run_wsl
echo [OK] Detected llama-server in WSL (%WSL_DISTRO%).
echo [INFO] Launching inside WSL (accessible from Windows at http://127.0.0.1:%PORT%)...
echo.

set "DRIVE_LETTER=%~d0"
set "DRIVE_LETTER=!DRIVE_LETTER:~0,1!"
for %%L in (a b c d e f g h i j k l m n o p q r s t u v w x y z) do (
    if /i "!DRIVE_LETTER!"=="%%L" set "DRIVE_LETTER=%%L"
)
set "P_PATH=%~p0"
set "P_PATH=!P_PATH:~0,-1!"
set "P_PATH=!P_PATH:\=/!"
set "WSL_DIR=/mnt/!DRIVE_LETTER!!P_PATH!"

%WSL_BIN% -d %WSL_DISTRO% -u root -e bash -c "cd '!WSL_DIR!' && ./run_llama_server.sh '!LINUX_MODEL!'"
goto end

:run_windows
echo [WARN] llama-server not found in WSL, falling back to Windows host...
set "WIN_LLAMA=C:\Users\Sp1r14ual\.docker\bin\inference\llama-server.exe"
if not exist "!WIN_LLAMA!" (
    where llama-server.exe >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "WIN_LLAMA=llama-server.exe"
    ) else (
        echo [ERROR] llama-server not found neither in WSL nor on Windows!
        echo To install in WSL: wsl -d Ubuntu -u root apt install -y llama.cpp-tools
        pause
        exit /b 1
    )
)
echo [OK] Using Windows binary: !WIN_LLAMA!
"!WIN_LLAMA!" -m "!MODEL_PATH!" --host 0.0.0.0 --port !PORT! -c !CTX! -ngl !NGL! -np 1
goto end

:end
pause
