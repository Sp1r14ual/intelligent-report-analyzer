import re
from dataclasses import dataclass
from typing import Optional
from .planner import DashboardPlan, ChartPlan


@dataclass
class ParsedIntent:
    intent_type: str   # 'students', 'rnd_funding', 'publications', 'stipends', 'faculty_overview'
    faculty_filter: Optional[str] = None
    year_filter: Optional[int] = None


FACULTY_CODES = ["ФПМИ", "АВТФ", "ФЭН", "РЭФ", "ФЛА"]


def extract_faculty_filter(prompt: str) -> Optional[str]:
    """Извлекает код факультета из текста промпта при наличии."""
    for f in FACULTY_CODES:
        if re.search(rf"\b{re.escape(f)}\b", prompt, flags=re.IGNORECASE):
            return f
    return None


def parse_dashboard_intent(prompt: str) -> Optional[ParsedIntent]:
    """Распознает доменное намерение пользователя по ключевым словам."""
    lowered = prompt.lower()
    fac = extract_faculty_filter(prompt)

    # 1. Студенты и факультеты
    if any(k in lowered for k in ["студент", "контингент", "форм", "обучени", "факультет", "бакалавриат", "магистратур"]):
        if any(k in lowered for k in ["ниокр", "грант", "финансирован", "стать", "лаборатор"]) and not fac:
            # Сводный межфакультетский обзор
            return ParsedIntent(intent_type="faculty_overview", faculty_filter=fac)
        return ParsedIntent(intent_type="students", faculty_filter=fac)

    # 2. Финансирование НИОКР
    if any(k in lowered for k in ["ниокр", "грант", "рнф", "госзадани", "хоздоговор", "источник"]):
        return ParsedIntent(intent_type="rnd_funding", faculty_filter=fac)

    # 3. Научные публикации и наукометрия
    if any(k in lowered for k in ["публикац", "стать", "вак", "scopus", "ринц", "индексац"]):
        return ParsedIntent(intent_type="publications", faculty_filter=fac)

    # 4. Стипендиальный фонд
    if any(k in lowered for k in ["стипенди", "пгас", "матпомощь", "социальн"]):
        return ParsedIntent(intent_type="stipends", faculty_filter=fac)

    # 5. Межфакультетский сравнительный обзор
    if any(k in lowered for k in ["сравн", "обзор", "лаборатор", "молодые учен"]):
        return ParsedIntent(intent_type="faculty_overview", faculty_filter=fac)

    return None


