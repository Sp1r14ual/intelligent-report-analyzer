@echo off
echo ========================================================
echo Starting llama.cpp server for local LLM...
echo ========================================================

set LLAMA_BIN=C:\Users\Sp1r14ual\.docker\bin\inference\llama-server.exe
set NGL=18
set PORT=8080
set MODEL_PATH=

:: 1. Проверяем аргумент командной строки
if not "%~1"=="" (
    set MODEL_PATH=%~1
)

:: 2. Считываем настройку LOCAL_MODEL из .env, если есть
if "%MODEL_PATH%"=="" (
    if exist .env (
        for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
            if "%%A"=="LOCAL_MODEL" set MODEL_PATH=%%B
        )
    )
)

:: 3. Приоритетный выбор по умолчанию (YandexGPT 5 -> Qwen 7B -> Qwen 3B)
if "%MODEL_PATH%"=="" (
    if exist "models\YandexGPT-5-Lite-8B-instruct-Q4_K_M.gguf" (
        set MODEL_PATH=models\YandexGPT-5-Lite-8B-instruct-Q4_K_M.gguf
    ) else if exist "models\Qwen2.5-7B-Instruct-Q4_K_M.gguf" (
        set MODEL_PATH=models\Qwen2.5-7B-Instruct-Q4_K_M.gguf
    ) else if exist "models\Qwen2.5-3B-Instruct-Q5_K_M.gguf" (
        set MODEL_PATH=models\Qwen2.5-3B-Instruct-Q5_K_M.gguf
    ) else if exist "models\Qwen2.5-3B-Instruct-Q4_K_M.gguf" (
        set MODEL_PATH=models\Qwen2.5-3B-Instruct-Q4_K_M.gguf
    )
)

if not exist "%LLAMA_BIN%" (
    echo [ERROR] llama-server.exe not found: %LLAMA_BIN%
    pause
    exit /b 1
)

if not exist "%MODEL_PATH%" (
    echo [ERROR] Model file not found: %MODEL_PATH%
    echo Please make sure the model exists in the models\ folder.
    pause
    exit /b 1
)

echo Model: %MODEL_PATH%
echo Port: %PORT%
echo Offload GPU layers: %NGL%
echo Context size: 8192
echo Single slot: -np 1
echo.

"%LLAMA_BIN%" -m "%MODEL_PATH%" --host 127.0.0.1 --port %PORT% -c 8192 -ngl %NGL% -np 1
pause


