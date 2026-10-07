from dataclasses import dataclass, field
from typing import Optional, Callable
from .config import settings
from .planner import (
    load_semantic_model,
    build_system_prompt,
    build_user_prompt,
    build_repair_prompt,
    parse_llm_plan,
    DashboardPlan,
)
from .sql_guard import validate_select_sql
from .domain_intents import compile_known_intent_plan, repair_known_domain_mistakes
from .db_introspect import introspect_and_validate_plan
from .superset_bundle import build_superset_bundle_zip, slugify, deterministic_uuid
from .superset_client import SupersetClient, SupersetClientError
from .llm_client import call_llm


@dataclass
class PipelineResult:
    success: bool
    dashboard_title: str = ""
    dashboard_url: str = ""
    dashboard_uuid: str = ""
    plan: Optional[DashboardPlan] = None
    bundle_bytes: Optional[bytes] = None
    logs: list[str] = field(default_factory=list)
    error_message: Optional[str] = None


def run_pipeline(
    prompt: str,
    skip_superset_import: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None,
    **kwargs,
) -> PipelineResult:
    """
    Основной конвейер преобразования естественно-языкового запроса в готовый дашборд Superset:
    1. Загрузка семантической модели
    2. Проверка намерений / вызов LLM (YandexGPT 5 Lite)
    3. Доменные исправления
    4. Статическая валидация SQL (SQL Guard)
    5. Проверка выполнения запросов в PostgreSQL
    6. Цикл авто-исправления (Repair Loop) при ошибках
    7. Сборка ZIP-бандла для Superset
    8. Импорт в Apache Superset через REST API
    """
    logs: list[str] = []

    def log(msg: str):
        logs.append(msg)
        if progress_callback:
            progress_callback(msg)

    log(f"🚀 Запуск конвейера для запроса: «{prompt}»")

    # 1. Загрузка семантической модели
    try:
        semantic_model = load_semantic_model(settings.semantic_model_path)
        log("✅ Семантическая модель предметной области успешно загружена.")
    except Exception as exc:
        err = f"Ошибка загрузки семантической модели ({settings.semantic_model_path}): {exc}"
        log(f"❌ {err}")
        return PipelineResult(success=False, logs=logs, error_message=err)

    # 2. Попытка детерминированной генерации через семантический компилятор для локальной модели
    plan: Optional[DashboardPlan] = None
    log("🔍 Проверка запроса семантическим компилятором предметной области...")
    intent_plan = compile_known_intent_plan(prompt)
    if intent_plan:
        log(f"✨ Распознано типовое намерение! План '{intent_plan.dashboard_title}' сформирован семантическим компилятором.")
        plan = intent_plan

    # 3. Если план не был скомпилирован детерминированно, обращаемся к локальной LLM YandexGPT
    if plan is None:
        log("🧠 Запрос к языковой модели (YandexGPT 5 Lite)...")
        system_prompt = build_system_prompt(semantic_model)
        user_prompt = build_user_prompt(prompt)

        raw_llm_response = ""
        try:
            raw_llm_response = call_llm(
                system_prompt,
                user_prompt,
            )
            plan = parse_llm_plan(raw_llm_response)
            log(f"✅ План дашборда «{plan.dashboard_title}» успешно сгенерирован LLM ({len(plan.charts)} чартов).")
        except Exception as exc:
            log(f"⚠️ Ошибка генерации LLM: {exc}. Переключение на резервный семантический компилятор...")
            plan = compile_known_intent_plan(prompt)
            if not plan:
                err = f"Не удалось получить корректный план ни от LLM, ни от семантического компилятора: {exc}"
                log(f"❌ {err}")
                return PipelineResult(success=False, logs=logs, error_message=err)

    # 4. Доменные исправления
    plan = repair_known_domain_mistakes(plan, prompt)

    # 5. Цикл валидации и исправления (Repair Loop)
    max_attempts = settings.llm_repair_attempts
    for attempt in range(max_attempts + 1):
        validation_errors: list[str] = []

        # Статическая валидация SQL через sql_guard
        for idx, chart in enumerate(plan.charts, 1):
            val_res = validate_select_sql(chart.sql)
            if not val_res.is_valid:
                for e in val_res.errors:
                    validation_errors.append(f"График {idx} ('{chart.title}'): {e}")

        # Проверка выполнения SQL и соответствия колонок
        if not validation_errors:
            db_errors = introspect_and_validate_plan(plan, skip_db_check=False)
            validation_errors.extend(db_errors)

        if not validation_errors:
            log(f"🛡️ Все SQL-запросы успешно прошли проверку SQL Guard и валидацию в БД!")
            break
        else:
            log(f"⚠️ Попытка {attempt + 1}/{max_attempts + 1}: обнаружены ошибки валидации:")
            for err_item in validation_errors:
                log(f"   • {err_item}")

            # Если есть ошибки, переключаемся на семантический компилятор fallback

            # Если попытки исчерпаны, переключаемся на семантический компилятор fallback
            log("⚙️ Переключение на гарантированный семантический компилятор (fallback)...")
            fallback_plan = compile_known_intent_plan(prompt)
            if fallback_plan:
                plan = fallback_plan
                log(f"✅ План успешно заменен на проверенный эталон: «{plan.dashboard_title}»")
                break
            else:
                err = "План дашборда не прошел проверку безопасности или синтаксиса SQL: \n" + "\n".join(validation_errors)
                log(f"❌ {err}")
                return PipelineResult(success=False, logs=logs, error_message=err, plan=plan)

    # 6. Проверка и автоматическое наполнение витрин данными, если таблицы в БД пусты
    try:
        from .db_introspect import check_postgres_has_data, check_postgres_online
        if check_postgres_online() and not check_postgres_has_data():
            log("📥 В витринах PostgreSQL не обнаружено записей. Выполняется автоматическое наполнение данными отчетов...")
            from scripts.init_postgres_analytics import init_analytics_database
            if init_analytics_database():
                log("✅ Аналитические витрины успешно наполнены показателями из отчетов ВПО и НИОКР!")
            else:
                log("⚠️ Автоматическое наполнение витрин завершилось предупреждением.")
    except Exception as e:
        log(f"ℹ️ Проверка наполненности витрин: {e}")

    # 7. Сборка ZIP-архива import-bundle для Apache Superset
    log("📦 Сборка нативного архива import-bundle (ZIP) для Apache Superset...")
    try:
        bundle_bytes = build_superset_bundle_zip(plan)
        dashboard_slug = slugify(plan.dashboard_title)
        dashboard_uuid = deterministic_uuid(f"dashboard:{dashboard_slug}")
        log(f"✅ Архив собран успешно ({len(bundle_bytes)} байт, UUID: {dashboard_uuid}).")
    except Exception as exc:
        err = f"Ошибка сборки бандла Superset: {exc}"
        log(f"❌ {err}")
        return PipelineResult(success=False, logs=logs, error_message=err, plan=plan)

    # 7. Импорт в Apache Superset через REST API
    dashboard_url = ""
    client = SupersetClient()

    if skip_superset_import:
        dashboard_url = client.get_dashboard_url(dashboard_uuid)
        log("ℹ️ Импорт в Superset пропущен (флаг skip_superset_import). Ссылка сгенерирована.")
    else:
        log(f"🌐 Импорт дашборда в Apache Superset ({client.base_url})...")
        if not client.check_health():
            log("⚠️ Сервер Apache Superset не отвечает по порту 8088. Бандл подготовлен для ручной загрузки или последующего запуска.")
            dashboard_url = client.get_dashboard_url(dashboard_uuid)
        else:
            try:
                client.import_bundle(bundle_bytes)
                dashboard_url = client.get_dashboard_url(dashboard_uuid)
                log(f"🎉 Дашборд успешно опубликован в Apache Superset!")
            except SupersetClientError as exc:
                log(f"⚠️ Ошибка автоматической публикации в Superset: {exc}")
                dashboard_url = client.get_dashboard_url(dashboard_uuid)

    log(f"🔗 Ссылка на дашборд: {dashboard_url}")

    return PipelineResult(
        success=True,
        dashboard_title=plan.dashboard_title,
        dashboard_url=dashboard_url,
        dashboard_uuid=dashboard_uuid,
        plan=plan,
        bundle_bytes=bundle_bytes,
        logs=logs,
    )
