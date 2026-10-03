import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def build_pdf(filename="report_vpo_sample_2025.pdf"):
    # Регистрация шрифта Arial с поддержкой кириллицы
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

    styles = getSampleStyleSheet()
    
    # Стили текста
    title_style = ParagraphStyle(
        "DocTitle",
        fontName="CustomArial-Bold",
        fontSize=13,
        leading=16,
        alignment=1, # Center
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
        spaceAfter=15,
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
        alignment=1, # Center
    )
    table_cell_left = ParagraphStyle(
        "TableCellLeft",
        fontName="CustomArial",
        fontSize=8.5,
        leading=11,
        alignment=0, # Left
    )
    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        fontName="CustomArial-Bold",
        fontSize=8.5,
        leading=11,
        alignment=1, # Center
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
    elements.append(Paragraph("СТАТИСТИЧЕСКИЙ ОТЧЁТ О ДЕЯТЕЛЬНОСТИ ОБРАЗОВАТЕЛЬНОЙ ОРГАНИЗАЦИИ ЗА 2025 ГОД<br/>(Сводные данные по формам ВПО-1 и ВПО-2)", subtitle_style))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Раздел 1. Общие сведения об организации", h1_style))
    elements.append(Paragraph("1.1 Организационная структура и характеристика образовательной деятельности", h2_style))
    elements.append(Paragraph(
        "Новосибирский государственный технический университет осуществляет образовательную деятельность по программам "
        "высшего образования, включая бакалавриат, специалитет, магистратуру и программы подготовки научно-педагогических кадров "
        "в аспирантуре. В структуру образовательной организации входят 8 факультетов, институты и научно-производственные центры. "
        "Подготовка кадров ведется по очной, заочной и очно-заочной формам обучения. В 2025 году контингент обучающихся показал устойчивый рост.",
        body_style
    ))

    elements.append(Paragraph("Раздел 2. Сведения о контингенте обучающихся", h1_style))
    elements.append(Paragraph("2.1 Численность обучающихся по образовательным программам", h2_style))
    elements.append(Paragraph("Таблица 1 — Динамика численности обучающихся по уровням высшего образования (2024–2025 гг.)", h2_style))

    t1_data = [
        [
            Paragraph("Уровень образования", table_cell_bold),
            Paragraph("2024 год (чел.)", table_cell_bold),
            Paragraph("2025 год (чел.)", table_cell_bold),
            Paragraph("Прирост (%)", table_cell_bold),
        ],
        [Paragraph("Бакалавриат", table_cell_left), Paragraph("7 420", table_cell), Paragraph("7 850", table_cell), Paragraph("+5.8%", table_cell)],
        [Paragraph("Специалитет", table_cell_left), Paragraph("1 850", table_cell), Paragraph("1 790", table_cell), Paragraph("-3.2%", table_cell)],
        [Paragraph("Магистратура", table_cell_left), Paragraph("2 100", table_cell), Paragraph("2 450", table_cell), Paragraph("+16.7%", table_cell)],
        [Paragraph("Аспирантура", table_cell_left), Paragraph("430", table_cell), Paragraph("480", table_cell), Paragraph("+11.6%", table_cell)],
        [Paragraph("Итого по университету", table_cell_bold_left), Paragraph("11 800", table_cell_bold), Paragraph("12 570", table_cell_bold), Paragraph("+6.5%", table_cell_bold)],
    ]
    t1 = Table(t1_data, colWidths=[200, 105, 105, 105])
    t1_style = list(table_base_style)
    t1_style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")))
    t1.setStyle(TableStyle(t1_style))
    elements.append(t1)

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "Анализ данных Таблицы 1 свидетельствует о значительном увеличении интереса к программам магистратуры (+16.7%) "
        "и аспирантуры (+11.6%). Общий контингент студентов за отчетный период увеличился на 770 человек (+6.5%).",
        body_style
    ))

    # ==================== СТРАНИЦА 2 ====================
    elements.append(PageBreak())
    elements.append(Paragraph("2.2 Распределение контингента по факультетам и формам обучения", h2_style))
    elements.append(Paragraph(
        "В данном подразделе приведены сведения о распределении студентов по основным факультетам и формам обучения по состоянию на 1 октября 2025 года.",
        body_style
    ))
    elements.append(Paragraph("Таблица 2 — Распределение студентов по факультетам и формам обучения (2025 г.)", h2_style))

    # ВНИМАНИЕ: Заложена преднамеренная аномалия для проверки запроса ANOMALIES!
    # Сумма очной (6610) + заочной (1010) + очно-заочной (340) = 7 960 чел.
    # В строке "Всего по факультетам" ошибочно впечатано 8 500!
    t2_data = [
        [
            Paragraph("Факультет", table_cell_bold),
            Paragraph("Очная форма", table_cell_bold),
            Paragraph("Заочная форма", table_cell_bold),
            Paragraph("Очно-заочная", table_cell_bold),
            Paragraph("Итого", table_cell_bold),
        ],
        [Paragraph("ФПМИ (Прикладная математика)", table_cell_left), Paragraph("1 450", table_cell), Paragraph("120", table_cell), Paragraph("80", table_cell), Paragraph("1 650", table_cell)],
        [Paragraph("АВТФ (Автоматика и ВТ)", table_cell_left), Paragraph("1 820", table_cell), Paragraph("250", table_cell), Paragraph("110", table_cell), Paragraph("2 180", table_cell)],
        [Paragraph("ФЭН (Энергетика)", table_cell_left), Paragraph("1 210", table_cell), Paragraph("310", table_cell), Paragraph("60", table_cell), Paragraph("1 580", table_cell)],
        [Paragraph("РЭФ (Радиотехника)", table_cell_left), Paragraph("980", table_cell), Paragraph("190", table_cell), Paragraph("40", table_cell), Paragraph("1 210", table_cell)],
        [Paragraph("ФЛА (Летательные аппараты)", table_cell_left), Paragraph("1 150", table_cell), Paragraph("140", table_cell), Paragraph("50", table_cell), Paragraph("1 340", table_cell)],
        [
            Paragraph("Всего по факультетам", table_cell_bold_left),
            Paragraph("6 610", table_cell_bold),
            Paragraph("1 010", table_cell_bold),
            Paragraph("340", table_cell_bold),
            Paragraph("8 500", table_cell_bold), # <- ОШИБКА: 6610 + 1010 + 340 = 7960
        ],
    ]
    t2 = Table(t2_data, colWidths=[185, 80, 80, 85, 85])
    t2_style = list(table_base_style)
    t2_style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FEE2E2"))) # легкий фон
    t2.setStyle(TableStyle(t2_style))
    elements.append(t2)

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "Наибольшая численность обучающихся сосредоточена на факультете автоматики и вычислительной техники (АВТФ) — "
        "2 180 человек суммарно, а также на факультете прикладной математики и информатики (ФПМИ) — 1 650 человек. "
        "Доля очной формы обучения на ФПМИ составляет более 87%, что является самым высоким показателем среди факультетов.",
        body_style
    ))

    # ==================== СТРАНИЦА 3 ====================
    elements.append(PageBreak())
    elements.append(Paragraph("Раздел 3. Финансово-экономические показатели и материальная база", h1_style))
    elements.append(Paragraph("3.1 Стипендиальное обеспечение и социальные выплаты", h2_style))
    elements.append(Paragraph("Таблица 3 — Структура выплат стипендиального фонда университета", h2_style))

    t3_data = [
        [
            Paragraph("Вид стипендии / выплаты", table_cell_bold),
            Paragraph("2024 год (млн руб.)", table_cell_bold),
            Paragraph("2025 год (млн руб.)", table_cell_bold),
            Paragraph("Доля в 2025 г. (%)", table_cell_bold),
        ],
        [Paragraph("Государственная академическая стипендия", table_cell_left), Paragraph("142.5", table_cell), Paragraph("158.0", table_cell), Paragraph("51.3%", table_cell)],
        [Paragraph("Государственная социальная стипендия", table_cell_left), Paragraph("48.0", table_cell), Paragraph("54.2", table_cell), Paragraph("17.6%", table_cell)],
        [Paragraph("Повышенная академическая стипендия (ПГАС)", table_cell_left), Paragraph("36.5", table_cell), Paragraph("42.8", table_cell), Paragraph("13.9%", table_cell)],
        [Paragraph("Стипендии Президента и Правительства РФ", table_cell_left), Paragraph("12.0", table_cell), Paragraph("14.5", table_cell), Paragraph("4.7%", table_cell)],
        [Paragraph("Материальная помощь студентам", table_cell_left), Paragraph("35.0", table_cell), Paragraph("38.5", table_cell), Paragraph("12.5%", table_cell)],
        [Paragraph("Итого стипендиальный фонд", table_cell_bold_left), Paragraph("274.0", table_cell_bold), Paragraph("308.0", table_cell_bold), Paragraph("100.0%", table_cell_bold)],
    ]
    t3 = Table(t3_data, colWidths=[210, 105, 105, 95])
    t3_style = list(table_base_style)
    t3_style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")))
    t3.setStyle(TableStyle(t3_style))
    elements.append(t3)

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("3.2 Финансирование научных исследований и модернизации инфраструктуры", h2_style))
    elements.append(Paragraph(
        "Общий объем финансирования программы развития университета в 2025 году увеличился на 14.2%. "
        "В частности, общая сумма, затраченная на модернизацию жилых зданий и помещений общежитий университета за 2025 год, "
        "составила 84.6 млн рублей (в 2024 году аналогичные расходы составили 62.1 млн рублей). "
        "На обновление серверного парка и лабораторных стендов кафедр информатики израсходовано 45.2 млн рублей. "
        "Грантовая поддержка молодых исследователей профинансирована в объеме 28.4 млн рублей.",
        body_style
    ))

    # ==================== СТРАНИЦА 4 ====================
    elements.append(PageBreak())
    elements.append(Paragraph("Раздел 4. Кадровый состав и научно-педагогические работники", h1_style))
    elements.append(Paragraph("4.1 Квалификация профессорско-преподавательского состава", h2_style))
    elements.append(Paragraph("Таблица 4 — Кадровое обеспечение образовательного процесса (чел.)", h2_style))

    t4_data = [
        [
            Paragraph("Категория ППС", table_cell_bold),
            Paragraph("Штатные сотрудники", table_cell_bold),
            Paragraph("Внешние совместители", table_cell_bold),
            Paragraph("Всего", table_cell_bold),
        ],
        [Paragraph("Профессора, доктора наук", table_cell_left), Paragraph("145", table_cell), Paragraph("28", table_cell), Paragraph("173", table_cell)],
        [Paragraph("Доценты, кандидаты наук", table_cell_left), Paragraph("520", table_cell), Paragraph("65", table_cell), Paragraph("585", table_cell)],
        [Paragraph("Старшие преподаватели без степени", table_cell_left), Paragraph("180", table_cell), Paragraph("35", table_cell), Paragraph("215", table_cell)],
        [Paragraph("Ассистенты и преподаватели", table_cell_left), Paragraph("95", table_cell), Paragraph("18", table_cell), Paragraph("113", table_cell)],
        [Paragraph("Итого ППС", table_cell_bold_left), Paragraph("940", table_cell_bold), Paragraph("146", table_cell_bold), Paragraph("1 086", table_cell_bold)],
    ]
    t4 = Table(t4_data, colWidths=[210, 105, 105, 95])
    t4_style = list(table_base_style)
    t4_style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")))
    t4.setStyle(TableStyle(t4_style))
    elements.append(t4)

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Раздел 5. Контрольные показатели и заключение комиссии", h1_style))
    elements.append(Paragraph("5.1 Заключение о выполнении контрольных нормативов", h2_style))
    elements.append(Paragraph(
        "Комиссия по мониторингу статистической отчетности подтверждает соответствие ключевых параметров университета "
        "государственным аккредитационным нормативам. Доля научно-педагогических работников с учеными степенями и званиями "
        "в общей численности ППС превышает 69.8%. Все контрольные цифры приема на программы бакалавриата (2 450 мест) "
        "и магистратуры (820 мест) выполнены в полном объеме. Настоящий отчет рекомендуется к утверждению Ученым советом.",
        body_style
    ))
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("Проректор по учебной работе: ___________________ / проф. Иванов А.В. /", body_style))
    elements.append(Paragraph("Начальник учебно-методического управления: _______ / доц. Петрова Е.С. /", body_style))
    elements.append(Paragraph("Дата составления отчета: 15 ноября 2025 года", subtitle_style))

    doc.build(elements)
    print(f"ReportLab successfully built: {filename}")

if __name__ == "__main__":
    build_pdf()

