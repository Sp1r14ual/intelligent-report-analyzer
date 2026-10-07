"""
Скрипт верификации миграции данных и работы компонентов с PostgreSQL.
"""
import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_db_connection
from embedding_manager import bytes_to_vector
import pandas as pd


def verify_migration():
    print("=" * 60)
    print("🔍 ВЕРИФИКАЦИЯ МИГРАЦИИ SQLITE -> POSTGRESQL")
    print("=" * 60)

    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Проверка таблиц RAG в PostgreSQL
    tables = ["reports", "document_chunks", "document_tables", "sections"]
    print("\n1. Проверка таблиц документов в PostgreSQL:")
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cur.fetchone()[0]
        print(f"  - Таблица `{t}`: {cnt} записей")

    # 2. Проверка отчетов
    cur.execute("SELECT id, filename, report_year, upload_date FROM reports ORDER BY id")
    reports = cur.fetchall()
    print("\n2. Список отчетов в PostgreSQL:")
    for r in reports:
        print(f"  - ID: {r[0]} | Файл: {r[1]} | Год: {r[2]} | Дата: {r[3]}")

    # 3. Проверка эмбеддингов
    print("\n3. Проверка бинарных эмбеддингов (BYTEA):")
    cur.execute("SELECT id, report_id, chunk_order, embedding FROM document_chunks WHERE embedding IS NOT NULL LIMIT 1")
    chunk_row = cur.fetchone()
    if chunk_row:
        emb_data = chunk_row[3]
        vec = bytes_to_vector(emb_data)
        print(f"  - Чанк ID={chunk_row[0]}: длина байт={len(emb_data)}, вектор shape={vec.shape}, dtype={vec.dtype}")
        assert vec.shape[0] == 1024, f"Ожидалась размерность 1024, получено {vec.shape[0]}"
        print("  - Вектор эмбеддинга BGE-M3 (1024d) успешно восстановлен из BYTEA!")

    # 4. Проверка document_tables эмбеддингов
    cur.execute("SELECT id, report_id, chunk_order, embedding FROM document_tables WHERE embedding IS NOT NULL LIMIT 1")
    tbl_row = cur.fetchone()
    if tbl_row:
        emb_data = tbl_row[3]
        vec = bytes_to_vector(emb_data)
        print(f"  - Таблица ID={tbl_row[0]}: длина байт={len(emb_data)}, вектор shape={vec.shape}, dtype={vec.dtype}")
        assert vec.shape[0] == 1024, f"Ожидалась размерность 1024, получено {vec.shape[0]}"
        print("  - Вектор эмбеддинга таблицы успешно восстановлен из BYTEA!")

    # 5. Проверка pandas queries с параметрами %s
    print("\n4. Проверка параметризованных запросов pandas:")
    active_ids = [r[0] for r in reports]
    if active_ids:
        placeholders = ','.join(['%s'] * len(active_ids))
        df = pd.read_sql_query(
            f"SELECT filename FROM reports WHERE id IN ({placeholders})",
            conn,
            params=tuple(active_ids),
        )
        print(f"  - pd.read_sql_query вернул {len(df)} записей: {df['filename'].tolist()}")

    conn.close()

    # 6. Проверка app.py init_db_checks
    print("\n5. Проверка функции init_db_checks() из app.py:")
    from app import init_db_checks
    db_ok = init_db_checks()
    print(f"  - init_db_checks() -> {db_ok}")
    assert db_ok is True, "init_db_checks() должен возвращать True!"

    # 7. Проверка TableRetriever загрузки
    print("\n6. Проверка TableRetriever.load():")
    from table_retriever import TableRetriever
    t_retriever = TableRetriever()
    print(f"  - Загружено таблиц в FAISS-индекс: {len(t_retriever.tables)}")
    if t_retriever.index:
        print(f"  - Размерность индекса: {t_retriever.index.d}, всего векторов: {t_retriever.index.ntotal}")

    # 8. Проверка FaissRetriever загрузки
    print("\n7. Проверка FaissRetriever.load_from_db():")
    from retriever import FaissRetriever
    f_retriever = FaissRetriever()
    print(f"  - Загружено чанков в FAISS-индекс: {len(f_retriever.chunk_map)}")
    if f_retriever.index:
        print(f"  - Размерность индекса: {f_retriever.index.d}, всего векторов: {f_retriever.index.ntotal}")

    print("\n" + "=" * 60)
    print("✅ ВСЕ ПРОВЕРКИ УСПЕШНО ПРОЙДЕНЫ! МИГРАЦИЯ ЗАВЕРШЕНА.")
    print("=" * 60)


if __name__ == "__main__":
    verify_migration()
