try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    psycopg2 = None
    HAS_PSYCOPG2 = False

from dataclasses import dataclass, field
from .config import settings
from .planner import DashboardPlan, ChartPlan


@dataclass
class QueryIntrospectResult:
    is_valid: bool
    columns: list[str] = field(default_factory=list)
    error_message: str | None = None


def get_postgres_connection():
    """Создает соединение с PostgreSQL с поддержкой fallback на шлюз WSL2."""
    if not HAS_PSYCOPG2:
        raise ImportError("psycopg2 is not installed")
    candidates = [settings.postgres_host]
    try:
        import sys
        from pathlib import Path
        root_dir = str(Path(__file__).resolve().parent.parent.parent)
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
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
                port=settings.postgres_port,
                dbname=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
                connect_timeout=3,
            )
        except Exception as exc:
            last_exc = exc
    raise last_exc


def check_postgres_online() -> bool:
    """Проверяет доступность PostgreSQL."""
    try:
        conn = get_postgres_connection()
        conn.close()
        return True
    except Exception:
        return False


def check_postgres_has_data() -> bool:
    """Проверяет, наполнены ли аналитические таблицы витрин данными."""
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM analytics.stipend_fund;")
        cnt = cursor.fetchone()[0]
        conn.close()
        return cnt > 0
    except Exception:
        return False


def introspect_sql(sql: str, row_limit: int = 1) -> QueryIntrospectResult:
    """
    Выполняет запрос с LIMIT 1 в PostgreSQL для проверки синтаксиса и извлечения фактических колонок.
    """
    if not HAS_PSYCOPG2:
        # Если psycopg2 еще не установлен в окружении, пропускаем проверку БД
        return QueryIntrospectResult(is_valid=True)

    # Оборачиваем запрос в подзапрос для безопасного ограничения строк
    wrapped_sql = f"SELECT * FROM ({sql.rstrip(';')}) AS __subquery LIMIT {row_limit}"

    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        cursor.execute(wrapped_sql)
        colnames = [desc[0].lower() for desc in cursor.description] if cursor.description else []
        conn.close()
        return QueryIntrospectResult(is_valid=True, columns=colnames)
    except Exception as exc:
        err_msg = str(exc)
        # Если это ошибка соединения с БД (хост не отвечает)
        if "connection" in err_msg.lower() or "could not connect" in err_msg.lower():
            return QueryIntrospectResult(is_valid=False, error_message=f"PostgreSQL connection error: {exc}")
        return QueryIntrospectResult(is_valid=False, error_message=err_msg)


def introspect_and_validate_plan(plan: DashboardPlan, skip_db_check: bool = False) -> list[str]:
    """
    Проверяет все чарты плана:
    - Выполняет запрос в PostgreSQL (если не skip_db_check).
    - Проверяет соответствие колонок из плана и фактических колонок из запроса.
    """
    errors: list[str] = []

    for i, chart in enumerate(plan.charts, 1):
        if skip_db_check:
            continue

        res = introspect_sql(chart.sql)
        if not res.is_valid:
            # Если это ошибка соединения с БД (например, docker не запущен)
            if "PostgreSQL connection error" in (res.error_message or ""):
                # Мягкое предупреждение
                continue
            errors.append(f"График {i} ('{chart.title}'): ошибка выполнения SQL в БД: {res.error_message}")
            continue

        actual_cols = set(res.columns)
        # Обновляем список колонок чарта фактическими
        if not chart.columns or set(c.lower() for c in chart.columns) != actual_cols:
            chart.columns = res.columns

        # Проверка metric_column
        if chart.metric_column and chart.metric_column.lower() not in actual_cols:
            errors.append(
                f"График {i} ('{chart.title}'): колонка метрики '{chart.metric_column}' "
                f"отсутствует в результате запроса (доступны: {list(actual_cols)})"
            )

        # Проверка groupby
        for grp in chart.groupby:
            if grp.lower() not in actual_cols:
                errors.append(
                    f"График {i} ('{chart.title}'): колонка группировки '{grp}' "
                    f"отсутствует в результате запроса (доступны: {list(actual_cols)})"
                )

        # Проверка x_axis
        if chart.x_axis and chart.x_axis.lower() not in actual_cols:
            errors.append(
                f"График {i} ('{chart.title}'): колонка оси X '{chart.x_axis}' "
                f"отсутствует в результате запроса (доступны: {list(actual_cols)})"
            )

    return errors
