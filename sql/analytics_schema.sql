-- ====================================================================
-- Схема аналитических витрин для сервиса построения дашбордов Superset
-- На основе показателей статистических отчетов ВПО и НИОКР
-- ====================================================================

CREATE SCHEMA IF NOT EXISTS analytics;

-- 1. Студенты по факультетам и формам обучения
CREATE TABLE IF NOT EXISTS analytics.students_faculty_form (
    id SERIAL PRIMARY KEY,
    faculty_code VARCHAR(32) NOT NULL,
    faculty_name VARCHAR(128) NOT NULL,
    training_form VARCHAR(64) NOT NULL,
    student_count INTEGER NOT NULL,
    year INTEGER NOT NULL DEFAULT 2025
);

-- 2. Контингент по уровням образования
CREATE TABLE IF NOT EXISTS analytics.students_education_level (
    id SERIAL PRIMARY KEY,
    education_level VARCHAR(64) NOT NULL,
    students_2024 INTEGER NOT NULL,
    students_2025 INTEGER NOT NULL,
    growth_pct NUMERIC(5, 2) NOT NULL
);

-- 3. Выплаты стипендиального фонда
CREATE TABLE IF NOT EXISTS analytics.stipend_fund (
    id SERIAL PRIMARY KEY,
    stipend_type VARCHAR(128) NOT NULL,
    amount_2024_mln NUMERIC(10, 2) NOT NULL,
    amount_2025_mln NUMERIC(10, 2) NOT NULL,
    share_2025_pct NUMERIC(5, 2) NOT NULL
);

-- 4. Кадровое обеспечение (ППС)
CREATE TABLE IF NOT EXISTS analytics.teaching_staff (
    id SERIAL PRIMARY KEY,
    staff_category VARCHAR(128) NOT NULL,
    full_time_staff INTEGER NOT NULL,
    part_time_staff INTEGER NOT NULL,
    total_staff INTEGER NOT NULL,
    year INTEGER NOT NULL DEFAULT 2025
);

-- 5. Финансирование НИОКР по источникам
CREATE TABLE IF NOT EXISTS analytics.rnd_funding_sources (
    id SERIAL PRIMARY KEY,
    funding_source VARCHAR(128) NOT NULL,
    amount_2024_mln NUMERIC(10, 2) NOT NULL,
    amount_2025_mln NUMERIC(10, 2) NOT NULL,
    share_2025_pct NUMERIC(5, 2) NOT NULL
);

-- 6. Динамика научных публикаций
CREATE TABLE IF NOT EXISTS analytics.publications_dynamics (
    id SERIAL PRIMARY KEY,
    index_type VARCHAR(64) NOT NULL,
    year INTEGER NOT NULL,
    publication_count INTEGER NOT NULL
);

-- 7. Интеллектуальная собственность
CREATE TABLE IF NOT EXISTS analytics.intellectual_property (
    id SERIAL PRIMARY KEY,
    object_type VARCHAR(128) NOT NULL,
    year INTEGER NOT NULL,
    object_count INTEGER NOT NULL
);

-- 8. Эффективность научных лабораторий факультетов
CREATE TABLE IF NOT EXISTS analytics.faculty_labs (
    id SERIAL PRIMARY KEY,
    faculty_code VARCHAR(32) NOT NULL,
    faculty_name VARCHAR(128) NOT NULL,
    lab_name VARCHAR(256) NOT NULL,
    funding_mln NUMERIC(10, 2) NOT NULL,
    articles_count INTEGER NOT NULL,
    young_researchers INTEGER NOT NULL,
    year INTEGER NOT NULL DEFAULT 2025
);

-- --------------------------------------------------------------------
-- АНАЛИТИЧЕСКИЕ ВИТРИНЫ (VIEWS) ДЛЯ LLM И SUPERSET
-- --------------------------------------------------------------------

-- Витрина 1: Студенты по факультетам и формам обучения
CREATE OR REPLACE VIEW analytics.v_students_by_faculty_form AS
SELECT
    faculty_code,
    faculty_name,
    training_form,
    student_count,
    year
FROM analytics.students_faculty_form;

