"""Скрипт для генерации второго тестового PDF-отчёта:
«ОТЧЁТ О НАУЧНО-ИССЛЕДОВАТЕЛЬСКОЙ ДЕЯТЕЛЬНОСТИ И ИННОВАЦИЯХ ЗА 2025 ГОД»
Использует ReportLab с поддержкой кириллицы (шрифт Arial).
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def build_science_pdf(filename="report_science_rnd_2025.pdf"):
    # Регистрация шрифта с кириллицей
    font_arial = "C:/Windows/Fonts/arial.ttf"
    font_bold = "C:/Windows/Fonts/arialbd.ttf"

    if not os.path.exists(font_arial):
        font_arial = "C:/Windows/Fonts/times.ttf"
        font_bold = "C:/Windows/Fonts/timesbd.ttf"

    pdfmetrics.registerFont(TTFont("CustomArial", font_arial))
    pdfmetrics.registerFont(TTFont("CustomArial-Bold", font_bold))

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    # Стили
    title_style = ParagraphStyle(
        "DocTitle",
        fontName="CustomArial-Bold",
        fontSize=13,
        leading=16,
        alignment=1,  # Center
        textColor=colors.HexColor("#1A2B4C"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        fontName="CustomArial",
        fontSize=10,
        leading=13,
        alignment=1,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=14,
    )
    h1_style = ParagraphStyle(
        "Heading1_Custom",
        fontName="CustomArial-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=14,
        spaceAfter=6,
    )
    h2_style = ParagraphStyle(
        "Heading2_Custom",
        fontName="CustomArial-Bold",
        fontSize=10.5,
        leading=13.5,
        textColor=colors.HexColor("#1F2937"),
        spaceBefore=10,
        spaceAfter=5,
    )
    body_style = ParagraphStyle(
        "Body_Custom",
        fontName="CustomArial",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=8,
    )
    table_cell = ParagraphStyle(
        "TableCell",
        fontName="CustomArial",
        fontSize=8.5,
        leading=11,
        alignment=1,  # Center
    )
    table_cell_left = ParagraphStyle(
        "TableCellLeft",
        fontName="CustomArial",
        fontSize=8.5,
        leading=11,
        alignment=0,  # Left
    )
    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        fontName="CustomArial-Bold",
        fontSize=8.5,
        leading=11,
        alignment=1,
        textColor=colors.HexColor("#0F172A"),
    )
    table_cell_bold_left = ParagraphStyle(
        "TableCellBoldLeft",
        fontName="CustomArial-Bold",
        fontSize=8.5,
        leading=11,
        alignment=0,
        textColor=colors.HexColor("#0F172A"),
    )

    table_base_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EBF2FA")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    elements = []

    # ==================== СТРАНИЦА 1 ====================
    elements.append(Paragraph("МИНИСТЕРСТВО НАУКИ И ВЫСШЕГО ОБРАЗОВАНИЯ РОССИЙСКОЙ ФЕДЕРАЦИИ", subtitle_style))
    elements.append(Paragraph("НОВОСИБИРСКИЙ ГОСУДАРСТВЕННЫЙ ТЕХНИЧЕСКИЙ УНИВЕРСИТЕТ", title_style))
    elements.append(Paragraph("ОТЧЁТ О НАУЧНО-ИССЛЕДОВАТЕЛЬСКОЙ ДЕЯТЕЛЬНОСТИ И ИННОВАЦИЯХ ЗА 2025 ГОД<br/>(Форма № 2-наука и мониторинг инновационной инфраструктуры)", subtitle_style))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Раздел 1. Финансирование научно-исследовательских работ (НИОКР)", h1_style))
    elements.append(Paragraph("1.1 Структура доходов от научных исследований и разработок", h2_style))
    elements.append(Paragraph(
        "В 2025 году научно-исследовательская деятельность университета осуществлялась в рамках национальных проектов "
        "и соглашений с индустриальными партнерами. Общий объем финансирования научно-исследовательских и опытно-конструкторских "
        "работ (НИОКР) показал существенный рост по сравнению с предыдущим годом, достигнув 644.0 млн рублей.",
        body_style
    ))
    elements.append(Paragraph("Таблица 1 — Объём финансирования НИОКР по источникам поступлений (2024–2025 гг.)", h2_style))

    t1_data = [
        [
            Paragraph("Источник финансирования", table_cell_bold),
            Paragraph("2024 год (млн руб.)", table_cell_bold),
            Paragraph("2025 год (млн руб.)", table_cell_bold),
            Paragraph("Доля в 2025 г. (%)", table_cell_bold),
        ],
        [Paragraph("Госзадание Минобрнауки РФ", table_cell_left), Paragraph("185.4", table_cell), Paragraph("210.6", table_cell), Paragraph("32.7%", table_cell)],
        [Paragraph("Гранты РНФ (Российский научный фонд)", table_cell_left), Paragraph("94.2", table_cell), Paragraph("118.5", table_cell), Paragraph("18.4%", table_cell)],
        [Paragraph("Хоздоговоры с промышленными предприятиями", table_cell_left), Paragraph("198.0", table_cell), Paragraph("245.8", table_cell), Paragraph("38.2%", table_cell)],
        [Paragraph("Региональные гранты и программы", table_cell_left), Paragraph("26.5", table_cell), Paragraph("32.4", table_cell), Paragraph("5.0%", table_cell)],
        [Paragraph("Международные научные контракты", table_cell_left), Paragraph("31.0", table_cell), Paragraph("36.7", table_cell), Paragraph("5.7%", table_cell)],
        [Paragraph("Итого объем НИОКР", table_cell_bold_left), Paragraph("535.1", table_cell_bold), Paragraph("644.0", table_cell_bold), Paragraph("100.0%", table_cell_bold)],
    ]
    t1 = Table(t1_data, colWidths=[210, 105, 105, 95])
    t1_style = list(table_base_style)
    t1_style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")))
    t1.setStyle(TableStyle(t1_style))
    elements.append(t1)

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "Совокупный объём НИОКР за отчетный период увеличился на 108.9 млн рублей (+20.4%). "
        "Наиболее высокие темпы прироста зафиксированы по договорам с индустриальными заказчиками (+24.1%) "
        "и грантам РНФ (+25.8%).",
        body_style
    ))

    # ==================== СТРАНИЦА 2 ====================
    elements.append(PageBreak())
    elements.append(Paragraph("Раздел 2. Публикационная активность и наукометрические показатели", h1_style))
    elements.append(Paragraph("2.1 Индексация научных публикаций сотрудников университета", h2_style))
    elements.append(Paragraph(
        "В данном подразделе представлены результаты мониторинга публикационной активности профессорско-преподавательского состава "
        "и научных сотрудников по ключевым наукометрическим системам за трехлетний период.",
        body_style
    ))
    elements.append(Paragraph("Таблица 2 — Динамика публикационной активности по типам индексации (2023–2025 гг.)", h2_style))

    # ВНИМАНИЕ: ЗАКЛАДЫВАЕМ ПРЕДНАМЕРЕННУЮ АНОМАЛИЮ В ТАБЛИЦУ 2 ДЛЯ ПРОВЕРКИ ANOMALIES!
    # Сумма за 2025 год: 215 + 175 + 560 + 38 + 790 = 1 778 публикаций!
    # В строке "Всего публикаций" ошибочно указано 1 890 (ошибка на 112 единиц).
    t2_data = [
        [
            Paragraph("Категория издания / индексация", table_cell_bold),
            Paragraph("2023 год", table_cell_bold),
            Paragraph("2024 год", table_cell_bold),
            Paragraph("2025 год", table_cell_bold),
        ],
        [Paragraph("Журналы Scopus / WoS (квартили Q1 и Q2)", table_cell_left), Paragraph("165", table_cell), Paragraph("182", table_cell), Paragraph("215", table_cell)],
        [Paragraph("Журналы Scopus / WoS (квартили Q3 и Q4)", table_cell_left), Paragraph("140", table_cell), Paragraph("158", table_cell), Paragraph("175", table_cell)],
        [Paragraph("Издания из Перечня ВАК (К1 и К2)", table_cell_left), Paragraph("480", table_cell), Paragraph("510", table_cell), Paragraph("560", table_cell)],
        [Paragraph("Монографии и академические сборники", table_cell_left), Paragraph("28", table_cell), Paragraph("32", table_cell), Paragraph("38", table_cell)],
        [Paragraph("Материалы конференций в РИНЦ", table_cell_left), Paragraph("680", table_cell), Paragraph("720", table_cell), Paragraph("790", table_cell)],
        [
            Paragraph("Всего публикаций", table_cell_bold_left),
            Paragraph("1 493", table_cell_bold),
            Paragraph("1 602", table_cell_bold),
            Paragraph("1 890", table_cell_bold),  # <- АНОМАЛИЯ: 215+175+560+38+790 = 1778, а впечатано 1890
        ],
    ]
    t2 = Table(t2_data, colWidths=[230, 95, 95, 95])
    t2_style = list(table_base_style)
    t2_style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FEE2E2")))
    t2.setStyle(TableStyle(t2_style))
    elements.append(t2)

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "Среднее число публикаций на 100 ставок научно-педагогических работников достигло 196 единиц. "
        "Доля статей в высокорейтинговых журналах категорий Q1 и Q2 составила 55.1% от общего объема международных публикаций университета.",
        body_style
    ))

    # ==================== СТРАНИЦА 3 ====================
    elements.append(PageBreak())
    elements.append(Paragraph("Раздел 3. Интеллектуальная собственность и коммерциализация разработок", h1_style))
    elements.append(Paragraph("3.1 Патентная активность и результаты интеллектуальной деятельности (РИД)", h2_style))
    elements.append(Paragraph("Таблица 3 — Распределение результатов интеллектуальной деятельности по факультетам (2025 г.)", h2_style))

    t3_data = [
        [
            Paragraph("Факультет / Подразделение", table_cell_bold),
            Paragraph("Патенты на изобретения", table_cell_bold),
            Paragraph("Полезные модели", table_cell_bold),
            Paragraph("Программы для ЭВМ", table_cell_bold),
            Paragraph("Лицензионные договоры", table_cell_bold),
        ],
        [Paragraph("ФПМИ (Прикладная математика)", table_cell_left), Paragraph("6", table_cell), Paragraph("2", table_cell), Paragraph("58", table_cell), Paragraph("14", table_cell)],
        [Paragraph("АВТФ (Автоматика и ВТ)", table_cell_left), Paragraph("12", table_cell), Paragraph("8", table_cell), Paragraph("46", table_cell), Paragraph("9", table_cell)],
        [Paragraph("ФЭН (Энергетика)", table_cell_left), Paragraph("18", table_cell), Paragraph("15", table_cell), Paragraph("14", table_cell), Paragraph("7", table_cell)],
        [Paragraph("РЭФ (Радиотехника)", table_cell_left), Paragraph("14", table_cell), Paragraph("11", table_cell), Paragraph("22", table_cell), Paragraph("5", table_cell)],
        [Paragraph("ФЛА (Летательные аппараты)", table_cell_left), Paragraph("16", table_cell), Paragraph("13", table_cell), Paragraph("18", table_cell), Paragraph("6", table_cell)],
        [Paragraph("Итого по университету", table_cell_bold_left), Paragraph("66", table_cell_bold), Paragraph("49", table_cell_bold), Paragraph("158", table_cell_bold), Paragraph("41", table_cell_bold)],
    ]
    t3 = Table(t3_data, colWidths=[180, 85, 80, 85, 85])
    t3_style = list(table_base_style)
    t3_style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")))
    t3.setStyle(TableStyle(t3_style))
    elements.append(t3)

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("3.2 Доходы от лицензирования и внедрения разработок", h2_style))
    elements.append(Paragraph(
        "Общий объём лицензионных платежей (роялти и единовременных паушальных взносов) от коммерциализации программного "
        "обеспечения и полезных моделей в 2025 году составил 24.8 млн рублей (в 2024 году аналогичный показатель составлял 17.3 млн рублей). "
        "Лидером по числу зарегистрированных программ для ЭВМ и объему лицензионных поступлений стал факультет прикладной математики и информатики (ФПМИ).",
        body_style
    ))

    # ==================== СТРАНИЦА 4 ====================
    elements.append(PageBreak())
    elements.append(Paragraph("Раздел 4. Подготовка научных кадров высшей квалификации", h1_style))
    elements.append(Paragraph("4.1 Защиты диссертаций и деятельность диссертационных советов", h2_style))
    elements.append(Paragraph("Таблица 4 — Показатели подготовки научно-педагогических кадров (2024–2025 гг.)", h2_style))

    t4_data = [
        [
            Paragraph("Показатель", table_cell_bold),
            Paragraph("2024 год", table_cell_bold),
            Paragraph("2025 год", table_cell_bold),
            Paragraph("Прирост (%)", table_cell_bold),
        ],
        [Paragraph("Выпуск аспирантов с защитой или представлением", table_cell_left), Paragraph("42", table_cell), Paragraph("56", table_cell), Paragraph("+33.3%", table_cell)],
        [Paragraph("Защиты кандидатских диссертаций сотрудниками", table_cell_left), Paragraph("34", table_cell), Paragraph("45", table_cell), Paragraph("+32.4%", table_cell)],
        [Paragraph("Защиты докторских диссертаций сотрудниками", table_cell_left), Paragraph("6", table_cell), Paragraph("9", table_cell), Paragraph("+50.0%", table_cell)],
        [Paragraph("Действующие диссертационные советы ВАК", table_cell_left), Paragraph("8", table_cell), Paragraph("9", table_cell), Paragraph("+12.5%", table_cell)],
        [Paragraph("Всего защит в советах университета", table_cell_bold_left), Paragraph("48", table_cell_bold), Paragraph("64", table_cell_bold), Paragraph("+33.3%", table_cell_bold)],
    ]
    t4 = Table(t4_data, colWidths=[230, 95, 95, 95])
    t4_style = list(table_base_style)
    t4_style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")))
    t4.setStyle(TableStyle(t4_style))
    elements.append(t4)

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Раздел 5. Центры коллективного пользования и научная инфраструктура", h1_style))
    elements.append(Paragraph("5.1 Научно-исследовательская база и уникальное оборудование", h2_style))
    elements.append(Paragraph(
        "В университете функционируют 3 центра коллективного пользования (ЦКП): ЦКП «Микроэлектроника и наноматериалы», "
        "ЦКП «Энергетическое машиностроение» и Научно-образовательный центр «Искусственный интеллект и большие данные». "
        "Балансовая стоимость научного оборудования центров на конец 2025 года составила 420.5 млн рублей. "
        "Средний коэффициент загрузки научного оборудования ЦКП составил 88.4%.",
        body_style
    ))
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("Проректор по научной работе: ___________________ / проф. Сидоров В.Н. /", body_style))
    elements.append(Paragraph("Начальник управления научных исследований: _______ / д.т.н. Кузнецов М.А. /", body_style))
    elements.append(Paragraph("Дата составления отчёта: 20 декабря 2025 года", subtitle_style))

    doc.build(elements)
    print(f"ReportLab successfully built: {filename}")


if __name__ == "__main__":
    build_science_pdf()
