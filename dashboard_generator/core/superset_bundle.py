import io
import json
import re
import uuid
import zipfile
import yaml
from datetime import datetime, timezone
from typing import Tuple
from .config import settings
from .planner import DashboardPlan, ChartPlan

# Фиксированный базовый namespace UUID для детерминированной генерации сущностей Superset
SUPERSET_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


def slugify(text: str, max_length: int = 80) -> str:
    """Транслитерирует русскоязычные названия в безопасные slug-идентификаторы."""
    text = text.lower()
    res = []
    for char in text:
        if char in CYRILLIC_TO_LATIN:
            res.append(CYRILLIC_TO_LATIN[char])
        elif re.match(r"[a-z0-9]", char):
            res.append(char)
        else:
            res.append("_")
    slug = "".join(res)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return (slug[:max_length] or "item").rstrip("_")


def deterministic_uuid(key: str) -> str:
    """Формирует стабильный UUID v5 на основе ключа."""
    return str(uuid.uuid5(SUPERSET_NAMESPACE, key))


def map_viz_type(plan_viz_type: str) -> Tuple[str, dict]:
    """Маппинг типа визуализации из плана в нативные параметры Superset / ECharts."""
    if plan_viz_type == "big_number":
        return "big_number_total", {
            "viz_type": "big_number_total",
            "subheader": "",
            "y_axis_format": ",d",
        }
    elif plan_viz_type == "pie":
        return "pie", {
            "viz_type": "pie",
            "show_legend": True,
            "legend_orientation": "top",
            "label_type": "key_percent",
            "color_scheme": "supersetColors",
        }
    elif plan_viz_type == "line":
        return "echarts_timeseries_line", {
            "viz_type": "echarts_timeseries_line",
            "show_legend": True,
            "x_axis_time_format": "smart_date",
            "color_scheme": "supersetColors",
        }
    elif plan_viz_type == "bar":
        return "echarts_timeseries_bar", {
            "viz_type": "echarts_timeseries_bar",
            "show_legend": True,
            "color_scheme": "supersetColors",
            "orientation": "vertical",
        }
    else:  # table
        return "table", {
            "viz_type": "table",
            "query_mode": "raw",
            "include_search": True,
            "page_length": 25,
            "show_cell_bars": True,
            "table_timestamp_format": "smart_date",
        }