-- Витрина 2: Сводка контингента по факультетам (итого и по формам)
CREATE OR REPLACE VIEW analytics.v_faculty_totals AS
SELECT
    faculty_code,
    faculty_name,
    SUM(CASE WHEN training_form = 'Очная форма' THEN student_count ELSE 0 END) AS full_time_count,
    SUM(CASE WHEN training_form = 'Заочная форма' THEN student_count ELSE 0 END) AS extramural_count,
    SUM(CASE WHEN training_form = 'Очно-заочная' THEN student_count ELSE 0 END) AS part_time_count,
    SUM(student_count) AS total_students
FROM analytics.students_faculty_form
GROUP BY faculty_code, faculty_name;

-- Витрина 3: Студенты по уровням высшего образования
CREATE OR REPLACE VIEW analytics.v_students_by_level AS
SELECT
    education_level,
    students_2024,
    students_2025,
    growth_pct
FROM analytics.students_education_level;

-- Витрина 4: Структура выплат стипендиального фонда
CREATE OR REPLACE VIEW analytics.v_stipend_fund AS
SELECT
    stipend_type,
    amount_2024_mln,
    amount_2025_mln,
    share_2025_pct
FROM analytics.stipend_fund;

-- Витрина 5: Источники финансирования НИОКР
CREATE OR REPLACE VIEW analytics.v_rnd_funding AS
SELECT
    funding_source,
    amount_2024_mln,
    amount_2025_mln,
    share_2025_pct
FROM analytics.rnd_funding_sources;

-- Витрина 6: Динамика публикационной активности по годам и типам
CREATE OR REPLACE VIEW analytics.v_publications AS
SELECT
    index_type,
    year,
    publication_count
FROM analytics.publications_dynamics;

-- Витрина 7: Научные лаборатории и молодые ученые
CREATE OR REPLACE VIEW analytics.v_faculty_labs_efficiency AS
SELECT
    faculty_code,
    faculty_name,
    lab_name,
    funding_mln,
    articles_count,
    young_researchers
FROM analytics.faculty_labs;

-- Витрина 8: Кадровый состав профессорско-преподавательского состава
CREATE OR REPLACE VIEW analytics.v_teaching_staff AS
SELECT
    staff_category,
    full_time_staff,
    part_time_staff,
    total_staff
FROM analytics.teaching_staff;

-- Витрина 9: Сводный межфакультетский сравнительный обзор
CREATE OR REPLACE VIEW analytics.v_faculty_overview AS
SELECT
    f.faculty_code,
    f.faculty_name,
    COALESCE(st.total_students, 0) AS total_students,
    COALESCE(SUM(l.funding_mln), 0) AS labs_funding_mln,
    COALESCE(SUM(l.articles_count), 0) AS total_lab_articles,
    COALESCE(SUM(l.young_researchers), 0) AS total_young_researchers
FROM (
    SELECT DISTINCT faculty_code, faculty_name FROM analytics.students_faculty_form
) f
LEFT JOIN analytics.v_faculty_totals st ON st.faculty_code = f.faculty_code
LEFT JOIN analytics.faculty_labs l ON l.faculty_code = f.faculty_code
GROUP BY f.faculty_code, f.faculty_name, st.total_students;

-- ====================================================================
-- Данные заполняются моделью (DataExtractor) на этапе парсинга PDF
-- ====================================================================


-- ====================================================================
-- Таблицы хранения документов для системы RAG и анализа отчетов
-- ====================================================================

CREATE TABLE IF NOT EXISTS reports (
    id          SERIAL PRIMARY KEY,
    filename    TEXT NOT NULL,
    report_year INTEGER,
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id          SERIAL PRIMARY KEY,
    report_id   INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    chunk_order INTEGER NOT NULL,
    chunk_text  TEXT NOT NULL,
    has_tables  INTEGER DEFAULT 0,
    embedding   BYTEA
);

CREATE TABLE IF NOT EXISTS document_tables (
    id          SERIAL PRIMARY KEY,
    report_id   INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    chunk_order INTEGER NOT NULL,
    table_text  TEXT NOT NULL,
    embedding   BYTEA
);

CREATE TABLE IF NOT EXISTS sections (
    id              SERIAL PRIMARY KEY,
    report_id       INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    section_number  TEXT,
    section_title   TEXT,
    chunk_order     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_report ON document_chunks(report_id, chunk_order);
CREATE INDEX IF NOT EXISTS idx_document_tables_report ON document_tables(report_id, chunk_order);
CREATE INDEX IF NOT EXISTS idx_sections_report ON sections(report_id);

