#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "  Starting llama-server for YandexGPT 5 Lite 8B (WSL)    "
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

# 3. Выбор по умолчанию (YandexGPT 5 Lite 8B)
if [ -z "$MODEL_PATH" ]; then
    MODEL_PATH="models/YandexGPT-5-Lite-8B-instruct-Q4_K_M.gguf"
fi

if [ ! -f "$MODEL_PATH" ]; then
    echo "[ERROR] Model file not found: $MODEL_PATH"
    echo "Please make sure the model exists in the models/ folder."
    exit 1
fi

# Поиск исполняемого файла llama-server
LLAMA_BIN=""
if command -v llama-server >/dev/null 2>&1; then
    LLAMA_BIN="$(command -v llama-server)"
elif [ -x "/usr/local/bin/llama-server" ]; then
    LLAMA_BIN="/usr/local/bin/llama-server"
elif [ -x "$HOME/llama.cpp/build/bin/llama-server" ]; then
    LLAMA_BIN="$HOME/llama.cpp/build/bin/llama-server"
elif [ -x "/opt/llama.cpp/build/bin/llama-server" ]; then
    LLAMA_BIN="/opt/llama.cpp/build/bin/llama-server"
else
    # Проверка наличия бинарника Windows в окружении WSL
    for win_candidate in \
        "/mnt/c/Users/Sp1r14ual/.docker/bin/inference/llama-server.exe" \
        /mnt/c/Users/*/.docker/bin/inference/llama-server.exe
    do
        if [ -f "$win_candidate" ]; then
            LLAMA_BIN="$win_candidate"
            break
        fi
    done
fi

if [ -z "$LLAMA_BIN" ]; then
    echo "[ERROR] llama-server not found in Linux PATH, /usr/local/bin, or Windows host!"
    echo ""
    echo "Способы запуска:"
    echo "1. Рекомендуемый (напрямую из Windows):"
    echo "   Откройте терминал PowerShell или CMD на Windows и запустите:"
    echo "   .\\run_llama_server.bat"
    echo ""
    echo "2. Сборка и установка llama-server внутри WSL (Linux):"
    echo "   sudo apt update && sudo apt install -y build-essential cmake"
    echo "   git clone https://github.com/ggerganov/llama.cpp.git ~/llama.cpp"
    echo "   cd ~/llama.cpp && cmake -B build && cmake --build build --config Release -j\$(nproc)"
    echo "   sudo cp build/bin/llama-server /usr/local/bin/"
    exit 1
fi

echo "Binary:      $LLAMA_BIN"
echo "Model:       $MODEL_PATH"
echo "Port:        $PORT"
echo "GPU Layers:  $NGL"
echo "Context:     $CTX"
echo "Host:        0.0.0.0 (Accessible from Windows at http://127.0.0.1:$PORT)"
echo ""

if [[ "$LLAMA_BIN" == *.exe ]]; then
    WIN_MODEL=$(wslpath -w "$MODEL_PATH" 2>/dev/null || echo "$MODEL_PATH" | tr '/' '\\')
    exec "$LLAMA_BIN" -m "$WIN_MODEL" --host 0.0.0.0 --port "$PORT" -c "$CTX" -ngl "$NGL" -np 1
else
    exec "$LLAMA_BIN" -m "$MODEL_PATH" --host 0.0.0.0 --port "$PORT" -c "$CTX" -ngl "$NGL" -np 1
fi

