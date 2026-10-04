import os
import re
import json
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field

from .config import settings
from .llm_client import call_llm
from .db_introspect import get_postgres_connection, check_postgres_online


@dataclass
class TableExtractionResult:
    target_table: str
    rows_extracted: int
    rows_inserted: int
    sample_data: list[dict] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ReportExtractionResult:
    report_id: int
    report_filename: str
    report_year: int
    tables_processed: int
    results_by_table: dict[str, TableExtractionResult] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    success: bool = True
    error_message: Optional[str] = None


# Описание целевых схем витрин PostgreSQL для промптов LLM
TARGET_TABLE_SCHEMAS = {
    "analytics.students_faculty_form": {
        "title": "Студенты по факультетам и формам обучения",
        "description": "Численность студентов по факультетам (ФПМИ, АВТФ, ФЭН, РЭФ, ФЛА) и формам (Очная форма, Заочная форма, Очно-заочная)",
        "keywords": ["факультет", "очная форма", "заочная форма", "обучени", "студент"],
        "columns": ["faculty_code", "faculty_name", "training_form", "student_count", "year"],
        "json_example": [
            {
                "faculty_code": "ФПМИ",
                "faculty_name": "Прикладная математика и информатика",
                "training_form": "Очная форма",
                "student_count": 1450,
                "year": 2025
            }
        ],
        "sql_insert": "INSERT INTO analytics.students_faculty_form (faculty_code, faculty_name, training_form, student_count, year) VALUES %s"
    },
    "analytics.students_education_level": {
        "title": "Контингент по уровням образования",
        "description": "Численность по ступеням образования (Бакалавриат, Специалитет, Магистратура, Аспирантура) за 2024 и 2025 годы с процентом прироста",
        "keywords": ["бакалавриат", "специалитет", "магистратур", "аспирантур", "уровен"],
        "columns": ["education_level", "students_2024", "students_2025", "growth_pct"],
        "json_example": [
            {
                "education_level": "Бакалавриат",
                "students_2024": 7420,
                "students_2025": 7850,
                "growth_pct": 5.8
            }
        ],
        "sql_insert": "INSERT INTO analytics.students_education_level (education_level, students_2024, students_2025, growth_pct) VALUES %s"
    },
    "analytics.stipend_fund": {
        "title": "Выплаты стипендиального фонда",
        "description": "Виды стипендий (академическая, социальная, ПГАС, Президента, матпомощь), объемы выплат за 2024 и 2025 годы (млн руб.) и доля в 2025 году (%)",
        "keywords": ["стипенди", "пгас", "матпомощь", "социальн", "выплат"],
        "columns": ["stipend_type", "amount_2024_mln", "amount_2025_mln", "share_2025_pct"],
        "json_example": [
            {
                "stipend_type": "Государственная академическая стипендия",
                "amount_2024_mln": 142.5,
                "amount_2025_mln": 158.0,
                "share_2025_pct": 51.3
            }
        ],
        "sql_insert": "INSERT INTO analytics.stipend_fund (stipend_type, amount_2024_mln, amount_2025_mln, share_2025_pct) VALUES %s"
    },
    "analytics.teaching_staff": {
        "title": "Кадровое обеспечение (ППС)",
        "description": "Штатная численность ППС по категориям (Профессора, Доценты, Старшие преподаватели, Ассистенты), штатные, совместители, всего",
        "keywords": ["ппс", "профессор", "доцент", "преподавател", "кадров", "штатн"],
        "columns": ["staff_category", "full_time_staff", "part_time_staff", "total_staff", "year"],
        "json_example": [
            {
                "staff_category": "Профессора, доктора наук",
                "full_time_staff": 145,
                "part_time_staff": 28,
                "total_staff": 173,
                "year": 2025
            }
        ],
        "sql_insert": "INSERT INTO analytics.teaching_staff (staff_category, full_time_staff, part_time_staff, total_staff, year) VALUES %s"
    },
    "analytics.rnd_funding_sources": {
        "title": "Источники финансирования НИОКР",
        "description": "Источники поступлений на науку (Госзадание, РНФ, хоздоговоры, гранты), объемы 2024 и 2025 гг. (млн руб.) и доля (%)",
        "keywords": ["госзадани", "рнф", "грант", "хоздоговор", "ниокр", "источник финансирован"],
        "columns": ["funding_source", "amount_2024_mln", "amount_2025_mln", "share_2025_pct"],
        "json_example": [
            {
                "funding_source": "Госзадание Минобрнауки РФ",
                "amount_2024_mln": 185.4,
                "amount_2025_mln": 210.6,
                "share_2025_pct": 32.7
            }
        ],
        "sql_insert": "INSERT INTO analytics.rnd_funding_sources (funding_source, amount_2024_mln, amount_2025_mln, share_2025_pct) VALUES %s"
    },
    "analytics.publications_dynamics": {
        "title": "Динамика научных публикаций",
        "description": "Количество публикаций по базам (ВАК, Scopus, Web of Science, Монографии, РИНЦ) и годам (2023, 2024, 2025)",
        "keywords": ["scopus", "web of science", "вак", "ринц", "монографи", "публикац"],
        "columns": ["index_type", "year", "publication_count"],
        "json_example": [
            {
                "index_type": "Scopus",
                "year": 2025,
                "publication_count": 175
            }
        ],
        "sql_insert": "INSERT INTO analytics.publications_dynamics (index_type, year, publication_count) VALUES %s"
    },
    "analytics.intellectual_property": {
        "title": "Интеллектуальная собственность",
        "description": "Объекты интеллектуальной собственности (Патенты, Свидетельства ЭВМ, Базы данных, Полезные модели) по годам и их количество",
        "keywords": ["патент", "эвм", "баз данн", "полезн модел", "интеллектуальн"],
        "columns": ["object_type", "year", "object_count"],
        "json_example": [
            {
                "object_type": "Патенты на изобретения",
                "year": 2025,
                "object_count": 26
            }
        ],
        "sql_insert": "INSERT INTO analytics.intellectual_property (object_type, year, object_count) VALUES %s"
    },
    "analytics.faculty_labs": {
        "title": "Научные лаборатории факультетов",
        "description": "Результативность лабораторий по факультетам (код, название факультета, название лаборатории, финансирование млн руб, статьи, молодые ученые)",
        "keywords": ["лаборатор", "smart grid", "молодые учен", "стать"],
        "columns": ["faculty_code", "faculty_name", "lab_name", "funding_mln", "articles_count", "young_researchers", "year"],
        "json_example": [
            {
                "faculty_code": "ФПМИ",
                "faculty_name": "Прикладная математика и информатика",
                "lab_name": "Лаборатория искусственного интеллекта и анализа больших данных",
                "funding_mln": 48.5,
                "articles_count": 24,
                "young_researchers": 14,
                "year": 2025
            }
        ],
        "sql_insert": "INSERT INTO analytics.faculty_labs (faculty_code, faculty_name, lab_name, funding_mln, articles_count, young_researchers, year) VALUES %s"
    },
}


