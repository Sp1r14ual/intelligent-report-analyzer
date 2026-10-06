import os
import sys
import shutil
import sqlite3
import psycopg2
from pathlib import Path

# Добавляем родительский каталог в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import get_db_connection, init_document_schema


def migrate():
    sqlite_path = "reports.db"
    if not os.path.exists(sqlite_path):
        print(f"[WARN] Файл {sqlite_path} не найден. Миграция данных пропущена.")
        print("[INFO] Инициализация схемы документов в PostgreSQL...")
        init_document_schema()
        print("[OK] Схема документов в PostgreSQL готова.")
        return

    print("==================================================")
    print("  Миграция базы данных reports.db -> PostgreSQL   ")
    print("==================================================")

    # 1. Создание резервной копии reports.db
    backup_path = "reports.db.bak"
    shutil.copy2(sqlite_path, backup_path)
    print(f"✅ Создана резервная копия: {backup_path}")

    # 2. Подключение к SQLite
    sq_conn = sqlite3.connect(sqlite_path)
    sq_cur = sq_conn.cursor()

    # 3. Подключение к PostgreSQL и создание схемы
    pg_conn = get_db_connection()
    init_document_schema(pg_conn)
    pg_cur = pg_conn.cursor()

    try:
        # 4. Миграция reports
        sq_cur.execute("SELECT id, filename, report_year, upload_date FROM reports ORDER BY id")
        reports = sq_cur.fetchall()
        print(f"-> Перенос reports ({len(reports)} записей)...")
        for r_id, fn, yr, up_date in reports:
            pg_cur.execute(
                """
                INSERT INTO reports (id, filename, report_year, upload_date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    filename = EXCLUDED.filename,
                    report_year = EXCLUDED.report_year,
                    upload_date = EXCLUDED.upload_date
                """,
                (r_id, fn, yr, up_date),
            )

        # 5. Миграция document_chunks
        sq_cur.execute("SELECT id, report_id, chunk_order, chunk_text, has_tables, embedding FROM document_chunks ORDER BY id")
        chunks = sq_cur.fetchall()
        print(f"-> Перенос document_chunks ({len(chunks)} записей)...")
        for c_id, r_id, order, text, has_tbl, emb in chunks:
            emb_bytes = psycopg2.Binary(emb) if emb is not None else None
            pg_cur.execute(
                """
                INSERT INTO document_chunks (id, report_id, chunk_order, chunk_text, has_tables, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    report_id = EXCLUDED.report_id,
                    chunk_order = EXCLUDED.chunk_order,
                    chunk_text = EXCLUDED.chunk_text,
                    has_tables = EXCLUDED.has_tables,
                    embedding = EXCLUDED.embedding
                """,
                (c_id, r_id, order, text, has_tbl, emb_bytes),
            )

        # 6. Миграция document_tables
        sq_cur.execute("SELECT id, report_id, chunk_order, table_text, embedding FROM document_tables ORDER BY id")
        tables = sq_cur.fetchall()
        print(f"-> Перенос document_tables ({len(tables)} записей)...")
        for t_id, r_id, order, text, emb in tables:
            emb_bytes = psycopg2.Binary(emb) if emb is not None else None
            pg_cur.execute(
                """
                INSERT INTO document_tables (id, report_id, chunk_order, table_text, embedding)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    report_id = EXCLUDED.report_id,
                    chunk_order = EXCLUDED.chunk_order,
                    table_text = EXCLUDED.table_text,
                    embedding = EXCLUDED.embedding
                """,
                (t_id, r_id, order, text, emb_bytes),
            )

        # 7. Миграция sections
        sq_cur.execute("SELECT id, report_id, section_number, section_title, chunk_order FROM sections ORDER BY id")
        sections = sq_cur.fetchall()
        print(f"-> Перенос sections ({len(sections)} записей)...")
        for s_id, r_id, s_num, s_title, order in sections:
            pg_cur.execute(
                """
                INSERT INTO sections (id, report_id, section_number, section_title, chunk_order)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    report_id = EXCLUDED.report_id,
                    section_number = EXCLUDED.section_number,
                    section_title = EXCLUDED.section_title,
                    chunk_order = EXCLUDED.chunk_order
                """,
                (s_id, r_id, s_num, s_title, order),
            )

        # 8. Синхронизация последовательностей ID (SERIAL sequences)
        for tbl in ["reports", "document_chunks", "document_tables", "sections"]:
            pg_cur.execute(f"SELECT COALESCE(MAX(id), 0) FROM {tbl}")
            max_id = pg_cur.fetchone()[0]
            if max_id > 0:
                pg_cur.execute(f"SELECT setval('{tbl}_id_seq', %s)", (max_id,))
                print(f"-> Последовательность {tbl}_id_seq установлена на {max_id}.")

        pg_conn.commit()
        print("==================================================")
        print("🎉 МИГРАЦИЯ УСПЕШНО ЗАВЕРШЕНА!")
        print(f"   • Перенесено отчетов (reports): {len(reports)}")
        print(f"   • Перенесено чанков (document_chunks): {len(chunks)}")
        print(f"   • Перенесено таблиц (document_tables): {len(tables)}")
        print(f"   • Перенесено разделов (sections): {len(sections)}")
        print("==================================================")

    except Exception as exc:
        pg_conn.rollback()
        print(f"❌ Ошибка миграции: {exc}")
        raise exc
    finally:
        sq_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    migrate()
