"""
Скрипт инициализации аналитических витрин PostgreSQL и наполнения данными из отчетов ВПО и НИОКР.
Может запускаться как локально, так и внутри контейнеров.
"""

import os
import sys
import psycopg2
from psycopg2.extras import execute_values

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

    # 2. Очистка существующих данных перед заполнением (идемпотентность)
    cursor.execute("""
        TRUNCATE TABLE 
            analytics.students_faculty_form,
            analytics.students_education_level,
            analytics.stipend_fund,
            analytics.teaching_staff,
            analytics.rnd_funding_sources,
            analytics.publications_dynamics,
            analytics.intellectual_property,
            analytics.faculty_labs
        RESTART IDENTITY CASCADE;
    """)

    # 3. Данные: студенты по факультетам и формам обучения (Таблица 2 отчета ВПО)
    students_data = [
        ('ФПМИ', 'Прикладная математика и информатика', 'Очная форма', 1450, 2025),
        ('ФПМИ', 'Прикладная математика и информатика', 'Заочная форма', 120, 2025),
        ('ФПМИ', 'Прикладная математика и информатика', 'Очно-заочная', 80, 2025),
        ('АВТФ', 'Автоматика и вычислительная техника', 'Очная форма', 1820, 2025),
        ('АВТФ', 'Автоматика и вычислительная техника', 'Заочная форма', 250, 2025),
        ('АВТФ', 'Автоматика и вычислительная техника', 'Очно-заочная', 110, 2025),
        ('ФЭН', 'Энергетика', 'Очная форма', 1210, 2025),
        ('ФЭН', 'Энергетика', 'Заочная форма', 310, 2025),
        ('ФЭН', 'Энергетика', 'Очно-заочная', 60, 2025),
        ('РЭФ', 'Радиотехника и электроника', 'Очная форма', 980, 2025),
        ('РЭФ', 'Радиотехника и электроника', 'Заочная форма', 190, 2025),
        ('РЭФ', 'Радиотехника и электроника', 'Очно-заочная', 40, 2025),
        ('ФЛА', 'Летательные аппараты', 'Очная форма', 1150, 2025),
        ('ФЛА', 'Летательные аппараты', 'Заочная форма', 140, 2025),
        ('ФЛА', 'Летательные аппараты', 'Очно-заочная', 50, 2025),
    ]
    execute_values(
        cursor,
        "INSERT INTO analytics.students_faculty_form (faculty_code, faculty_name, training_form, student_count, year) VALUES %s",
        students_data,
    )

    # 4. Данные: уровни образования (Таблица 1 отчета ВПО)
    levels_data = [
        ('Бакалавриат', 7420, 7850, 5.8),
        ('Специалитет', 1850, 1790, -3.2),
        ('Магистратура', 2100, 2450, 16.7),
        ('Аспирантура', 430, 480, 11.6),
    ]
    execute_values(
        cursor,
        "INSERT INTO analytics.students_education_level (education_level, students_2024, students_2025, growth_pct) VALUES %s",
        levels_data,
    )

    # 5. Данные: стипендии (Таблица 3 отчета ВПО)
    stipend_data = [
        ('Государственная академическая стипендия', 142.5, 158.0, 51.3),
        ('Государственная социальная стипендия', 48.0, 54.2, 17.6),
        ('Повышенная академическая стипендия (ПГАС)', 36.5, 42.8, 13.9),
        ('Стипендии Президента и Правительства РФ', 12.0, 14.5, 4.7),
        ('Материальная помощь студентам', 35.0, 38.5, 12.5),
    ]
    execute_values(
        cursor,
        "INSERT INTO analytics.stipend_fund (stipend_type, amount_2024_mln, amount_2025_mln, share_2025_pct) VALUES %s",
        stipend_data,
    )

    # 6. Данные: ППС (Таблица 4 отчета ВПО)
    staff_data = [
        ('Профессора, доктора наук', 145, 28, 173, 2025),
        ('Доценты, кандидаты наук', 520, 65, 585, 2025),
        ('Старшие преподаватели без степени', 180, 35, 215, 2025),
        ('Ассистенты и преподаватели', 95, 18, 113, 2025),
    ]
    execute_values(
        cursor,
        "INSERT INTO analytics.teaching_staff (staff_category, full_time_staff, part_time_staff, total_staff, year) VALUES %s",
        staff_data,
    )

    # 7. Данные: НИОКР финансирование (Таблица 1 отчета НИОКР)
    rnd_data = [
        ('Госзадание Минобрнауки РФ', 185.4, 210.6, 32.7),
        ('Гранты РНФ (Российский научный фонд)', 94.2, 118.5, 18.4),
        ('Хоздоговоры с промышленными предприятиями', 198.0, 245.8, 38.2),
        ('Региональные гранты и программы', 26.5, 32.4, 5.0),
        ('Международные научные контракты', 31.0, 36.7, 5.7),
    ]
    execute_values(
        cursor,
        "INSERT INTO analytics.rnd_funding_sources (funding_source, amount_2024_mln, amount_2025_mln, share_2025_pct) VALUES %s",
        rnd_data,
    )

    # 8. Данные: Публикации (Таблица 2 отчета НИОКР)
    pubs_data = [
        ('ВАК', 2023, 190), ('ВАК', 2024, 205), ('ВАК', 2025, 215),
        ('Scopus', 2023, 140), ('Scopus', 2024, 160), ('Scopus', 2025, 175),
        ('Web of Science', 2023, 50), ('Web of Science', 2024, 45), ('Web of Science', 2025, 38),
        ('Монографии', 2023, 25), ('Монографии', 2024, 30), ('Монографии', 2025, 35),
        ('РИНЦ', 2023, 680), ('РИНЦ', 2024, 730), ('РИНЦ', 2025, 790),
    ]
    execute_values(
        cursor,
        "INSERT INTO analytics.publications_dynamics (index_type, year, publication_count) VALUES %s",
        pubs_data,
    )

    # 9. Данные: Интеллектуальная собственность
    ip_data = [
        ('Патенты на изобретения', 2023, 18), ('Патенты на изобретения', 2024, 22), ('Патенты на изобретения', 2025, 26),
        ('Свидетельства на программы для ЭВМ', 2023, 45), ('Свидетельства на программы для ЭВМ', 2024, 58), ('Свидетельства на программы для ЭВМ', 2025, 64),
        ('Базы данных', 2023, 12), ('Базы данных', 2024, 15), ('Базы данных', 2025, 19),
        ('Полезные модели', 2023, 8), ('Полезные модели', 2024, 11), ('Полезные модели', 2025, 14),
    ]
    execute_values(
        cursor,
        "INSERT INTO analytics.intellectual_property (object_type, year, object_count) VALUES %s",
        ip_data,
    )

    # 10. Данные: Научные лаборатории
    labs_data = [
        ('ФПМИ', 'Прикладная математика и информатика', 'Лаборатория искусственного интеллекта и анализа больших данных', 48.5, 24, 14, 2025),
        ('АВТФ', 'Автоматика и вычислительная техника', 'Научно-образовательный центр встраиваемых систем и робототехники', 62.0, 31, 18, 2025),
        ('ФЭН', 'Энергетика', 'Лаборатория интеллектуальных энергетических сетей Smart Grid', 54.2, 19, 11, 2025),
        ('РЭФ', 'Радиотехника и электроника', 'Центр микроэлектроники и квантовых оптических сенсоров', 42.8, 16, 9, 2025),
        ('ФЛА', 'Летательные аппараты', 'Лаборатория аэродинамических исследований и композитных конструкций', 38.3, 14, 8, 2025),
    ]
    execute_values(
        cursor,
        "INSERT INTO analytics.faculty_labs (faculty_code, faculty_name, lab_name, funding_mln, articles_count, young_researchers, year) VALUES %s",
        labs_data,
    )

    conn.close()
    print("✅ Все таблицы схемы analytics успешно заполнены тестовыми данными из отчетов ВПО и НИОКР!")
    return True


if __name__ == "__main__":
    init_analytics_database()
