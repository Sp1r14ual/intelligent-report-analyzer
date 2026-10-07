import os
import streamlit as st
import pandas as pd
from db import get_db_connection

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from docling_parser import process_document
from analyzer import (
    get_analysis_from_yandexgpt,
    load_llm,
)
from dashboard_generator.core.pipeline import run_pipeline
from dashboard_generator.core.superset_client import SupersetClient
from dashboard_generator.core.config import settings

st.set_page_config(page_title="Система анализа документов и дашбордов", layout="wide")



# ── Вспомогательные функции ───────────────────────────────────────────────────

def check_superset_online() -> bool:
    """Проверяет доступность Apache Superset."""
    try:
        c = SupersetClient()
        return c.check_health()
    except Exception:
        return False


from dashboard_generator.core.db_introspect import check_postgres_online, check_postgres_has_data


def init_db_checks() -> bool:
    """Проверяет, существует ли таблица reports в базе данных PostgreSQL.
    Возвращает True, если таблица найдена, иначе False."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'reports'"
        )
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    except Exception:
        return False


def delete_report(report_id: int):
    """Удаляет запись об отчёте из таблицы reports по его идентификатору.
    Все связанные чанки, таблицы и разделы удаляются каскадно (ON DELETE CASCADE)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reports WHERE id = %s", (report_id,))
    conn.commit()
    conn.close()


# ── Инициализация состояния сессии ────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []   # [{role, content}]

if "active_ids" not in st.session_state:
    st.session_state.active_ids = []

if "dashboard_history" not in st.session_state:
    st.session_state.dashboard_history = []

if "superset_prompt_input" not in st.session_state:
    st.session_state.superset_prompt_input = ""


# ── Боковая панель ────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("📂 Загрузка документов")
    uploaded_file = st.file_uploader("PDF-документ", type="pdf")
    year = st.number_input("Год отчёта", value=2025, step=1)
    auto_extract_superset = st.checkbox(
        "📊 Извлечь данные в базу Superset (PostgreSQL)",
        value=True,
        help="Модель автоматически проанализирует таблицы в загруженном отчёте и наполнит ими витрины базы данных для дашбордов Superset.",
    )

    if uploaded_file and st.button("Обработать и сохранить", type="primary"):
        with st.spinner("Идёт обработка документа..."):
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            if process_document(temp_path, year, uploaded_file.name):
                st.success("✅ Документ добавлен в базу!")
                if auto_extract_superset:
                    try:
                        conn_chk = get_db_connection()
                        cur_chk = conn_chk.cursor()
                        cur_chk.execute("SELECT id FROM reports WHERE filename = %s ORDER BY id DESC LIMIT 1", (uploaded_file.name,))
                        r_row = cur_chk.fetchone()
                        conn_chk.close()
                        if r_row:
                            from dashboard_generator.core.data_extractor import PDFDataExtractor
                            extractor = PDFDataExtractor()
                            ext_res = extractor.extract_from_report(r_row[0])
                            if ext_res.success and ext_res.results_by_table:
                                st.info(f"📊 Модель извлекла данные для Superset: обновлено витрин: {len(ext_res.results_by_table)}.")
                    except Exception as exc:
                        print(f"Ошибка автоматического извлечения в PostgreSQL: {exc}")
                st.rerun()
            else:
                st.error("❌ Ошибка при обработке документа.")

    st.divider()
    st.header("🗂️ Выбор документов для анализа")

    active_ids: list[int] = []

    if init_db_checks():
        conn = get_db_connection()
        reports_df = pd.read_sql_query(
            "SELECT id, filename, report_year, upload_date FROM reports ORDER BY upload_date DESC",
            conn,
        )
        conn.close()

        if not reports_df.empty:
            report_options = {
                f"{row['filename']} ({row['report_year']})": row["id"]
                for _, row in reports_df.iterrows()
            }
            selected_labels = st.multiselect(
                "Отметьте документы:",
                list(report_options.keys()),
                default=[
                    label for label, rid in report_options.items()
                    if rid in st.session_state.active_ids
                ],
            )
            active_ids = [report_options[label] for label in selected_labels]
            st.session_state.active_ids = active_ids

            with st.expander("🗑️ Удалить документ из базы"):
                del_label = st.selectbox(
                    "Выберите документ для удаления:",
                    ["— выберите —"] + list(report_options.keys()),
                )
                if del_label != "— выберите —" and st.button("Удалить", type="secondary"):
                    delete_report(report_options[del_label])
                    st.success(f"Документ «{del_label}» удалён.")
                    st.rerun()
        else:
            st.info("В базе пока нет документов.")
    else:
        st.info("База данных пуста. Загрузите первый документ.")

    st.divider()
    st.header("🧠 Языковая модель")

    llm = load_llm()
    active_model_badge = "🇷🇺 YandexGPT 5 Lite 8B"

    st.markdown(f"**Активная модель:** `{active_model_badge}`")
    server_info = llm.get_server_info()
    if server_info["online"]:
        st.success(f"🟢 Сервер онлайн: `YandexGPT 5 Lite 8B` (порт 8080)")
    else:
        st.info("ℹ️ Сервер `llama-server` не запущен. Запустите `run_llama_server.bat`")

    st.divider()
    with st.expander("💡 Типы запросов"):
        st.markdown("""
| Тип | Пример запроса |
|-----|---------------|
| 🔍 SEARCH | «Найди значение показателя X в таблице 3» |
| 🧮 CALCULATE | «Посчитай сумму по столбцу "Итого"» |
| ⚠️ ANOMALIES | «Проверь, нет ли расхождений в данных» |
| 📊 ANALYZE | «Проанализируй динамику показателей» |
| 🗂️ STRUCTURE | «Сколько таблиц в документе?» |
""")


