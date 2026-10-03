import os
import json
import requests
from typing import Optional, Callable
from .config import settings


class LLMClientError(Exception):
    pass


def call_local_llama_server(system_prompt: str, user_prompt: str, base_url: Optional[str] = None) -> str:
    """Вызывает локальный сервер llama-server (порт 8080) по OpenAI-совместимому API."""
    url = f"{base_url or os.getenv('LLM_BASE_URL', 'http://127.0.0.1:8080')}/v1/chat/completions"

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.05,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    try:
        resp = requests.post(url, json=payload, timeout=90)
        if resp.status_code != 200:
            # Некоторые версии llama-server могут не поддерживать response_format json_object
            if resp.status_code in (400, 422):
                payload.pop("response_format", None)
                resp = requests.post(url, json=payload, timeout=90)

        if resp.status_code != 200:
            raise LLMClientError(f"Ошибка llama-server ({resp.status_code}): {resp.text}")

        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.RequestException as exc:
        raise LLMClientError(
            f"Не удалось связаться с локальным llama-server по адресу {url}: {exc}. "
            "Убедитесь, что запущен `run_llama_server.bat`."
        )


def call_gemini_api(system_prompt: str, user_prompt: str, api_key: Optional[str] = None, model: Optional[str] = None) -> str:
    """Вызывает Google Gemini API для генерации JSON-плана с устойчивостью к временным ошибкам моделей."""
    key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise LLMClientError("Не указан GEMINI_API_KEY для генерации дашборда.")

    primary_model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    # Список кандидатов моделей при 503/404
    candidate_models = [primary_model]
    for alt in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-pro", "gemini-flash-latest"]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    proxies = {}
    proxy_url = os.getenv("GEMINI_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        }
    }

    last_error = ""
    for candidate in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent?key={key}"
        try:
            resp = requests.post(url, json=payload, proxies=proxies, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
            last_error = f"Gemini API ({candidate}, status {resp.status_code}): {resp.text[:300]}"
            # Если 503 или 404, пробуем следующую модель из списка
            if resp.status_code in (404, 503, 429):
                continue
            break
        except requests.RequestException as exc:
            last_error = f"Ошибка сети при обращении к Gemini ({candidate}): {exc}"

    raise LLMClientError(f"Ошибка Gemini API: {last_error}")


def call_llm(
    system_prompt: str,
    user_prompt: str,
    provider: str = "gemini",
    gemini_key: Optional[str] = None,
    gemini_model: Optional[str] = None,
    custom_caller: Optional[Callable[[str, str], str]] = None,
) -> str:
    """
    Единая точка входа для обращения к LLM:
    - provider='gemini': вызывает облачный Gemini API
    - provider='local': вызывает локальный llama-server (YandexGPT / Qwen)
    - custom_caller: пользовательская функция для интеграции
    """
    if custom_caller is not None:
        return custom_caller(system_prompt, user_prompt)

    prov = provider.lower()
    if "gemini" in prov or "cloud" in prov:
        return call_gemini_api(system_prompt, user_prompt, api_key=gemini_key, model=gemini_model)
    elif "local" in prov or "llama" in prov or "qwen" in prov or "yandex" in prov:
        return call_local_llama_server(system_prompt, user_prompt)
    else:
        # По умолчанию пробуем Gemini при наличии ключа, иначе local
        if os.getenv("GEMINI_API_KEY"):
            return call_gemini_api(system_prompt, user_prompt, api_key=gemini_key, model=gemini_model)
        return call_local_llama_server(system_prompt, user_prompt)
