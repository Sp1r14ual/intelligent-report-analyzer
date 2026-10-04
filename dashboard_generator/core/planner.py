import json
import re
import yaml
from typing import Literal
from pydantic import BaseModel, Field, model_validator


ChartType = Literal["table", "bar", "pie", "line", "big_number"]


class ChartPlan(BaseModel):
    title: str
    viz_type: ChartType = "table"
    sql: str
    description: str | None = None
    columns: list[str] = Field(default_factory=list)
    groupby: list[str] = Field(default_factory=list)
    metric_column: str | None = None
    x_axis: str | None = None
    row_limit: int = 1000
    width: int = 6   # В Superset 12-колоночная сетка (6 = половина ширины, 12 = во всю ширину)
    height: int = 50

    @model_validator(mode="after")
    def validate_chart(self) -> "ChartPlan":
        # Валидация специфических требований типов чартов
        if self.viz_type == "big_number" and not self.metric_column:
            raise ValueError(f"График '{self.title}' типа big_number требует указания metric_column")
        if self.viz_type in {"bar", "pie"} and not self.metric_column:
            raise ValueError(f"График '{self.title}' типа {self.viz_type} требует указания metric_column")
        if self.viz_type == "pie":
            if not self.groupby and self.x_axis:
                self.groupby = [self.x_axis]
            if not self.groupby:
                raise ValueError(f"График '{self.title}' типа pie требует указания groupby")
        if self.viz_type in {"bar", "line"}:
            if not self.x_axis and self.groupby:
                self.x_axis = self.groupby[0]
            if not self.x_axis:
                raise ValueError(f"График '{self.title}' типа {self.viz_type} требует указания x_axis")
            # Предотвращаем дублирование x_axis в groupby (вызывает ошибку Duplicate column labels в Superset)
            if self.x_axis and self.x_axis in self.groupby:
                self.groupby = [g for g in self.groupby if g != self.x_axis]
        return self


class DashboardPlan(BaseModel):
    dashboard_title: str
    description: str | None = None
    charts: list[ChartPlan]


def load_semantic_model(model_path: str) -> dict:
    """Загружает семантическую модель предметной области из YAML-файла."""
    with open(model_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_system_prompt(semantic_model: dict) -> str:
    """Формирует строгий системный промпт для LLM на основе семантической модели."""
    yaml_snippet = yaml.dump(semantic_model, allow_unicode=True, sort_keys=False)

    return f"""Ты — эксперт по бизнес-аналитике и генерации дашбордов для Apache Superset и PostgreSQL.
Твоя задача: по естественно-языковому запросу пользователя составить детальный план аналитического дашборда (DashboardPlan) в строгом формате JSON.

### СЕМАНТИЧЕСКАЯ МОДЕЛЬ ПРЕДМЕТНОЙ ОБЛАСТИ (YAML):
```yaml
{yaml_snippet}
```

### ПРАВИЛА И ОГРАНИЧЕНИЯ (КРИТИЧЕСКИ ВАЖНО):
1. Используй ТОЛЬКО витрины из схемы analytics (например: analytics.v_students_by_faculty_form, analytics.v_faculty_totals, analytics.v_rnd_funding и др.).
2. SQL-запросы должны быть строго SELECT или WITH ... SELECT. Любые INSERT, UPDATE, DROP, ALTER КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНЫ.
3. Никаких персональных данных (ФИО, паспорта, телефоны, email) в отчетах быть не должно.
4. В каждом объекте ChartPlan:
   - "title": человекочитаемое понятное название графика на русском языке;
   - "viz_type": один из ("table", "bar", "pie", "line", "big_number");
   - "sql": готовый, синтаксически валидный SQL-запрос для PostgreSQL;
   - "columns": список всех колонок, которые возвращает данный SQL;
   - "x_axis": колонка по оси X (для line, bar);
   - "groupby": список текстовых измерений (для pie; для bar/line указывать ТОЛЬКО при вторичном разбиении серии, иначе пустой список []); НЕ дублировать x_axis в groupby;
   - "metric_column": название числовой колонки метрики (для bar, pie, big_number, line);
   - "width": 6 (половина ширины дашборда) или 12 (полная ширина);
   - "height": 45-60.
5. Для дашборда обычно достаточно от 2 до 5 разноплановых графиков (например, KPI big_number + bar диаграмма + pie/таблица), чтобы всесторонне осветить вопрос.
6. Вывод должен быть ТОЛЬКО чистым JSON без лишнего текста и без оберток ```json.

### ФОРМАТ ВЫХОДНОГО JSON:
{{
  "dashboard_title": "Название дашборда",
  "description": "Краткое пояснение",
  "charts": [
    {{
      "title": "Общее количество студентов",
      "viz_type": "big_number",
      "sql": "SELECT SUM(total_students) AS total_students FROM analytics.v_faculty_totals",
      "description": "Суммарный контингент",
      "columns": ["total_students"],
      "groupby": [],
      "metric_column": "total_students",
      "x_axis": null,
      "width": 6,
      "height": 30
    }},
    {{
      "title": "Распределение студентов по факультетам",
      "viz_type": "bar",
      "sql": "SELECT faculty_code, total_students FROM analytics.v_faculty_totals ORDER BY total_students DESC",
      "description": "Численность по факультетам",
      "columns": ["faculty_code", "total_students"],
      "groupby": [],
      "metric_column": "total_students",
      "x_axis": "faculty_code",
      "width": 6,
      "height": 50
    }}
  ]
}}
"""


def build_user_prompt(query: str) -> str:
    return f"Запрос пользователя на построение дашборда: «{query}». Сформируй план дашборда в строгом формате JSON."


def build_repair_prompt(current_json: str, errors: list[str]) -> str:
    err_text = "\n".join(f"- {e}" for e in errors)
    return f"""Ранее сгенерированный план дашборда содержит ошибки:
{err_text}

Предыдущий ответ:
{current_json}

Исправь указанные ошибки и верни корректный исправленный JSON объекта DashboardPlan. Никакого постороннего текста, только валидный JSON.
"""


def parse_llm_plan(raw_text: str) -> DashboardPlan:
    """Извлекает и парсит JSON в Pydantic объект DashboardPlan."""
    cleaned = raw_text.strip()
    
    # Удаление markdown блоков ```json ... ```
    if "```" in cleaned:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if m:
            cleaned = m.group(1).strip()
            
    # Если остались начальные/конечные фигурные скобки с мусором вокруг
    brace_start = cleaned.find("{")
    brace_end = cleaned.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        cleaned = cleaned[brace_start : brace_end + 1]

    data = json.loads(cleaned)
    return DashboardPlan.model_validate(data)
