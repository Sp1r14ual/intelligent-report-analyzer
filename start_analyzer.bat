@echo off
chcp 65001 >nul
echo Запуск системы анализа документов...

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

python init_db.py
streamlit run app.py
pause