def compile_known_intent_plan(prompt: str) -> Optional[DashboardPlan]:
    """
    Семантический компилятор: детерминированно строит выверенный DashboardPlan
    по распознанному намерению. Используется как надежный fallback для локальных LLM.
    """
    intent = parse_dashboard_intent(prompt)
    if not intent:
        return None

    if intent.intent_type == "students":
        fac_where = f"WHERE faculty_code = '{intent.faculty_filter}'" if intent.faculty_filter else ""
        fac_title = f" ({intent.faculty_filter})" if intent.faculty_filter else ""

        charts = [
            ChartPlan(
                title=f"Общий контингент студентов{fac_title}",
                viz_type="big_number",
                sql=f"SELECT SUM(total_students) AS total_students FROM analytics.v_faculty_totals {fac_where}".strip(),
                description="Суммарная численность обучающихся",
                columns=["total_students"],
                groupby=[],
                metric_column="total_students",
                width=6,
                height=30,
            ),
            ChartPlan(
                title=f"Контингент по уровням образования",
                viz_type="bar",
                sql="SELECT education_level, students_2025 FROM analytics.v_students_by_level ORDER BY students_2025 DESC",
                description="Численность по ступеням высшего образования (2025 г.)",
                columns=["education_level", "students_2025"],
                groupby=["education_level"],
                metric_column="students_2025",
                x_axis="education_level",
                width=6,
                height=45,
            ),
            ChartPlan(
                title=f"Распределение по формам обучения{fac_title}",
                viz_type="pie",
                sql=f"SELECT training_form, SUM(student_count) AS student_count FROM analytics.v_students_by_faculty_form {fac_where} GROUP BY training_form ORDER BY student_count DESC".strip(),
                description="Соотношение очной, заочной и вечерней форм",
                columns=["training_form", "student_count"],
                groupby=["training_form"],
                metric_column="student_count",
                width=6,
                height=50,
            ),
            ChartPlan(
                title="Сводная таблица по факультетам и формам",
                viz_type="table",
                sql="SELECT faculty_code, full_time_count, extramural_count, part_time_count, total_students FROM analytics.v_faculty_totals ORDER BY total_students DESC",
                description="Детальная численность по всем факультетам",
                columns=["faculty_code", "full_time_count", "extramural_count", "part_time_count", "total_students"],
                groupby=["faculty_code"],
                metric_column="total_students",
                width=6,
                height=50,
            ),
        ]
        return DashboardPlan(
            dashboard_title=f"Анализ студенческого контингента{fac_title}",
            description="Дашборд распределения студентов по факультетам, уровням образования и формам обучения.",
            charts=charts,
        )

    elif intent.intent_type == "rnd_funding":
        charts = [
            ChartPlan(
                title="Общий объем финансирования НИОКР (2025 г.)",
                viz_type="big_number",
                sql="SELECT SUM(amount_2025_mln) AS total_rnd_2025 FROM analytics.v_rnd_funding",
                description="Суммарный объем НИОКР (млн руб.)",
                columns=["total_rnd_2025"],
                groupby=[],
                metric_column="total_rnd_2025",
                width=6,
                height=30,
            ),
            ChartPlan(
                title="Структура финансирования НИОКР по источникам (2025 г.)",
                viz_type="pie",
                sql="SELECT funding_source, amount_2025_mln FROM analytics.v_rnd_funding ORDER BY amount_2025_mln DESC",
                description="Доли источников: Госзадание, РНФ, хоздоговоры",
                columns=["funding_source", "amount_2025_mln"],
                groupby=["funding_source"],
                metric_column="amount_2025_mln",
                width=6,
                height=50,
            ),
            ChartPlan(
                title="Сравнение объемов НИОКР (2024 vs 2025)",
                viz_type="bar",
                sql="SELECT funding_source, amount_2025_mln FROM analytics.v_rnd_funding ORDER BY amount_2025_mln DESC",
                description="Объемы финансирования в млн рублей",
                columns=["funding_source", "amount_2025_mln"],
                groupby=["funding_source"],
                metric_column="amount_2025_mln",
                x_axis="funding_source",
                width=6,
                height=50,
            ),
            ChartPlan(
                title="Источники и доли финансирования",
                viz_type="table",
                sql="SELECT funding_source, amount_2024_mln, amount_2025_mln, share_2025_pct FROM analytics.v_rnd_funding ORDER BY amount_2025_mln DESC",
                description="Детальная финансовая сводка",
                columns=["funding_source", "amount_2024_mln", "amount_2025_mln", "share_2025_pct"],
                width=6,
                height=50,
            ),
        ]
        return DashboardPlan(
            dashboard_title="Финансирование научных исследований (НИОКР)",
            description="Дашборд анализа структуры и динамики доходов от научных исследований и грантов.",
            charts=charts,
        )

    elif intent.intent_type == "publications":
        charts = [
            ChartPlan(
                title="Всего публикаций за 2025 год",
                viz_type="big_number",
                sql="SELECT SUM(publication_count) AS total_pubs_2025 FROM analytics.v_publications WHERE year = 2025",
                description="Суммарное количество научных работ в 2025 году",
                columns=["total_pubs_2025"],
                metric_column="total_pubs_2025",
                width=6,
                height=30,
            ),
            ChartPlan(
                title="Публикации по типам индексации (2025 г.)",
                viz_type="bar",
                sql="SELECT index_type, publication_count FROM analytics.v_publications WHERE year = 2025 ORDER BY publication_count DESC",
                description="Количество статей по базам (ВАК, Scopus, Web of Science, РИНЦ)",
                columns=["index_type", "publication_count"],
                groupby=["index_type"],
                metric_column="publication_count",
                x_axis="index_type",
                width=6,
                height=50,
            ),
            ChartPlan(
                title="Динамика публикационной активности по годам",
                viz_type="line",
                sql="SELECT year, SUM(publication_count) AS yearly_pubs FROM analytics.v_publications GROUP BY year ORDER BY year ASC",
                description="Временной ряд публикационной активности 2023–2025 гг.",
                columns=["year", "yearly_pubs"],
                groupby=["year"],
                metric_column="yearly_pubs",
                x_axis="year",
                width=6,
                height=50,
            ),
            ChartPlan(
                title="Сводная таблица публикаций (2023–2025 гг.)",
                viz_type="table",
                sql="SELECT index_type, year, publication_count FROM analytics.v_publications ORDER BY year DESC, publication_count DESC",
                description="Детальные наукометрические показатели",
                columns=["index_type", "year", "publication_count"],
                width=6,
                height=50,
            ),
        ]
        return DashboardPlan(
            dashboard_title="Научные публикации и наукометрия",
            description="Дашборд публикационной активности сотрудников университета по базам цитирования.",
            charts=charts,
        )

    elif intent.intent_type == "stipends":
        charts = [
            ChartPlan(
                title="Объем стипендиального фонда (2025 г.)",
                viz_type="big_number",
                sql="SELECT SUM(amount_2025_mln) AS total_stipend_2025 FROM analytics.v_stipend_fund",
                description="Суммарный объем фонда (млн руб.)",
                columns=["total_stipend_2025"],
                metric_column="total_stipend_2025",
                width=6,
                height=30,
            ),
            ChartPlan(
                title="Структура стипендиального фонда по видам выплат",
                viz_type="pie",
                sql="SELECT stipend_type, amount_2025_mln FROM analytics.v_stipend_fund ORDER BY amount_2025_mln DESC",
                description="Доли видов выплат в 2025 году",
                columns=["stipend_type", "amount_2025_mln"],
                groupby=["stipend_type"],
                metric_column="amount_2025_mln",
                width=6,
                height=50,
            ),
            ChartPlan(
                title="Сравнительная таблица выплат (2024 vs 2025)",
                viz_type="table",
                sql="SELECT stipend_type, amount_2024_mln, amount_2025_mln, share_2025_pct FROM analytics.v_stipend_fund ORDER BY amount_2025_mln DESC",
                description="Выплаты и процентные доли фонда",
                columns=["stipend_type", "amount_2024_mln", "amount_2025_mln", "share_2025_pct"],
                width=12,
                height=45,
            ),
        ]
        return DashboardPlan(
            dashboard_title="Стипендиальное обеспечение и социальные выплаты",
            description="Дашборд анализа структуры стипендиального фонда университета.",
            charts=charts,
        )

    elif intent.intent_type == "faculty_overview":
        charts = [
            ChartPlan(
                title="Студенты по факультетам",
                viz_type="bar",
                sql="SELECT faculty_code, total_students FROM analytics.v_faculty_overview ORDER BY total_students DESC",
                description="Численность контингента обучающихся",
                columns=["faculty_code", "total_students"],
                groupby=["faculty_code"],
                metric_column="total_students",
                x_axis="faculty_code",
                width=6,
                height=50,
            ),
            ChartPlan(
                title="Финансирование лабораторий по факультетам (млн руб.)",
                viz_type="bar",
                sql="SELECT faculty_code, labs_funding_mln FROM analytics.v_faculty_overview ORDER BY labs_funding_mln DESC",
                description="Объем финансирования научных центров",
                columns=["faculty_code", "labs_funding_mln"],
                groupby=["faculty_code"],
                metric_column="labs_funding_mln",
                x_axis="faculty_code",
                width=6,
                height=50,
            ),
            ChartPlan(
                title="Молодые ученые в лабораториях по факультетам",
                viz_type="pie",
                sql="SELECT faculty_code, total_young_researchers FROM analytics.v_faculty_overview WHERE total_young_researchers > 0 ORDER BY total_young_researchers DESC",
                description="Доля молодых ученых",
                columns=["faculty_code", "total_young_researchers"],
                groupby=["faculty_code"],
                metric_column="total_young_researchers",
                width=6,
                height=50,
            ),
            ChartPlan(
                title="Сводная таблица эффективности факультетов",
                viz_type="table",
                sql="SELECT faculty_code, faculty_name, total_students, labs_funding_mln, total_lab_articles, total_young_researchers FROM analytics.v_faculty_overview ORDER BY total_students DESC",
                description="Комплексный межфакультетский обзор показателей",
                columns=["faculty_code", "faculty_name", "total_students", "labs_funding_mln", "total_lab_articles", "total_young_researchers"],
                width=6,
                height=50,
            ),
        ]
        return DashboardPlan(
            dashboard_title="Межфакультетский сравнительный анализ",
            description="Сводный дашборд сопоставления учебных и научно-исследовательских показателей факультетов.",
            charts=charts,
        )

    return None


