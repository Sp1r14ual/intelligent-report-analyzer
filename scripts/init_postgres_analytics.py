"""
Скрипт инициализации аналитических витрин PostgreSQL и наполнения данными из отчетов ВПО и НИОКР.
Может запускаться как локально, так и внутри контейнеров.
"""

import os
import sys
import psycopg2

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "analytics_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "superset")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "superset")


def get_connection():
    candidates = [POSTGRES_HOST]
    try:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from analyzer import get_wsl_host_ip
        wsl_ip = get_wsl_host_ip()
        if wsl_ip and wsl_ip not in candidates:
            candidates.append(wsl_ip)
    except Exception:
        pass

    last_exc = None
    for h in candidates:
        try:
            return psycopg2.connect(
                host=h,
                port=POSTGRES_PORT,
                dbname=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                connect_timeout=3,
            )
        except Exception as exc:
            last_exc = exc
    raise last_exc


def init_analytics_database():
    print(f"Подключение к PostgreSQL: {POSTGRES_USER}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}...")
    try:
        conn = get_connection()
        conn.autocommit = True
        cursor = conn.cursor()
    except Exception as exc:
        print(f"❌ Не удалось подключиться к PostgreSQL: {exc}")
        print("Убедитесь, что контейнер PostgreSQL запущен (scripts/start_superset.bat)")
        return False

    # 1. Применение DDL схемы и витрин
    schema_path = os.path.join(os.path.dirname(__file__), "..", "sql", "analytics_schema.sql")
    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            ddl_sql = f.read()
        cursor.execute(ddl_sql)
        print("✅ DDL схемы analytics и витрин успешно применен.")
    else:
        print(f"⚠️ Файл схемы {schema_path} не найден.")

    conn.close()
    print("✅ Инициализация таблиц схемы analytics успешно завершена!")
    return True


if __name__ == "__main__":
    init_analytics_database()