def clean_number(val: Any) -> float:
    """Очищает строку от пробелов, знаков процентов, букв и преобразует в float."""
    if isinstance(val, (int, float)):
        return float(val)
    if val is None:
        return 0.0
    s = str(val).strip()
    s = s.replace(" ", "").replace("\xa0", "").replace("%", "").replace(",", ".")
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            pass
    return 0.0


def classify_table(markdown_table: str) -> Optional[str]:
    """Определяет, к какой аналитической витрине относится данная Markdown-таблица."""
    lowered = markdown_table.lower()
    best_target = None
    max_score = 0

    for table_name, schema in TARGET_TABLE_SCHEMAS.items():
        score = sum(1 for kw in schema["keywords"] if kw in lowered)
        if score > max_score:
            max_score = score
            best_target = table_name

    if max_score >= 1:
        return best_target
    return None


def fallback_parse_markdown_table(target_table: str, markdown_table: str, default_year: int = 2025) -> list[dict]:
    """Резервный детерминированный парсер Markdown-таблицы, если модель не вернула JSON."""
    lines = [l.strip() for l in markdown_table.splitlines() if l.strip().startswith("|")]
    if len(lines) < 3:
        return []

    data_rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if cells and not all(c == "" for c in cells):
            first_cell = cells[0].lower()
            if "итого" in first_cell or "всего" in first_cell:
                continue
            data_rows.append(cells)

    results = []
    if target_table == "analytics.stipend_fund":
        for r in data_rows:
            if len(r) >= 4:
                results.append({
                    "stipend_type": r[0],
                    "amount_2024_mln": clean_number(r[1]),
                    "amount_2025_mln": clean_number(r[2]),
                    "share_2025_pct": clean_number(r[3]),
                })
    elif target_table == "analytics.students_education_level":
        for r in data_rows:
            if len(r) >= 4:
                results.append({
                    "education_level": r[0],
                    "students_2024": int(clean_number(r[1])),
                    "students_2025": int(clean_number(r[2])),
                    "growth_pct": clean_number(r[3]),
                })
    elif target_table == "analytics.students_faculty_form":
        faculty_map = {
            "фпми": "Прикладная математика и информатика",
            "автф": "Автоматика и вычислительная техника",
            "фэн": "Энергетика",
            "рэф": "Радиотехника и электроника",
            "фла": "Летательные аппараты",
        }
        for r in data_rows:
            if len(r) >= 4:
                fac_code = r[0].upper().strip()
                fac_name = faculty_map.get(fac_code.lower(), fac_code)
                forms = [("Очная форма", r[1]), ("Заочная форма", r[2]), ("Очно-заочная", r[3])]
                for f_name, f_val in forms:
                    results.append({
                        "faculty_code": fac_code,
                        "faculty_name": fac_name,
                        "training_form": f_name,
                        "student_count": int(clean_number(f_val)),
                        "year": default_year,
                    })
    elif target_table == "analytics.teaching_staff":
        for r in data_rows:
            if len(r) >= 4:
                results.append({
                    "staff_category": r[0],
                    "full_time_staff": int(clean_number(r[1])),
                    "part_time_staff": int(clean_number(r[2])),
                    "total_staff": int(clean_number(r[3])),
                    "year": default_year,
                })
    elif target_table == "analytics.rnd_funding_sources":
        for r in data_rows:
            if len(r) >= 4:
                results.append({
                    "funding_source": r[0],
                    "amount_2024_mln": clean_number(r[1]),
                    "amount_2025_mln": clean_number(r[2]),
                    "share_2025_pct": clean_number(r[3]),
                })
    elif target_table == "analytics.publications_dynamics":
        for r in data_rows:
            if len(r) >= 4:
                idx_type = r[0]
                years = [(2023, r[1]), (2024, r[2]), (2025, r[3])]
                for yr, val in years:
                    results.append({
                        "index_type": idx_type,
                        "year": yr,
                        "publication_count": int(clean_number(val)),
                    })
    elif target_table == "analytics.intellectual_property":
        for r in data_rows:
            if len(r) >= 4:
                obj_type = r[0]
                years = [(2023, r[1]), (2024, r[2]), (2025, r[3])]
                for yr, val in years:
                    results.append({
                        "object_type": obj_type,
                        "year": yr,
                        "object_count": int(clean_number(val)),
                    })
    elif target_table == "analytics.faculty_labs":
        faculty_map = {
            "фпми": "Прикладная математика и информатика",
            "автф": "Автоматика и вычислительная техника",
            "фэн": "Энергетика",
            "рэф": "Радиотехника и электроника",
            "фла": "Летательные аппараты",
        }
        for r in data_rows:
            if len(r) >= 5:
                fac = r[0].upper().strip()
                fac_name = faculty_map.get(fac.lower(), r[0])
                results.append({
                    "faculty_code": fac,
                    "faculty_name": fac_name,
                    "lab_name": r[1],
                    "funding_mln": clean_number(r[2]),
                    "articles_count": int(clean_number(r[3])),
                    "young_researchers": int(clean_number(r[4])),
                    "year": default_year,
                })
    return results


