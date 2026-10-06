from db import get_db_connection, init_document_schema

def create_structure():
    conn = get_db_connection()
    init_document_schema(conn)
    conn.close()
    print("PostgreSQL document schema initialized successfully (reports, chunks, tables, sections).")

if __name__ == "__main__":
    create_structure()