"""Скрипт для быстрой проверки подключения и валидности ключа Google Gemini API."""

import os
import sys
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def test_gemini(api_key: str | None = None, model: str = "gemini-2.5-flash"):
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        if len(sys.argv) > 1:
            key = sys.argv[1].strip()
        else:
            try:
                key = input("Введите ваш Gemini API Key: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nОтмена.")
                return

    if not key:
        print("[ОШИБКА] Ключ не передан.")
        return

    print(f"-> Проверка подключения к Gemini API...")
    print(f"-> Модель: {model}")
    print(f"-> Ключ: {key[:6]}...{key[-4:] if len(key) > 10 else ''}")

    base_url = (os.getenv("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com").rstrip("/")
    url = f"{base_url}/v1beta/models/{model}:generateContent?key={key}"

    payload = {
        "contents": [
            {
                "parts": [{"text": "Ответь одним коротким предложением: подтверди, что подключение успешно."}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 100,
        }
    }

    proxies = {}
    proxy = os.getenv("GEMINI_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if proxy:
        print(f"-> Использование прокси: {proxy}")
        proxies = {"http": proxy, "https": proxy}

    try:
        resp = requests.post(url, json=payload, timeout=30, proxies=proxies if proxies else None)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts).strip()
                print("\n========================================================")
                print(" УСПЕШНО! Ответ от модели:")
                print(text)
                print("========================================================\n")
                return True
            print("[ВНИМАНИЕ] Пустой ответ от модели.")
            return False

        print(f"\n[ОШИБКА HTTP {resp.status_code}]")
        err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        err_msg = err_data.get("error", {}).get("message", resp.text)
        print(f"Сообщение API: {err_msg}")

        if "API_KEY_INVALID" in err_msg or (resp.status_code == 400 and "API key" in err_msg):
            print("\n-> Причина: Неверный API-ключ. Проверьте ключ в Google AI Studio.")
        elif "User location is not supported" in err_msg:
            print("\n-> Причина: Геолокация не поддерживается Google Gemini без VPN/прокси.")
            print("   Решение: Включите VPN или укажите прокси в .env (GEMINI_PROXY=http://127.0.0.1:10808).")
        elif resp.status_code == 404:
            print(f"\n-> Модель {model} не найдена. Попробуйте gemini-1.5-flash.")
        return False

    except requests.exceptions.Timeout:
        print("\n[ОШИБКА] Таймаут соединения (сервер не ответил за 30 секунд).")
        return False
    except requests.exceptions.RequestException as e:
        print(f"\n[ОШИБКА СЕТИ] Не удалось подключиться к Google: {e}")
        print("Подсказка: Проверьте интернет-соединение или настройки VPN/прокси.")
        return False


if __name__ == "__main__":
    test_gemini()