def repair_known_domain_mistakes(plan: DashboardPlan, prompt: str) -> DashboardPlan:
    """Исправляет распространенные мелкие доменные неточности в плане LLM."""
    for chart in plan.charts:
        # 1. Приведение имен схем: если модель написала 'public.v_...' или забыла схему
        for v in [
            "v_students_by_faculty_form", "v_faculty_totals", "v_students_by_level",
            "v_rnd_funding", "v_publications", "v_faculty_labs_efficiency",
            "v_stipend_fund", "v_teaching_staff", "v_faculty_overview"
        ]:
            # Замена 'public.{v}' или 'from {v}' на 'analytics.{v}'
            chart.sql = re.sub(rf"\bpublic\.{v}\b", f"analytics.{v}", chart.sql, flags=re.IGNORECASE)
            chart.sql = re.sub(rf"\bFROM\s+{v}\b", f"FROM analytics.{v}", chart.sql, flags=re.IGNORECASE)
            chart.sql = re.sub(rf"\bJOIN\s+{v}\b", f"JOIN analytics.{v}", chart.sql, flags=re.IGNORECASE)

        # 2. Исправление частых опечаток в алиасах колонок
        typo_replacements = {
            "total_student": "total_students",
            "student_counts": "student_count",
            "amount_2025": "amount_2025_mln",
            "amount_2024": "amount_2024_mln",
            "publication_counts": "publication_count",
            "young_researcher": "young_researchers",
        }
        for bad, good in typo_replacements.items():
            if bad in chart.columns and good not in chart.columns:
                chart.columns = [good if c == bad else c for c in chart.columns]
            if chart.metric_column == bad:
                chart.metric_column = good

        # 3. Валидация x_axis для line и bar
        if chart.viz_type in {"bar", "line"} and not chart.x_axis and chart.groupby:
            chart.x_axis = chart.groupby[0]

    return plan
