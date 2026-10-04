import re
from dataclasses import dataclass, field


FORBIDDEN_COMMANDS = {
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "grant", "revoke", "copy", "execute", "call", "do", "vacuum", "analyze"
}

FORBIDDEN_PERSONAL_TERMS = {
    "fio", "passport", "surname", "lastname", "firstname", "patronymic",
    "phone", "email", "snils", "inn", "password", "secret", "credit_card",
    "фио", "паспорт", "фамилия", "имя", "отчество", "телефон", "почта", "снилс", "инн"
}

ALLOWED_PUBLIC_TABLES = set()


@dataclass
class SqlValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)


def strip_comments(sql: str) -> str:
    """Удаляет однострочные (-- ...) и многострочные (/* ... */) комментарии SQL."""
    # Удаляем многострочные комментарии
    sql = re.sub(r"/\*[\s\S]*?\*/", " ", sql)
    # Удаляем однострочные комментарии
    lines = [re.sub(r"--.*$", "", line) for line in sql.splitlines()]
    return "\n".join(lines).strip()


def _referenced_objects(sql: str) -> set[str]:
    """Извлекает имена таблиц/витрин после ключевых слов FROM и JOIN."""
    pattern = r"\b(?:from|join)\s+([a-zA-Z0-9_\.\"]+)"
    matches = re.findall(pattern, sql, flags=re.IGNORECASE)
    cleaned = set()
    for m in matches:
        obj = m.strip('"\';`')
        if obj:
            cleaned.add(obj.lower())
    return cleaned


def validate_select_sql(sql: str) -> SqlValidationResult:
    """
    Выполняет строгую проверку SQL-запроса по принципу 'whitelist':
    1. Запрос не пустой
    2. Одиночный оператор SELECT или WITH
    3. Отсутствие DDL/DML операций
    4. Отсутствие упоминаний персональных данных
    5. Обращение только к объектам схемы analytics.* (или разрешенным таблицам)
    """
    errors: list[str] = []
    cleaned = strip_comments(sql)
    lowered = cleaned.lower()

    if not cleaned:
        errors.append("SQL-запрос пуст.")
        return SqlValidationResult(False, errors)

    # Проверка на несколько операторов
    no_trailing = cleaned[:-1].strip() if cleaned.endswith(";") else cleaned
    if ";" in no_trailing:
        errors.append("Разрешен только один SQL-оператор (запрещены множественные выражения).")

    # Проверка первого ключевого слова
    if not re.match(r"^\s*(select|with)\b", lowered):
        errors.append("SQL-запрос должен начинаться с SELECT или WITH.")

    # Проверка запрещенных команд
    for cmd in sorted(FORBIDDEN_COMMANDS):
        if re.search(rf"\b{re.escape(cmd)}\b", lowered):
            errors.append(f"Обнаружена запрещенная SQL-команда: {cmd.upper()}. Разрешены только SELECT-запросы.")

    # Проверка персональных данных
    for term in sorted(FORBIDDEN_PERSONAL_TERMS):
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            errors.append(f"Обнаружено запрещенное поле персональных данных: '{term}'.")

    # Проверка разрешенных источников данных
    refs = _referenced_objects(cleaned)
    for ref in sorted(refs):
        # Если это подзапрос или CTE без схемы, пропускаем
        if "." not in ref:
            continue
        if ref.startswith("analytics."):
            continue
        if ref in ALLOWED_PUBLIC_TABLES:
            continue
        errors.append(f"Обращение к неразрешенному объекту базы данных: '{ref}'. Разрешена только схема 'analytics'.")

    return SqlValidationResult(is_valid=(len(errors) == 0), errors=errors)