def parse_llm_json_array(text: str) -> list[dict]:
    """Надёжно извлекает JSON-массив объектов из ответа модели."""
    cleaned = text.strip()
    if "```" in cleaned:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if m:
            cleaned = m.group(1).strip()

    arr_start = cleaned.find("[")
    arr_end = cleaned.rfind("]")
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        cleaned_arr = cleaned[arr_start : arr_end + 1]
        try:
            res = json.loads(cleaned_arr)
            if isinstance(res, list):
                return res
        except json.JSONDecodeError:
            pass

    obj_start = cleaned.find("{")
    obj_end = cleaned.rfind("}")
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        cleaned_obj = cleaned[obj_start : obj_end + 1]
        try:
            res = json.loads(cleaned_obj)
            if isinstance(res, dict):
                for k in ["records", "data", "rows", "items", "table"]:
                    if k in res and isinstance(res[k], list):
                        return res[k]
        except json.JSONDecodeError:
            pass

    return []


class PDFDataExtractor:
    """Сервис для извлечения данных из Markdown-таблиц отчетов с помощью LLM
    и сохранения в аналитические витрины PostgreSQL."""

    def __init__(self, **kwargs):
        pass

    def extract_from_report(
        self,
        report_id: int,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> ReportExtractionResult:
        """
        Извлекает таблицы отчета из SQLite reports.db, передает их LLM для структурирования
        и наполняет целевые таблицы PostgreSQL analytics.*
        """
        def log(msg: str):
            if progress_callback:
                progress_callback(msg)

        log(f"🔎 Чтение таблиц отчета (ID: {report_id}) из локальной базы данных...")

        conn_sq = sqlite3.connect("reports.db")
        cur_sq = conn_sq.cursor()
        cur_sq.execute("SELECT filename, report_year FROM reports WHERE id = ?", (report_id,))
        rep_row = cur_sq.fetchone()
        if not rep_row:
            conn_sq.close()
            return ReportExtractionResult(
                report_id=report_id,
                report_filename="Unknown",
                report_year=2025,
                tables_processed=0,
                success=False,
                error_message=f"Отчет с ID {report_id} не найден в reports.db",
            )

        filename, year = rep_row
        cur_sq.execute(
            "SELECT id, table_text FROM document_tables WHERE report_id = ? ORDER BY chunk_order ASC",
            (report_id,),
        )
        tables = cur_sq.fetchall()
        conn_sq.close()

        if not tables:
            return ReportExtractionResult(
                report_id=report_id,
                report_filename=filename,
                report_year=year or 2025,
                tables_processed=0,
                success=True,
                logs=["В данном отчете не найдено Markdown-таблиц для извлечения."],
            )

        log(f"📄 Отчет «{filename}»: найдено {len(tables)} таблиц для анализа.")

        try:
            pg_conn = get_postgres_connection()
            pg_conn.autocommit = True
            pg_cur = pg_conn.cursor()
        except Exception as exc:
            return ReportExtractionResult(
                report_id=report_id,
                report_filename=filename,
                report_year=year or 2025,
                tables_processed=len(tables),
                success=False,
                error_message=f"Не удалось подключиться к PostgreSQL: {exc}",
            )

        result_summary: dict[str, TableExtractionResult] = {}
        processed_count = 0

        for tbl_id, tbl_text in tables:
            if not tbl_text or len(tbl_text.strip()) < 20:
                continue

            target_table = classify_table(tbl_text)
            if not target_table:
                continue

            schema = TARGET_TABLE_SCHEMAS[target_table]
            log(f"📊 Анализ таблицы: «{schema['title']}» (целевая витрина: `{target_table}`)...")

            try:
                system_prompt = f"""Ты — специализированный модуль ETL и нормализации данных для базы PostgreSQL.
Твоя задача: преобразовать Markdown-таблицу из отчета образовательной организации в чистый JSON-массив объектов в строгом соответствии со схемой.

ЦЕЛЕВАЯ ТАБЛИЦА: {target_table} ({schema['title']})
ОПИСАНИЕ: {schema['description']}
ТРЕБУЕМЫЕ КОЛОНКИ: {schema['columns']}

ПРАВИЛА ИЗВЛЕЧЕНИЯ:
1. Выведи ТОЛЬКО валидный JSON-массив объектов: [{json.dumps(schema['json_example'][0], ensure_ascii=False)}]
2. Очищай числовые поля: убирай единицы измерения ('млн', 'тыс', 'руб', '%'), знаки сносок (*), пробелы в числах. Разделитель десятичной дроби строго точка.
3. Пропускай итоговые строки ('Итого', 'Всего'), так как они будут суммироваться в дашбордах Superset.
4. Отчетный год: используй {year or 2025}, если год не указан явно в строке.
5. Не добавляй никаких пояснений или комментариев до или после JSON."""

                user_prompt = f"Markdown-таблица из отчета «{filename}»:\n\n{tbl_text}\n\nСформируй JSON-массив объектов для таблицы {target_table}."

                records = []
                try:
                    raw_response = call_llm(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=1500,
                        timeout=60,
                    )
                    records = parse_llm_json_array(raw_response)
                except Exception as llm_err:
                    log(f"ℹ️ Модель не ответила за 60с ({llm_err}). Применение прямого семантического парсера...")

                if not records:
                    log(f"⚙️ Применение семантического парсера структуры таблицы для `{target_table}`...")
                    records = fallback_parse_markdown_table(target_table, tbl_text, year)

                if not records:
                    log(f"⚠️ Не удалось извлечь структурированные строки для {target_table}.")
                    continue

                validated_tuples = []
                sample_dicts = []
                cols = schema["columns"]

                for rec in records:
                    if not isinstance(rec, dict):
                        continue
                    row_tuple = []
                    row_dict = {}

                    for col in cols:
                        val = rec.get(col)
                        if col.endswith("_count") or col in {"full_time_staff", "part_time_staff", "total_staff", "students_2024", "students_2025", "articles_count", "young_researchers"}:
                            num = int(clean_number(val))
                            row_tuple.append(num)
                            row_dict[col] = num
                        elif col.endswith("_mln") or col.endswith("_pct") or col == "growth_pct" or col == "funding_mln":
                            flt = round(clean_number(val), 2)
                            row_tuple.append(flt)
                            row_dict[col] = flt
                        elif col == "year":
                            y = int(clean_number(val)) or (year or 2025)
                            row_tuple.append(y)
                            row_dict[col] = y
                        else:
                            s = str(val or "").strip()
                            row_tuple.append(s)
                            row_dict[col] = s

                    if any(row_tuple):
                        validated_tuples.append(tuple(row_tuple))
                        if len(sample_dicts) < 3:
                            sample_dicts.append(row_dict)

                if validated_tuples:
                    pg_cur.execute(f"TRUNCATE TABLE {target_table} RESTART IDENTITY CASCADE;")
                    execute_values(pg_cur, schema["sql_insert"], validated_tuples)

                    log(f"✅ Успешно записано в `{target_table}`: {len(validated_tuples)} записей.")
                    result_summary[target_table] = TableExtractionResult(
                        target_table=target_table,
                        rows_extracted=len(records),
                        rows_inserted=len(validated_tuples),
                        sample_data=sample_dicts,
                    )
                    processed_count += 1

            except Exception as exc:
                log(f"❌ Ошибка извлечения данных для {target_table}: {exc}")
                result_summary[target_table] = TableExtractionResult(
                    target_table=target_table,
                    rows_extracted=0,
                    rows_inserted=0,
                    error=str(exc),
                )

        pg_conn.close()

        log(f"🎉 Обработка отчета завершена! Обновлено витрин: {len(result_summary)}.")
        return ReportExtractionResult(
            report_id=report_id,
            report_filename=filename,
            report_year=year or 2025,
            tables_processed=processed_count,
            results_by_table=result_summary,
            success=True,
        )
