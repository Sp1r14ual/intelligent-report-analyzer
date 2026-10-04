#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "  Starting llama-server for local LLM (Linux / WSL)    "
echo "========================================================"

PORT=8080
NGL=18
CTX=8192
MODEL_PATH=""

# 1. Аргумент командной строки
if [ -n "$1" ]; then
    MODEL_PATH="$1"
fi

# 2. Настройки из .env
if [ -z "$MODEL_PATH" ] && [ -f .env ]; then
    ENV_MODEL=$(grep -E '^LOCAL_MODEL=' .env 2>/dev/null | cut -d '=' -f2- | tr -d '\r"')
    ENV_NGL=$(grep -E '^LLM_GPU_LAYERS=' .env 2>/dev/null | cut -d '=' -f2- | tr -d '\r"')
    ENV_CTX=$(grep -E '^LLM_CTX=' .env 2>/dev/null | cut -d '=' -f2- | tr -d '\r"')
    [ -n "$ENV_MODEL" ] && MODEL_PATH="$ENV_MODEL"
    [ -n "$ENV_NGL" ] && NGL="$ENV_NGL"
    [ -n "$ENV_CTX" ] && CTX="$ENV_CTX"
fi

# Нормализация путей из Windows в Linux
MODEL_PATH=$(echo "$MODEL_PATH" | tr '\\' '/')

# 3. Выбор по умолчанию
if [ -z "$MODEL_PATH" ]; then
    if [ -f "models/YandexGPT-5-Lite-8B-instruct-Q4_K_M.gguf" ]; then
        MODEL_PATH="models/YandexGPT-5-Lite-8B-instruct-Q4_K_M.gguf"
    elif [ -f "models/Qwen2.5-7B-Instruct-Q4_K_M.gguf" ]; then
        MODEL_PATH="models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
    fi
fi

if [ ! -f "$MODEL_PATH" ]; then
    echo "[ERROR] Model file not found: $MODEL_PATH"
    echo "Please make sure the model exists in the models/ folder."
    exit 1
fi

echo "Model:       $MODEL_PATH"
echo "Port:        $PORT"
echo "GPU Layers:  $NGL"
echo "Context:     $CTX"
echo "Host:        0.0.0.0 (Accessible from Windows at http://127.0.0.1:$PORT)"
echo ""

exec llama-server -m "$MODEL_PATH" --host 0.0.0.0 --port "$PORT" -c "$CTX" -ngl "$NGL" -np 1
