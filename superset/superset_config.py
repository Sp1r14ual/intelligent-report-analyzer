import os

SECRET_KEY = os.getenv("SUPERSET_SECRET_KEY", "TEST_SUPERSET_SECRET_KEY_DIPLOMA_2026_VERY_SECURE")
SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", "postgresql://superset:superset@postgres:5432/analytics_db")

# Отключение блокировок CSRF и Talisman для локальной разработки и Streamlit встраивания
WTF_CSRF_ENABLED = False
TALISMAN_ENABLED = False
ENABLE_CORS = True
CORS_OPTIONS = {
    'supports_credentials': True,
    'allow_headers': ['*'],
    'resources': ['*'],
    'origins': ['*']
}

FEATURE_FLAGS = {
    "ALERT_REPORTS": False,
    "EMBEDDED_SUPERSET": True,
    "DASHBOARD_NATIVE_FILTERS": True,
}

# Разрешаем запуск запросов в виртуальных датасетах
SQLLAB_ASYNC_TIME_LIMIT_SEC = 300
SQLLAB_TIMEOUT = 300
PUBLIC_ROLE_LIKE_GAMMA = True
GUEST_ROLE_NAME = "Public"
