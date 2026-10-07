import os
import psycopg2
from psycopg2.extras import execute_values
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_wsl_host_ip() -> Optional[str]:
    """Определяет IP-адрес хоста Windows при запуске кода внутри WSL2."""
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


def get_db_connection():
    """Создает соединение с базой данных PostgreSQL (analytics_db)
    с автоматическим fallback на IP хоста Windows при работе в WSL2."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    dbname = os.getenv("POSTGRES_DB", "analytics_db")
    user = os.getenv("POSTGRES_USER", "superset")
    password = os.getenv("POSTGRES_PASSWORD", "superset")

    candidates = [host]
    wsl_ip = get_wsl_host_ip()
    if wsl_ip and wsl_ip not in candidates:
        candidates.append(wsl_ip)

    last_error = None
    for candidate_host in candidates:
        try:
            conn = psycopg2.connect(
                host=candidate_host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
                connect_timeout=4,
            )
            return conn
        except Exception as exc:
            last_error = exc

    raise ConnectionError(
        f"Не удалось подключиться к PostgreSQL по адресам {candidates}:{port} (БД: {dbname}): {last_error}. "
        "Убедитесь, что контейнеры запущены (docker compose -f docker-compose.superset.yml up -d)."
    )


def init_document_schema(conn=None):
    """Создает таблицы для хранения документов, чанков, таблиц и разделов в PostgreSQL."""
    close_after = False
    if conn is None:
        conn = get_db_connection()
        close_after = True

    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id          SERIAL PRIMARY KEY,
                filename    TEXT NOT NULL,
                report_year INTEGER,
                upload_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS document_chunks (
                id          SERIAL PRIMARY KEY,
                report_id   INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                chunk_order INTEGER NOT NULL,
                chunk_text  TEXT NOT NULL,
                has_tables  INTEGER DEFAULT 0,
                embedding   BYTEA
            );

            CREATE TABLE IF NOT EXISTS document_tables (
                id          SERIAL PRIMARY KEY,
                report_id   INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                chunk_order INTEGER NOT NULL,
                table_text  TEXT NOT NULL,
                embedding   BYTEA
            );

            CREATE TABLE IF NOT EXISTS sections (
                id              SERIAL PRIMARY KEY,
                report_id       INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                section_number  TEXT,
                section_title   TEXT,
                chunk_order     INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_document_chunks_report ON document_chunks(report_id, chunk_order);
            CREATE INDEX IF NOT EXISTS idx_document_tables_report ON document_tables(report_id, chunk_order);
            CREATE INDEX IF NOT EXISTS idx_sections_report ON sections(report_id);
        """)
        conn.commit()

    if close_after:
        conn.close()