# ── Главная область: вкладки Чат и Дашборды Superset ─────────────────────────

st.title("🎓 Аналитическая система университета")
st.caption(f"Активная модель: **{active_model_badge}**")

tab_chat, tab_superset = st.tabs([
    "💬 Чат с документами (RAG)",
    "📊 Генерация дашбордов (Apache Superset)"
])


# ── Вкладка 1: Чат с документами ──────────────────────────────────────────────
with tab_chat:
    if not active_ids:
        st.info("👈 Выберите один или несколько документов в боковой панели для анализа в чате.")
    else:
        conn = get_db_connection()
        placeholders = ','.join(['%s'] * len(active_ids))
        active_names = pd.read_sql_query(
            f"SELECT filename FROM reports WHERE id IN ({placeholders})",
            conn,
            params=tuple(active_ids),
        )
        conn.close()
        names_str = ", ".join(active_names["filename"].tolist())
        st.subheader(f"💬 Чат — {names_str}")

        col1, col2 = st.columns([8, 1])
        with col2:
            if st.button("🗑️ Очистить", help="Очистить историю чата"):
                st.session_state.messages = []
                st.rerun()

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        user_query = st.chat_input("Введите запрос к документам…")

        if user_query:
            st.session_state.messages.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            with st.chat_message("assistant"):
                with st.spinner(f"Модель ({active_model_badge}) анализирует документы…"):
                    answer = get_analysis_from_yandexgpt(llm, active_ids, user_query)
                st.markdown(answer)

            st.session_state.messages.append({"role": "assistant", "content": answer})


