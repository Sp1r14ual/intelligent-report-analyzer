import os
import json
import requests
from typing import Optional, Callable
from .config import settings


class LLMClientError(Exception):
    pass


def _get_wsl_host_ip() -> Optional[str]:
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
                if "microsoft" in f.read().lower():
                    if os.path.exists("/etc/resolv.conf"):
                        with open("/etc/resolv.conf", "r", encoding="utf-8", errors="ignore") as rf:
                            for line in rf:
                                parts = line.strip().split()
                                if len(parts) >= 2 and parts[0] == "nameserver":
                                    return parts[1]
    except Exception:
        pass
    return None


def call_local_llama_server(
    system_prompt: str,
    user_prompt: str,
    base_url: Optional[str] = None,
    max_tokens: int = 2048,
    timeout: int = 180,
) -> str:
    """Вызывает локальный сервер llama-server (порт 8080) по OpenAI-совместимому API."""
    raw_base = (base_url or os.getenv("LLM_BASE_URL", "http://127.0.0.1:8080")).rstrip("/")
    candidate_urls = [f"{raw_base}/v1/chat/completions"]

    if "127.0.0.1" in raw_base or "localhost" in raw_base:
        host_ip = _get_wsl_host_ip()
        if host_ip:
            import urllib.parse
            parsed = urllib.parse.urlparse(raw_base)
            port = parsed.port or 8080
            candidate_urls.append(f"http://{host_ip}:{port}/v1/chat/completions")

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.05,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    last_error = None
    for url in candidate_urls:
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            if resp.status_code != 200:
                # Некоторые версии llama-server могут не поддерживать response_format json_object
                if resp.status_code in (400, 422):
                    p = dict(payload)
                    p.pop("response_format", None)
                    resp = requests.post(url, json=p, timeout=timeout)

            if resp.status_code != 200:
                raise LLMClientError(f"Ошибка llama-server ({resp.status_code}): {resp.text}")

            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.RequestException as exc:
            last_error = exc
            continue

    raise LLMClientError(
        f"Не удалось связаться с локальным llama-server по адресу {candidate_urls}: {last_error}. "
        "Убедитесь, что запущен `run_llama_server.bat` (модель YandexGPT 5 Lite 8B)."
    )


def call_llm(
    system_prompt: str,
    user_prompt: str,
    custom_caller: Optional[Callable[[str, str], str]] = None,
    max_tokens: int = 2048,
    timeout: int = 180,
    **kwargs,
) -> str:
    """
    Единая точка входа для обращения к локальной языковой модели YandexGPT 5 Lite (llama-server).
    """
    if custom_caller is not None:
        return custom_caller(system_prompt, user_prompt)

    return call_local_llama_server(system_prompt, user_prompt, max_tokens=max_tokens, timeout=timeout)
