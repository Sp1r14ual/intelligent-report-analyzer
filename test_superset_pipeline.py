"""
Модульный тест компонентов генерации дашбордов Superset.
Проверяет:
1. Валидатор SQL Guard (whitelist, блокировка DDL/DML/PII)
2. Семантический компилятор (детерминированная сборка планов)
3. Генератор ZIP-бандлов Apache Superset (валидность архива и YAML-файлов)
"""

import io
import sys
import zipfile
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from dashboard_generator.core.sql_guard import validate_select_sql
from dashboard_generator.core.domain_intents import compile_known_intent_plan
from dashboard_generator.core.superset_bundle import build_superset_bundle_zip, deterministic_uuid


def test_sql_guard():
    print("--- 1. Тестирование SQL Guard ---")

    # Корректный запрос
    good_sql = "SELECT faculty_code, total_students FROM analytics.v_faculty_totals WHERE total_students > 1000 ORDER BY total_students DESC"
    res = validate_select_sql(good_sql)
    assert res.is_valid, f"Ожидался валидный запрос, но получены ошибки: {res.errors}"
    print("  ✅ Корректный SELECT к analytics.* одобрен.")

    # Запрещенная команда DROP
    bad_drop = "DROP TABLE analytics.students_faculty_form"
    res_drop = validate_select_sql(bad_drop)
    assert not res_drop.is_valid, "Ожидалась блокировка DROP TABLE!"
    print(f"  ✅ DROP TABLE успешно заблокирован ({res_drop.errors[0]}).")

    # Запрещенная команда INSERT
    bad_insert = "INSERT INTO analytics.students_faculty_form VALUES ('ФПМИ', 'ПМИ', 'Очная', 100, 2025)"
    res_ins = validate_select_sql(bad_insert)
    assert not res_ins.is_valid, "Ожидалась блокировка INSERT!"
    print(f"  ✅ INSERT успешно заблокирован.")

    # Запрет персональных данных (fio)
    bad_pii = "SELECT fio, passport FROM analytics.v_students_by_faculty_form"
    res_pii = validate_select_sql(bad_pii)
    assert not res_pii.is_valid, "Ожидалась блокировка персональных данных!"
    print(f"  ✅ Персональные данные (fio/passport) успешно заблокированы.")

    # Запрет обращений к неразрешенным таблицам
    bad_table = "SELECT * FROM public.student JOIN secret.admin_keys ON 1=1"
    res_tbl = validate_select_sql(bad_table)
    assert not res_tbl.is_valid, "Ожидалась блокировка неразрешенных схем/таблиц!"
    print(f"  ✅ Неразрешенные схемы/таблицы успешно заблокированы.")


def test_domain_compiler():
    print("\n--- 2. Тестирование семантического компилятора ---")

    queries = [
        "Построй дашборд по распределению студентов по факультетам и формам обучения",
        "Построй аналитический дашборд финансирования НИОКР по источникам поступлений",
        "Покажи динамику научных публикаций по базам Scopus, ВАК и РИНЦ",
        "Сравни показатели факультетов по лабораториям и статьям",
    ]

    for q in queries:
        plan = compile_known_intent_plan(q)
        assert plan is not None, f"Семантический компилятор не распознал запрос: {q}"
        assert len(plan.charts) >= 2, f"В плане должно быть не менее 2 чартов: {plan.charts}"
        print(f"  ✅ Запрос «{q[:40]}...» -> План: «{plan.dashboard_title}» ({len(plan.charts)} чартов)")

        # Проверяем все чарты плана через SQL Guard
        for c in plan.charts:
            val = validate_select_sql(c.sql)
            assert val.is_valid, f"Сгенерированный компилятором SQL не прошел Guard: {c.sql}, ошибки: {val.errors}"


def test_bundle_generation():
    print("\n--- 3. Тестирование генератора ZIP-бандлов Apache Superset ---")

    plan = compile_known_intent_plan("Построй дашборд по распределению студентов по факультетам")
    bundle_bytes = build_superset_bundle_zip(plan)

    assert len(bundle_bytes) > 500, f"Бандл слишком мал ({len(bundle_bytes)} байт)"

    # Распаковываем и проверяем структуру ZIP
    zf = zipfile.ZipFile(io.BytesIO(bundle_bytes))
    file_list = zf.namelist()
    print(f"  📦 Содержимое ZIP-архива ({len(file_list)} файлов):")
    for fname in file_list:
        print(f"     - {fname}")

    meta_file = [f for f in file_list if f.endswith("metadata.yaml")]
    assert len(meta_file) == 1, "Отсутствует metadata.yaml"
    db_file = [f for f in file_list if f.endswith("databases/PostgreSQL.yaml")]
    assert len(db_file) == 1, "Отсутствует databases/PostgreSQL.yaml"
    
    # Проверка YAML валидности
    meta_parsed = yaml.safe_load(zf.read(meta_file[0]))
    assert meta_parsed.get("version") == "1.0.0", "Неверная версия в metadata.yaml"
    assert meta_parsed.get("type") == "assets", "Неверный type в metadata.yaml"

    db_parsed = yaml.safe_load(zf.read(db_file[0]))
    assert db_parsed.get("database_name") == "PostgreSQL"
    assert "analytics_db" in db_parsed.get("sqlalchemy_uri", "")

    # Проверка дашборда
    dash_files = [f for f in file_list if "/dashboards/" in f]
    assert len(dash_files) == 1, "Должен быть ровно один YAML дашборда"
    dash_parsed = yaml.safe_load(zf.read(dash_files[0]))
    assert "position" in dash_parsed
    assert dash_parsed.get("published") is True

    print("  ✅ Все YAML-файлы и структура бандла полностью соответствуют спецификации Superset 3.1+!")



if __name__ == "__main__":
    print("=" * 60)
    print("  ЗАПУСК ТЕСТОВ КОМПОНЕНТОВ SUPERSET GENERATOR")
    print("=" * 60)
    test_sql_guard()
    test_domain_compiler()
    test_bundle_generation()
    print("\n" + "=" * 60)
    print("  🎉 ВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!")
    print("=" * 60)
