import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_db_connection

def inspect():
    conn = get_db_connection()
    cur = conn.cursor()
    tables = [
        "students_faculty_form", "students_education_level", "stipend_fund",
        "teaching_staff", "rnd_funding_sources", "publications_dynamics",
        "intellectual_property", "faculty_labs"
    ]
    print("--- Analytics tables row counts ---")
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM analytics.{t}")
        print(f"analytics.{t}: {cur.fetchone()[0]}")
    
    print("\n--- Document tables row counts ---")
    for dt in ["reports", "document_chunks", "document_tables", "sections"]:
        cur.execute(f"SELECT COUNT(*) FROM {dt}")
        print(f"{dt}: {cur.fetchone()[0]}")
    conn.close()

if __name__ == "__main__":
    inspect()