# ── Вкладка 2: Генерация дашбордов Superset ──────────────────────────────────
with tab_superset:
    st.subheader("📊 Построение дашбордов в Apache Superset по текстовому запросу")
    st.caption("Генерация интерактивных визуализаций по естественно-языковым запросам на основе семантической модели предметной области (отчеты ВПО и НИОКР).")

    # Статусная панель подключений
    col_stat1, col_stat2, col_stat3 = st.columns([3, 3, 2])
    with col_stat1:
        superset_ok = check_superset_online()
        if superset_ok:
            st.success("🟢 Apache Superset: онлайн (порт 8088)")
        else:
            st.warning("🟡 Apache Superset: офлайн")
    with col_stat2:
        pg_ok = check_postgres_online()
        if pg_ok:
            pg_has_data = check_postgres_has_data()
            if pg_has_data:
                st.success("🟢 PostgreSQL: витрины наполнены")
            else:
                st.warning("🟡 PostgreSQL: таблицы пусты")
        else:
            st.warning("🟡 PostgreSQL: не подключен")
    with col_stat3:
        if st.button("🔄 Обновить статус", help="Проверить подключение к Superset и базе данных"):
            st.rerun()

    # ── Блок наполнения витрин данными из PDF через модель ──
    with st.expander("🤖 Наполнение базы данных показателями из загруженных PDF (через LLM)", expanded=(pg_ok and not pg_has_data)):
        st.markdown(
            "Модель анализирует таблицы в загруженном отчёте, сопоставляет их со схемами витрин PostgreSQL "
            "(`students_faculty_form`, `stipend_fund`, `rnd_funding_sources` и др.), нормализует числовые показатели "
            "и наполняет базу данных для построения интерактивных дашбордов Superset."
        )

        conn_r = get_db_connection()
        pdf_reports_df = pd.read_sql_query(
            "SELECT id, filename, report_year FROM reports ORDER BY upload_date DESC",
            conn_r,
        )
        conn_r.close()

        if not pdf_reports_df.empty:
            report_dict = {
                f"{row['filename']} ({row['report_year']})": row["id"]
                for _, row in pdf_reports_df.iterrows()
            }
            col_rep, col_ext_btn = st.columns([5, 3])
            with col_rep:
                chosen_report_label = st.selectbox(
                    "Выберите отчёт для извлечения данных:",
                    list(report_dict.keys()),
                    key="extract_pdf_report_select",
                )
                chosen_report_id = report_dict[chosen_report_label]
            with col_ext_btn:
                st.write("")
                run_extract_btn = st.button("🚀 Извлечь показатели в БД", type="primary", use_container_width=True)

            if run_extract_btn:
                with st.status(f"🛠️ Модель извлекает данные из «{chosen_report_label}»...", expanded=True) as ext_status:
                    ext_log_box = st.empty()
                    ext_logs = []
                    def on_ext_log(m: str):
                        ext_logs.append(m)
                        ext_log_box.markdown("\n\n".join(ext_logs))

                    from dashboard_generator.core.data_extractor import PDFDataExtractor
                    extractor = PDFDataExtractor()
                    res = extractor.extract_from_report(chosen_report_id, progress_callback=on_ext_log)

                    if res.success and res.results_by_table:
                        ext_status.update(label=f"✅ Успешно обновлено витрин: {len(res.results_by_table)}!", state="complete")
                        st.success(f"Показатели из документа «{chosen_report_label}» успешно загружены в витрины PostgreSQL!")
                        st.rerun()
                    elif res.success:
                        ext_status.update(label="ℹ️ В документе не найдено подходящих аналитических таблиц", state="complete")
                    else:
                        ext_status.update(label="❌ Ошибка извлечения", state="error")
                        st.error(res.error_message)

            if st.button("🔄 Сбросить и заполнить эталонными демо-данными (ВПО + НИОКР)"):
                from scripts.init_postgres_analytics import init_analytics_database
                with st.spinner("Перезаполнение аналитических таблиц..."):
                    if init_analytics_database():
                        st.success("✅ Данные витрин успешно сброшены и наполнены!")
                        st.rerun()
        else:
            st.info("ℹ️ В системе пока нет загруженных PDF-отчетов. Загрузите отчет на панели слева.")

    if not superset_ok or not pg_ok:
        with st.expander("ℹ️ Как запустить Apache Superset и аналитическую базу"):
            st.markdown("""
            Для развертывания Apache Superset, PostgreSQL 16 и Redis:
            1. Запустите скрипт **`scripts/start_superset.bat`** (или команду `docker compose -f docker-compose.superset.yml up -d`).
            2. Дождитесь завершения инициализации базы и создания администратора (`admin / admin`).
            3. Заполните базу аналитическими данными из отчетов (кнопкой выше или командой `python scripts/init_postgres_analytics.py`).
            *(Даже если Superset временно не запущен, сервис сформирует валидный план и архив import-bundle.zip для ручного импорта!)*
            """)

    st.markdown("##### 💡 Быстрые примеры запросов:")
    chip_cols = st.columns(3)
    with chip_cols[0]:
        if st.button("👥 Студенты по факультетам и ступеням"):
            st.session_state.superset_prompt_input = "Построй дашборд распределения студентов по факультетам, уровням образования и формам обучения"
            st.rerun()
    with chip_cols[1]:
        if st.button("💰 Финансирование НИОКР по источникам"):
            st.session_state.superset_prompt_input = "Построй аналитический дашборд финансирования научных исследований (НИОКР) по источникам поступлений"
            st.rerun()
    with chip_cols[2]:
        if st.button("📚 Научные публикации (ВАК, Scopus, РИНЦ)"):
            st.session_state.superset_prompt_input = "Построй дашборд динамики научных публикаций сотрудников университета по базам цитирования"
            st.rerun()

    chip_cols2 = st.columns(3)
    with chip_cols2[0]:
        if st.button("🔬 Сравнение факультетов (лаборатории)"):
            st.session_state.superset_prompt_input = "Сравни показатели факультетов по численности студентов, финансированию лабораторий и статьям"
            st.rerun()
    with chip_cols2[1]:
        if st.button("💳 Стипендиальный фонд"):
            st.session_state.superset_prompt_input = "Построй дашборд структуры выплат стипендиального фонда университета за 2024-2025 годы"
            st.rerun()
    with chip_cols2[2]:
        if st.button("🏛️ Анализ факультета ФПМИ"):
            st.session_state.superset_prompt_input = "Построй аналитический отчет по студентам факультета ФПМИ и формам обучения"
            st.rerun()

    prompt_text = st.text_area(
        "Ваш запрос на построение дашборда:",
        value=st.session_state.get("superset_prompt_input", ""),
        placeholder="Например: Построй дашборд по распределению студентов по факультетам и формам обучения...",
        height=85,
    )

    col_btn1, col_btn2 = st.columns([3, 5])
    with col_btn1:
        generate_btn = st.button("🚀 Сгенерировать дашборд", type="primary", use_container_width=True)
    with col_btn2:
        skip_import = st.checkbox("Только собрать bundle (без вызова API Superset)", value=(not superset_ok))

    if generate_btn:
        if not prompt_text.strip():
            st.warning("⚠️ Пожалуйста, введите запрос на построение дашборда или выберите один из быстрых примеров выше.")
        else:
            with st.status("🛠️ Выполнение конвейера prompt-to-dashboard...", expanded=True) as status_box:
                log_container = st.empty()
                logs_history = []

                def on_progress(msg: str):
                    logs_history.append(msg)
                    log_container.markdown("\n\n".join(logs_history))

                result = run_pipeline(
                    prompt=prompt_text,
                    skip_superset_import=skip_import,
                    progress_callback=on_progress,
                )

                if result.success:
                    status_box.update(label=f"✅ Дашборд «{result.dashboard_title}» успешно создан!", state="complete", expanded=False)
                    st.success(f"🎉 **Дашборд успешно создан:** «{result.dashboard_title}» ({len(result.plan.charts) if result.plan else 0} чартов)")

                    c_act1, c_act2 = st.columns([4, 4])
                    with c_act1:
                        if result.dashboard_url:
                            st.link_button("🔗 Открыть дашборд в Apache Superset", result.dashboard_url, type="primary", use_container_width=True)
                    with c_act2:
                        if result.bundle_bytes:
                            st.download_button(
                                "💾 Скачать import-bundle.zip",
                                data=result.bundle_bytes,
                                file_name=f"superset_bundle_{result.dashboard_uuid}.zip",
                                mime="application/zip",
                                use_container_width=True,
                            )

                    # Сохранение в историю сессии
                    import datetime
                    st.session_state.dashboard_history.insert(0, {
                        "title": result.dashboard_title,
                        "uuid": result.dashboard_uuid,
                        "url": result.dashboard_url,
                        "charts_count": len(result.plan.charts) if result.plan else 0,
                        "time": datetime.datetime.now().strftime("%H:%M:%S"),
                        "prompt": prompt_text,
                    })

                    # Детали чартов
                    if result.plan and result.plan.charts:
                        with st.expander("📊 Детали чартов и сгенерированные SQL-запросы", expanded=True):
                            for i, ch in enumerate(result.plan.charts, 1):
                                st.markdown(f"**{i}. {ch.title}** (тип: `{ch.viz_type}`) — *{ch.description or ''}*")
                                st.code(ch.sql, language="sql")
                else:
                    status_box.update(label="❌ Ошибка при генерации дашборда", state="error", expanded=True)
                    st.error(f"Не удалось построить дашборд: {result.error_message}")

    # Журнал дашбордов текущей сессии
    if st.session_state.dashboard_history:
        st.divider()
        st.markdown("##### 📜 Недавно созданные дашборды:")
        for item in st.session_state.dashboard_history[:5]:
            col_h1, col_h2, col_h3 = st.columns([5, 2, 2])
            with col_h1:
                st.markdown(f"**{item['title']}** ({item['charts_count']} чартов) — *{item['time']}*")
                st.caption(f"Запрос: {item['prompt']}")
            with col_h2:
                if item["url"]:
                    st.link_button("🔗 Открыть", item["url"], use_container_width=True)
            with col_h3:
                st.caption(f"UUID: `{item['uuid'][:8]}...`")