def build_superset_bundle_zip(plan: DashboardPlan) -> bytes:
    """
    Создает in-memory ZIP-архив import-bundle для Apache Superset 3.x / 4.x.
    Архив содержит:
    - metadata.yaml
    - databases/PostgreSQL.yaml
    - datasets/analytics/<slug>.yaml
    - charts/<slug>.yaml
    - dashboards/<slug>.yaml
    """
    buf = io.BytesIO()
    zip_f = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)

    now_iso = datetime.now(timezone.utc).isoformat()

    dashboard_slug = slugify(plan.dashboard_title)
    root_dir = f"dashboard_export_{dashboard_slug}"

    # 1. metadata.yaml
    metadata_content = {
        "version": "1.0.0",
        "type": "assets",
        "timestamp": now_iso,
    }
    zip_f.writestr(f"{root_dir}/metadata.yaml", yaml.safe_dump(metadata_content, sort_keys=False))

    # 2. databases/PostgreSQL.yaml
    db_uuid = deterministic_uuid("database:PostgreSQL")
    db_content = {
        "database_name": "PostgreSQL",
        "sqlalchemy_uri": settings.postgres_superset_uri,
        "uuid": db_uuid,
        "password": None,
        "cache_timeout": None,
        "expose_in_sqllab": True,
        "allow_run_async": False,
        "allow_ctas": False,
        "allow_cvas": False,
        "allow_dml": False,
        "allow_csv_upload": False,
        "extra": {
            "engine_params": {},
            "metadata_params": {},
            "schemas_allowed_for_csv_upload": [],
        },
        "version": "1.0.0",
    }
    zip_f.writestr(f"{root_dir}/databases/PostgreSQL.yaml", yaml.safe_dump(db_content, sort_keys=False))

    dashboard_uuid = deterministic_uuid(f"dashboard:{dashboard_slug}")

    chart_uuids = []
    chart_info_list = []


    # 3. datasets & charts
    for idx, chart in enumerate(plan.charts, 1):
        chart_slug = f"{dashboard_slug}_chart_{idx}_{slugify(chart.title)}"
        chart_uuid = deterministic_uuid(f"chart:{chart_slug}")
        dataset_uuid = deterministic_uuid(f"dataset:{chart_slug}")
        dataset_slug = f"ds_{chart_slug}"

        # Колонки и метрики датасета
        metrics = [
            {
                "metric_name": "count",
                "verbose_name": "Количество записей",
                "metric_type": "count",
                "expression": "COUNT(*)",
            }
        ]
        if chart.metric_column:
            metrics.append({
                "metric_name": chart.metric_column,
                "verbose_name": chart.metric_column,
                "metric_type": None,
                "expression": f"SUM({chart.metric_column})",
            })

        cols_yaml = []
        for col in chart.columns:
            cols_yaml.append({
                "column_name": col,
                "verbose_name": col,
                "is_dttm": col in {"year", "date", "upload_date"},
                "is_active": True,
                "type": "NUMERIC" if col == chart.metric_column else "VARCHAR",
                "groupby": True,
                "filterable": True,
            })

        dataset_content = {
            "table_name": dataset_slug,
            "main_dttm_col": None,
            "description": chart.description or chart.title,
            "default_endpoint": None,
            "offset": 0,
            "cache_timeout": None,
            "schema": "analytics",
            "sql": chart.sql.rstrip(";"),
            "params": None,
            "template_params": None,
            "filter_select_enabled": True,
            "fetch_values_predicate": None,
            "extra": None,
            "uuid": dataset_uuid,
            "metrics": metrics,
            "columns": cols_yaml,
            "database_uuid": db_uuid,
            "version": "1.0.0",
        }
        zip_f.writestr(f"{root_dir}/datasets/analytics/{dataset_slug}.yaml", yaml.safe_dump(dataset_content, sort_keys=False))

        # Настройки чарта
        superset_viz, extra_viz_params = map_viz_type(chart.viz_type)
        primary_metric = chart.metric_column or "count"

        if chart.viz_type == "table":
            params = {
                "viz_type": "table",
                "datasource": f"{dataset_uuid}__table",
                "slice_id": idx,
                "query_mode": "raw",
                "all_columns": chart.columns,
                "metrics": [],
                "percent_metrics": [],
                "groupby": [],
                "adhoc_filters": [],
                "row_limit": chart.row_limit,
                **extra_viz_params,
            }
        elif chart.viz_type in {"bar", "line"}:
            x_axis = chart.x_axis
            if not x_axis and chart.groupby:
                x_axis = chart.groupby[0]
            elif not x_axis:
                non_metrics = [c for c in chart.columns if c != primary_metric]
                x_axis = non_metrics[0] if non_metrics else chart.columns[0]

            # Исключаем дублирование x_axis и primary_metric в groupby (критично для ECharts в Superset)
            clean_groupby = [
                g for g in chart.groupby
                if g != x_axis and g != primary_metric
            ]

            params = {
                "viz_type": superset_viz,
                "datasource": f"{dataset_uuid}__table",
                "slice_id": idx,
                "x_axis": x_axis,
                "metrics": [primary_metric],
                "metric": primary_metric,
                "groupby": clean_groupby,
                "adhoc_filters": [],
                "row_limit": chart.row_limit,
                **extra_viz_params,
            }
        elif chart.viz_type == "pie":
            clean_groupby = [g for g in chart.groupby if g != primary_metric]
            if not clean_groupby and chart.x_axis and chart.x_axis != primary_metric:
                clean_groupby = [chart.x_axis]
            if not clean_groupby:
                non_metrics = [c for c in chart.columns if c != primary_metric]
                clean_groupby = [non_metrics[0]] if non_metrics else ["count"]

            params = {
                "viz_type": superset_viz,
                "datasource": f"{dataset_uuid}__table",
                "slice_id": idx,
                "metrics": [primary_metric],
                "metric": primary_metric,
                "groupby": clean_groupby,
                "adhoc_filters": [],
                "row_limit": chart.row_limit,
                **extra_viz_params,
            }
        elif chart.viz_type == "big_number":
            params = {
                "viz_type": superset_viz,
                "datasource": f"{dataset_uuid}__table",
                "slice_id": idx,
                "metrics": [primary_metric],
                "metric": primary_metric,
                "groupby": [],
                "adhoc_filters": [],
                "row_limit": chart.row_limit,
                **extra_viz_params,
            }
        else:
            clean_groupby = [g for g in chart.groupby if g != primary_metric]
            params = {
                "viz_type": superset_viz,
                "datasource": f"{dataset_uuid}__table",
                "slice_id": idx,
                "metrics": [primary_metric],
                "metric": primary_metric,
                "groupby": clean_groupby,
                "adhoc_filters": [],
                "row_limit": chart.row_limit,
                **extra_viz_params,
            }

        chart_yaml = {
            "slice_name": chart.title,
            "viz_type": superset_viz,
            "params": params,
            "dataset_uuid": dataset_uuid,
            "uuid": chart_uuid,
            "version": "1.0.0",
        }
        zip_f.writestr(f"{root_dir}/charts/{chart_slug}.yaml", yaml.safe_dump(chart_yaml, sort_keys=False))

        chart_uuids.append(chart_uuid)
        chart_info_list.append({
            "uuid": chart_uuid,
            "title": chart.title,
            "width": chart.width,
            "height": chart.height,
        })

    # 4. dashboards/<dashboard_slug>.yaml (позиционирование сетки Superset v2)
    position = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": []},
    }

    current_row_id = None
    current_row_width = 0
    row_counter = 0

    for idx, c_info in enumerate(chart_info_list, 1):
        chart_elem_id = f"CHART-{idx}"
        w = c_info["width"]
        h = c_info["height"]

        if current_row_id is None or (current_row_width + w > 12):
            row_counter += 1
            current_row_id = f"ROW-{row_counter}"
            position["GRID_ID"]["children"].append(current_row_id)
            position[current_row_id] = {
                "type": "ROW",
                "id": current_row_id,
                "children": [],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            }
            current_row_width = 0

        position[current_row_id]["children"].append(chart_elem_id)
        current_row_width += w

        position[chart_elem_id] = {
            "type": "CHART",
            "id": chart_elem_id,
            "children": [],
            "meta": {
                "chartId": idx,
                "uuid": c_info["uuid"],
                "width": w,
                "height": h,
                "sliceName": c_info["title"],
            },
        }

    dashboard_yaml = {
        "dashboard_title": plan.dashboard_title,
        "description": plan.description or "",
        "css": "",
        "slug": None,
        "certified_by": "",
        "certification_details": "",
        "published": True,
        "uuid": dashboard_uuid,
        "position": position,
        "version": "1.0.0",
    }
    zip_f.writestr(f"{root_dir}/dashboards/{dashboard_slug}.yaml", yaml.safe_dump(dashboard_yaml, sort_keys=False))

    zip_f.close()
    return buf.getvalue()

