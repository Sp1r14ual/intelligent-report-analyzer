import json
import requests
from typing import Optional
from .config import settings


class SupersetClientError(Exception):
    pass


class SupersetClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.superset_url).rstrip("/")
        self.session = requests.Session()
        self.access_token: Optional[str] = None

    def check_health(self) -> bool:
        """Проверяет доступность сервера Apache Superset."""
        try:
            r = self.session.get(f"{self.base_url}/health", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> str:
        """Авторизуется в Apache Superset REST API и сохраняет JWT access token."""
        user = username or settings.superset_username
        pwd = password or settings.superset_password

        url = f"{self.base_url}/api/v1/security/login"
        payload = {
            "username": user,
            "password": pwd,
            "provider": "db",
            "refresh": True,
        }
        try:
            resp = self.session.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                raise SupersetClientError(
                    f"Ошибка авторизации в Superset ({resp.status_code}): {resp.text}"
                )
            data = resp.json()
            self.access_token = data.get("access_token")
            if not self.access_token:
                raise SupersetClientError("В ответе Superset отсутствует access_token")
            return self.access_token
        except requests.RequestException as exc:
            raise SupersetClientError(f"Не удалось подключиться к Superset по адресу {url}: {exc}")

    def import_bundle(self, bundle_zip_bytes: bytes) -> dict:
        """
        Импортирует ZIP-бандл (ассеты: база, датасеты, чарты, дашборд)
        через endpoint /api/v1/assets/import.
        """
        if not self.access_token:
            self.login()

        url = f"{self.base_url}/api/v1/assets/import/"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }

        # Пароль для подключения к PostgreSQL внутри бандла
        passwords_map = {
            "databases/PostgreSQL.yaml": settings.postgres_password
        }

        files = {
            "bundle": ("bundle.zip", bundle_zip_bytes, "application/zip")
        }
        data = {
            "passwords": json.dumps(passwords_map)
        }

        try:
            resp = self.session.post(url, headers=headers, files=files, data=data, timeout=30)
            if resp.status_code not in (200, 201):
                # Если токен истек, пробуем один раз перелогиниться
                if resp.status_code == 401:
                    self.login()
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    files = {"bundle": ("bundle.zip", bundle_zip_bytes, "application/zip")}
                    resp = self.session.post(url, headers=headers, files=files, data=data, timeout=30)

                if resp.status_code not in (200, 201):
                    raise SupersetClientError(
                        f"Ошибка импорта бандла в Superset ({resp.status_code}): {resp.text}"
                    )

            return resp.json()
        except requests.RequestException as exc:
            raise SupersetClientError(f"Ошибка запроса при импорте бандла в Superset: {exc}")

    def get_dashboard_url(self, dashboard_uuid: str) -> str:
        """Возвращает веб-ссылку на дашборд в интерфейсе Superset."""
        return f"{self.base_url}/superset/dashboard/{dashboard_uuid}/"
