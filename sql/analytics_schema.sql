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
-- НАПОЛНЕНИЕ ДАННЫМИ ИЗ СТАТИСТИЧЕСКИХ ОТЧЕТОВ ВПО И НИОКР
-- ====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM analytics.stipend_fund LIMIT 1) THEN
        -- 1. Студенты по факультетам и формам обучения
        INSERT INTO analytics.students_faculty_form (faculty_code, faculty_name, training_form, student_count, year) VALUES
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
            ('ФЛА', 'Летательные аппараты', 'Очно-заочная', 50, 2025);

        -- 2. Уровни высшего образования
        INSERT INTO analytics.students_education_level (education_level, students_2024, students_2025, growth_pct) VALUES
            ('Бакалавриат', 7420, 7850, 5.8),
            ('Специалитет', 1850, 1790, -3.2),
            ('Магистратура', 2100, 2450, 16.7),
            ('Аспирантура', 430, 480, 11.6);

        -- 3. Выплаты стипендиального фонда
        INSERT INTO analytics.stipend_fund (stipend_type, amount_2024_mln, amount_2025_mln, share_2025_pct) VALUES
            ('Государственная академическая стипендия', 142.5, 158.0, 51.3),
            ('Государственная социальная стипендия', 48.0, 54.2, 17.6),
            ('Повышенная академическая стипендия (ПГАС)', 36.5, 42.8, 13.9),
            ('Стипендии Президента и Правительства РФ', 12.0, 14.5, 4.7),
            ('Материальная помощь студентам', 35.0, 38.5, 12.5);

        -- 4. Кадровое обеспечение (ППС)
        INSERT INTO analytics.teaching_staff (staff_category, full_time_staff, part_time_staff, total_staff, year) VALUES
            ('Профессора, доктора наук', 145, 28, 173, 2025),
            ('Доценты, кандидаты наук', 520, 65, 585, 2025),
            ('Старшие преподаватели без степени', 180, 35, 215, 2025),
            ('Ассистенты и преподаватели', 95, 18, 113, 2025);

        -- 5. Финансирование НИОКР
        INSERT INTO analytics.rnd_funding_sources (funding_source, amount_2024_mln, amount_2025_mln, share_2025_pct) VALUES
            ('Госзадание Минобрнауки РФ', 185.4, 210.6, 32.7),
            ('Гранты РНФ (Российский научный фонд)', 94.2, 118.5, 18.4),
            ('Хоздоговоры с промышленными предприятиями', 198.0, 245.8, 38.2),
            ('Региональные гранты и программы', 26.5, 32.4, 5.0),
            ('Международные научные контракты', 31.0, 36.7, 5.7);

        -- 6. Публикационная активность
        INSERT INTO analytics.publications_dynamics (index_type, year, publication_count) VALUES
            ('ВАК', 2023, 190), ('ВАК', 2024, 205), ('ВАК', 2025, 215),
            ('Scopus', 2023, 140), ('Scopus', 2024, 160), ('Scopus', 2025, 175),
            ('Web of Science', 2023, 50), ('Web of Science', 2024, 45), ('Web of Science', 2025, 38),
            ('Монографии', 2023, 25), ('Монографии', 2024, 30), ('Монографии', 2025, 35),
            ('РИНЦ', 2023, 680), ('РИНЦ', 2024, 730), ('РИНЦ', 2025, 790);

        -- 7. Интеллектуальная собственность
        INSERT INTO analytics.intellectual_property (object_type, year, object_count) VALUES
            ('Патенты на изобретения', 2023, 18), ('Патенты на изобретения', 2024, 22), ('Патенты на изобретения', 2025, 26),
            ('Свидетельства на программы для ЭВМ', 2023, 45), ('Свидетельства на программы для ЭВМ', 2024, 58), ('Свидетельства на программы для ЭВМ', 2025, 64),
            ('Базы данных', 2023, 12), ('Базы данных', 2024, 15), ('Базы данных', 2025, 19),
            ('Полезные модели', 2023, 8), ('Полезные модели', 2024, 11), ('Полезные модели', 2025, 14);

        -- 8. Научные лаборатории факультетов
        INSERT INTO analytics.faculty_labs (faculty_code, faculty_name, lab_name, funding_mln, articles_count, young_researchers, year) VALUES
            ('ФПМИ', 'Прикладная математика и информатика', 'Лаборатория искусственного интеллекта и анализа больших данных', 48.5, 24, 14, 2025),
            ('АВТФ', 'Автоматика и вычислительная техника', 'Научно-образовательный центр встраиваемых систем и робототехники', 62.0, 31, 18, 2025),
            ('ФЭН', 'Энергетика', 'Лаборатория интеллектуальных энергетических сетей Smart Grid', 54.2, 19, 11, 2025),
            ('РЭФ', 'Радиотехника и электроника', 'Центр микроэлектроники и квантовых оптических сенсоров', 42.8, 16, 9, 2025),
            ('ФЛА', 'Летательные аппараты', 'Лаборатория аэродинамических исследований и композитных конструкций', 38.3, 14, 8, 2025);
    END IF;
END $$;

