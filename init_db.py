import sqlite3
from docling_parser import _ensure_schema

def create_structure():
    conn = sqlite3.connect("reports.db")
    cursor = conn.cursor()
    _ensure_schema(cursor)
    conn.commit()
    conn.close()
    print("Database initialized successfully with all tables (reports, chunks, tables, sections).")

if __name__ == "__main__":
    create_structure()