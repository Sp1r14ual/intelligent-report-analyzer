import re
import os
import requests
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from table_retriever import TableRetriever
from reranker import get_reranker
from retriever import FaissRetriever, extract_section_fragment
from db import get_db_connection



def get_wsl_host_ip() -> str | None:
    """Определяет IP-адрес хоста Windows при запуске кода внутри WSL2."""
    try:
        is_wsl = False
        if os.path.exists("/proc/version"):
            with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
                if "microsoft" in f.read().lower():
                    is_wsl = True
        if not is_wsl:
            return None

        if os.path.exists("/etc/resolv.conf"):
            with open("/etc/resolv.conf", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2 and parts[0] == "nameserver":
                        return parts[1]
    except Exception:
        pass
    return None


class LLMClient:
    """Клиент для взаимодействия с локальным сервером YandexGPT:
    1) HTTP llama-server (OpenAI-compatible /v1/completions или /completion)
    2) Локальный llama-cpp-python (если библиотека установлена)
    3) Безопасная заглушка (если сервер ещё не запущен, чтобы интерфейс не падал)."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080", gguf_path: str | None = None, model_name: str | None = None):
        self.base_url = os.getenv("LLM_BASE_URL", base_url).rstrip("/")
        self.gguf_path = gguf_path
        self.model_name = model_name or (os.path.basename(gguf_path) if gguf_path else "YandexGPT 5 Lite 8B")
        self._llama_instance = None

        if self.gguf_path and os.path.exists(self.gguf_path):
            try:
                from llama_cpp import Llama
                self._llama_instance = Llama(
                    model_path=self.gguf_path,
                    n_gpu_layers=int(os.getenv("LLM_GPU_LAYERS", "18")),
                    n_ctx=int(os.getenv("LLM_CTX", "8192")),
                    n_threads=int(os.getenv("LLM_THREADS", "6")),
                    n_batch=512,
                    flash_attn=True,
                    verbose=False,
                )
            except Exception:
                self._llama_instance = None

    def _get_candidate_urls(self) -> list[str]:
        """Возвращает список URL для подключения с учетом возможного хоста Windows из WSL2."""
        urls = [self.base_url]
        if "127.0.0.1" in self.base_url or "localhost" in self.base_url:
            host_ip = get_wsl_host_ip()
            if host_ip:
                import urllib.parse
                parsed = urllib.parse.urlparse(self.base_url)
                port = parsed.port or 8080
                wsl_url = f"http://{host_ip}:{port}"
                if wsl_url not in urls:
                    urls.append(wsl_url)
        return urls

    def get_server_info(self) -> dict:
        """Проверяет доступность сервера llama-server и определяет имя запущенной модели."""
        for candidate_url in self._get_candidate_urls():
            try:
                resp = requests.get(f"{candidate_url}/health", timeout=2.5)
                if resp.status_code == 200:
                    self.base_url = candidate_url
                    return {"online": True, "model": self.model_name or "YandexGPT 5 Lite 8B"}
            except Exception:
                pass

            try:
                resp = requests.get(f"{candidate_url}/v1/models", timeout=2.5)
                if resp.status_code == 200:
                    self.base_url = candidate_url
                    data = resp.json()
                    models_data = data.get("data", [])
                    if models_data:
                        raw_id = models_data[0].get("id", "")
                        name = os.path.basename(raw_id.replace("\\", "/")) if raw_id else "YandexGPT 5 Lite 8B"
                        return {"online": True, "model": name}
            except Exception:
                pass

            try:
                resp = requests.get(f"{candidate_url}/props", timeout=2.5)
                if resp.status_code == 200:
                    self.base_url = candidate_url
                    data = resp.json()
                    raw_path = data.get("model_path", "")
                    name = os.path.basename(raw_path.replace("\\", "/")) if raw_path else "YandexGPT 5 Lite 8B"
                    return {"online": True, "model": name}
            except Exception:
                pass

        return {"online": False, "model": None}

    def __call__(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.1, repeat_penalty: float = 1.1) -> dict:
        # 1. Попытка через локальный инстанс llama_cpp, если он загружен
        if self._llama_instance is not None:
            try:
                return self._llama_instance(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    repeat_penalty=repeat_penalty,
                )
            except Exception as e:
                print(f"Ошибка локального инференса llama_cpp: {e}")

        # 2. Обращение к HTTP llama-server (порт 8080)
        import requests
        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "repeat_penalty": repeat_penalty,
        }

        for candidate_url in self._get_candidate_urls():
            try:
                resp = requests.post(f"{candidate_url}/v1/completions", json=payload, timeout=240)
                if resp.status_code == 200:
                    self.base_url = candidate_url
                    data = resp.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        return data
                else:
                    print(f"[LLMClient] /v1/completions HTTP {resp.status_code}: {resp.text[:200]}")
            except requests.exceptions.RequestException:
                pass

            try:
                resp = requests.post(f"{candidate_url}/completion", json=payload, timeout=240)
                if resp.status_code == 200:
                    self.base_url = candidate_url
                    data = resp.json()
                    text = data.get("content", "")
                    return {"choices": [{"text": text}]}
                else:
                    print(f"[LLMClient] /completion HTTP {resp.status_code}: {resp.text[:200]}")
            except requests.exceptions.RequestException:
                pass

        # 3. Сообщение пользователю, если сервер модели ещё не запущен
        return {
            "choices": [{
                "text": (
                    "###ОТВЕТ###\n"
                    "⚠️ **Сервер языковой модели не отвечает.**\n\n"
                    f"Сервис попытался подключиться к `{self.base_url}`, но соединение не установлено.\n\n"
                    "**Как включить генерацию ответов:**\n"
                    "1. Запустите локальный сервер `run_llama_server.bat` (он запустит модель YandexGPT 5 Lite на порту 8080).\n\n"
                    "*Примечание: Загрузка документов, парсинг Docling и семантический поиск по таблицам и чанкам работают независимо от сервера LLM.*"
                )
            }]
        }


def get_available_local_models() -> list[str]:
    """Возвращает список доступных .gguf моделей из папки models/,
    фильтруя модель YandexGPT-5-Lite-8B-instruct-Q4_K_M.gguf."""
    base = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base, "models")
    if not os.path.exists(models_dir):
        return []

    target = "YandexGPT-5-Lite-8B-instruct-Q4_K_M.gguf"
    if os.path.exists(os.path.join(models_dir, target)):
        return [target]
    return [f for f in os.listdir(models_dir) if f.endswith(".gguf")]


def set_env_local_model(model_filename: str):
    """Сохраняет выбранную локальную модель в файл .env для скрипта запуска."""
    base = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base, ".env")
    lines = []
    found = False
    new_line = f"LOCAL_MODEL=models\\{model_filename}\n"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("LOCAL_MODEL="):
                lines[i] = new_line
                found = True
                break
    if not found:
        lines.append(new_line)
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


@st.cache_resource
def load_llm(model_name: str | None = None) -> LLMClient:
    """Загружает или подключает модель YandexGPT 5 Lite 8B и кэширует клиент."""
    base = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base, "models")

    target = "YandexGPT-5-Lite-8B-instruct-Q4_K_M.gguf"
    candidate = os.path.join(models_dir, target)
    model_path = candidate if os.path.exists(candidate) else None
    model_name = target

    server_url = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8080")
    return LLMClient(base_url=server_url, gguf_path=model_path, model_name=model_name)



@st.cache_resource
def load_table_retriever():
    """Создаёт и кэширует экземпляр TableRetriever для поиска по таблицам."""
    return TableRetriever()


@st.cache_resource
def load_retriever():
    """Создаёт и кэширует экземпляр FaissRetriever для семантического поиска по чанкам."""
    return FaissRetriever()


_VALID_INTENTS = ("SEARCH", "CALCULATE", "ANOMALIES", "ANALYZE", "STRUCTURE", "GENERAL")

_META_RE = re.compile(r"###\s+МЕТАДАННЫЕ:.*?###\n+", re.DOTALL)
_PAGE_IN_META_RE = re.compile(r"Стр\.\s*(\d+)")
_SECTION_QUERY_RE = re.compile(r"(\d+(?:\.\d+)+)")

_INTENT_PROMPT = """
SEARCH - поиск факта
CALCULATE - вычисления
ANOMALIES - поиск ошибок
ANALYZE - анализ
STRUCTURE - структура документа
GENERAL - остальное

Запрос: {query}
Ответ:
"""

_INTENT_INSTRUCTIONS = {
    "SEARCH": (
        "- Найди точное значение в переданном контексте.\n"
        "- Обязательно сопоставляй точный столбец (год, форму обучения, категорию) с нужной строкой.\n"
        "- Укажи таблицу или раздел и точное значение."
    ),
    "CALCULATE": (
        "- Для вычислений: сначала выпиши точные исходные числа из таблицы/текста с указанием строки и столбца.\n"
        "- Покажи пошаговый расчет с формулой (например: 274.0 + 308.0 = 582.0).\n"
        "- Дай четкий итоговый результат."
    ),
    "ANOMALIES": (
        "- Внимательно проверь таблицы на предмет математических ошибок и нестыковок.\n"
        "- Пересчитай суммы по строкам и столбцам: сложи отдельные слагаемые и сравни их фактическую сумму со значением в строке 'Итого' / 'Всего'.\n"
        "- Если сумма слагаемых не сходится со значением в 'Итого' / 'Всего', обязательно укажи: в какой таблице ошибка, какие числа складывались, сколько должно получиться на самом деле и какое ошибочное число впечатано в отчет."
    ),
    "ANALYZE": (
        "- Проведи сравнительный анализ показателей, выдели ключевые изменения и тенденции.\n"
        "- Приведи динамику изменений как в абсолютных значениях, так и в процентах (прирост/спад)."
    ),
    "STRUCTURE": (
        "- Приведи структурированный перечень всех разделов и таблиц, найденных в контексте документа."
    ),
    "GENERAL": (
        "- Ответь четко и по существу на основе информации из переданного контекста."
    ),
}

_SYSTEM_PROMPT = """Ты аналитик университетской отчетности. Твоя задача — дать точный, логически обоснованный и проверяемый ответ по предоставленному контексту.

Строгие правила:
1. Используй ИСКЛЮЧИТЕЛЬНО информацию из раздела «Контекст» ниже.
2. Не добавляй факты, догадки или цифры от себя. Если данных в контексте недостаточно — прямо сообщи об этом.
3. Соблюдай специальные требования для текущей задачи ({intent}):
{intent_instruction}

Контекст:
{context}

Вопрос:
{query}

Ответ аналитика:"""


def rerank_results(query, results, top_k=100):
    """Переранжирует список результатов поиска с помощью CrossEncoder-реранкера.
    Добавляет поле rerank_score к каждому результату, сортирует по убыванию
    и возвращает не более top_k лучших."""
    if not results:
        return []

    reranker = get_reranker()
    pairs = [(query, r["chunk_text"][:2000]) for r in results]
    scores = reranker.predict(pairs)

    for r, score in zip(results, scores):
        r["rerank_score"] = float(score)

    results.sort(key=lambda x: x["rerank_score"], reverse=True)
    return results[:top_k]


def is_table_query(query):
    """Определяет, связан ли запрос с табличными данными.
    Проверяет наличие ключевых слов, характерных для вопросов о численности,
    долях, категориях обучающихся и финансовых показателях."""
    keywords = [
        "сколько", "численность", "количество", "обучающихся",
        "магистрат", "магистр", "бакалавр", "аспирант",
        "стипенд", "доля", "процент", "всего",
        "таблиц", "сумм", "затрат", "расход", "рубл", "млн",
        "бюджет", "выплат", "фонд", "ппс", "профессор", "доцент",
        "кадр", "преподавател", "факультет", "фпми", "автф", "фэн",
        "рэф", "фла", "ошибк", "расхожден", "аномал", "динамик", "прирост"
    ]
    return any(k in query.lower() for k in keywords)


def get_intent(llm, user_query):
    """Определяет тип запроса пользователя (intent).
    Сначала проверяет запрос по регулярным выражениям для быстрого распознавания
    STRUCTURE и SEARCH, затем при необходимости обращается к языковой модели.
    Возвращает одну из констант: SEARCH, CALCULATE, ANOMALIES, ANALYZE, STRUCTURE, GENERAL."""
    q = user_query.lower()

    if re.search(r"(оглавлен|структур)", q):
        return "STRUCTURE"

    if re.search(
        r"(что содержится в разделе|что находится в разделе"
        r"|что указано в разделе|содержимое раздела)", q
    ):
        return "SEARCH"

    prompt = _INTENT_PROMPT.format(query=user_query)
    try:
        out = llm(prompt, max_tokens=8, temperature=0)
        raw = out["choices"][0]["text"].strip().upper()
        for v in _VALID_INTENTS:
            if v in raw:
                return v
    except Exception:
        pass

    return "GENERAL"


def _strip_metadata(text):
    """Удаляет блок метаданных формата ### МЕТАДАННЫЕ: ... ### из текста чанка."""
    return _META_RE.sub("", text)


def _page_from_metadata(text):
    """Извлекает номер первой страницы из блока метаданных чанка.
    Возвращает целое число или 0, если метаданные не найдены."""
    m = _PAGE_IN_META_RE.search(text[:300])
    return int(m.group(1)) if m else 0


def extract_headers_from_chunks(chunks):
    """Извлекает все заголовки Markdown (h1–h6) из списка чанков документа.
    Возвращает список словарей с полями level, title и page."""
    headers = []
    md_header = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    for chunk in chunks:
        text = _strip_metadata(chunk[1])
        page = _page_from_metadata(chunk[1]) or chunk[0]

        for m in md_header.finditer(text):
            headers.append({
                "level": len(m.group(1)),
                "title": m.group(2).strip(),
                "page": page,
            })

    return headers


def build_structure_context(report_name, chunks):
    """Строит текстовое представление структуры документа в виде дерева заголовков.
    Используется для ответа на запросы типа STRUCTURE (оглавление, структура)."""
    headers = extract_headers_from_chunks(chunks)
    lines = [f"=== СТРУКТУРА {report_name} ==="]

    for h in headers:
        indent = "  " * (h["level"] - 1)
        lines.append(f'{indent}{h["title"]} (стр. {h["page"]})')

    return "\n".join(lines)


def faiss_results_to_context(report_name, results):
    """Формирует единую строку контекста из списка найденных чанков.
    Ограничивает суммарный объём контекста 12 000 символами (~2500 токенов),
    чтобы не перегружать контекстное окно и KV-кэш модели."""
    MAX_CONTEXT_CHARS = 12_000
    parts = []
    total_size = 0

    for r in results:
        block = (
            f"\n=== {report_name}\n"
            f"Чанк {r['chunk_order']}\n"
            f"===\n\n"
            f"{r['chunk_text']}\n"
        )
        if total_size + len(block) > MAX_CONTEXT_CHARS:
            break
        parts.append(block)
        total_size += len(block)

    return "\n".join(parts)


def _deduplicate(results, key_fn):
    """Удаляет дублирующиеся результаты из списка по ключу, вычисляемому функцией key_fn.
    Сохраняет порядок и оставляет только первое вхождение каждого уникального ключа."""
    seen = set()
    unique = []
    for r in results:
        sig = key_fn(r)
        if sig not in seen:
            seen.add(sig)
            unique.append(r)
    return unique


def _collect_context_for_report(report_id, user_query, intent, cursor):
    """Собирает текстовый контекст для одного документа по его report_id.
    В зависимости от intent выбирает стратегию поиска:
    - STRUCTURE: строит дерево заголовков из всех чанков;
    - запрос с номером раздела: точечный поиск по section_number;
    - остальное: семантический поиск с опциональным поиском по таблицам и реранкингом.
    Возвращает строку контекста, готовую к подстановке в промпт."""
    cursor.execute(
        "SELECT chunk_order, chunk_text, COALESCE(has_tables, 0) "
        "FROM document_chunks "
        "WHERE report_id = %s "
        "ORDER BY chunk_order",
        (report_id,),
    )
    chunks = cursor.fetchall()

    cursor.execute(
        "SELECT filename FROM reports WHERE id = %s", (report_id,)
    )
    row = cursor.fetchone()
    report_name = row[0] if row else str(report_id)

    if intent == "STRUCTURE":
        return build_structure_context(report_name, chunks)

    retriever = load_retriever()

    # ── Поиск по номеру раздела ───────────────────────────────────────────────
    # Ищем явное указание на раздел/пункт (например: «в разделе 3.1», «пункт 2», «раздел 1.1»)
    # или формат «X.Y» (например, «2.2»), исключая 4-значные года (2024, 2025)
    section_pattern = re.compile(
        r"(?:раздел[а-я]*|пункт[а-я]*|п\.)\s*(\d+(?:\.\d+)*)|\b([1-9]\d{0,1}\.\d+(?:\.\d+)*)\b",
        re.IGNORECASE
    )
    section_match = section_pattern.search(user_query)
    is_explicit_section_query = (
        section_match is not None and any(w in user_query.lower() for w in ("раздел", "пункт", "п."))
    )

    results = []
    if is_explicit_section_query and section_match:
        section = section_match.group(1) or section_match.group(2)
        print(f"\nSECTION SEARCH: {section}\n")

        raw_results = retriever.search_by_section(section, report_ids=[report_id])
        filtered = []
        for r in raw_results:
            fragment = extract_section_fragment(r["chunk_text"], section)
            filtered.append({
                "score": r["score"],
                "report_id": r["report_id"],
                "chunk_order": r["chunk_order"],
                "chunk_text": fragment,
            })

        results = _deduplicate(filtered, key_fn=lambda r: r["chunk_text"][:1000])

    # ── Семантический и табличный поиск ───────────────────────────────────────
    if not results:
        table_results = []
        if is_table_query(user_query):
            table_retriever = load_table_retriever()
            # Запрос с запасом
            table_results = table_retriever.search(
                user_query, report_ids=[report_id], top_k=100
            )
            print("\nTABLE SEARCH\n")
            for r in table_results:
                print(f"  table chunk={r['chunk_order']} score={r['score']:.4f}")

        # Аналогично — берём с запасом, чтобы после фильтрации осталось достаточно
        text_results = retriever.search(
            user_query, report_ids=[report_id], top_k=100
        )

        results = [
            {
                "score": r["score"],
                "report_id": r["report_id"],
                "chunk_order": r["chunk_order"],
                "chunk_text": r["table_text"],
            }
            for r in table_results
        ]
        results.extend(text_results)

        # Убеждаемся, что все результаты принадлежат нужному отчёту
        results = [r for r in results if r["report_id"] == report_id]

        results = _deduplicate(
            results,
            key_fn=lambda r: str(r["chunk_order"]) + r["chunk_text"][:500],
        )
        # Отбираем наиболее релевантные чанки (топ-3 для точечных, топ-5 для общих)
        top_k_rerank = 5 if intent in ("ANALYZE", "ANOMALIES", "STRUCTURE") else 3
        results = rerank_results(user_query, results, top_k=top_k_rerank)

        print("\nRERANK RESULTS")
        for r in results:
            print(f"  chunk={r['chunk_order']} rerank={r['rerank_score']:.4f}")
        print()

    print("=" * 50)
    print("QUERY:", user_query)
    print("REPORT:", report_name)
    for r in results:
        print(
            f"  chunk={r['chunk_order']}"
            f"  score={r.get('score', 0):.4f}"
            f"  rerank={r.get('rerank_score', 0):.4f}"
        )
    print("=" * 50)

    return faiss_results_to_context(report_name, results)


def get_analysis_from_yandexgpt(llm, report_ids, user_query):
    """Главная точка входа для анализа запроса пользователя через YandexGPT.
    Определяет intent, собирает контекст по каждому из выбранных документов,
    формирует промпт и получает ответ от языковой модели.
    Из сырого вывода удаляет блоки размышлений (<think> и текст до маркера ###ОТВЕТ###).
    Возвращает финальный текст ответа."""
    intent = get_intent(llm, user_query)

    conn = get_db_connection()
    cursor = conn.cursor()
    contexts = []

    for report_id in report_ids:
        try:
            ctx = _collect_context_for_report(report_id, user_query, intent, cursor)
            if ctx:
                contexts.append(ctx)
        except Exception as exc:
            print(f"Ошибка при обработке report_id={report_id}: {exc}")

    conn.close()

    full_context = "\n\n".join(contexts)

    print("SELECTED REPORT IDS:", report_ids)
    print("CONTEXT LENGTH:", len(full_context))

    if not full_context.strip():
        return "По выбранным документам релевантная информация не найдена."

    intent_instruction = _INTENT_INSTRUCTIONS.get(intent, _INTENT_INSTRUCTIONS["GENERAL"])
    prompt = _SYSTEM_PROMPT.format(
        intent=intent,
        intent_instruction=intent_instruction,
        context=full_context,
        query=user_query,
    )

    print()
    print("=" * 80)
    print("FINAL CONTEXT")
    print("=" * 80)
    print(full_context[:5000])
    print("=" * 80)
    print()

    out = llm(prompt, max_tokens=2048, temperature=0.1, repeat_penalty=1.1)
    raw_answer = out["choices"][0]["text"]
    print(f"\nRAW MODEL OUTPUT:\n{raw_answer}\n")

    # Убираем блоки <think>...</think>
    raw_answer = re.sub(r"<think>.*?</think>", "", raw_answer, flags=re.DOTALL)

    # Убираем маркер ###ОТВЕТ### (с любыми пробелами, двоеточиями и регистрами)
    parts = re.split(r"###\s*ОТВЕТ\s*[:#]*", raw_answer, flags=re.IGNORECASE)
    if len(parts) > 1:
        raw_answer = parts[-1]

    # Подчищаем остаточные маркеры
    raw_answer = re.sub(r"###\s*[ОO][ТT]?[ВB]?[ЕE]?[ТT]?\s*[:#]*", "", raw_answer, flags=re.IGNORECASE)

    return raw_answer.strip()


# Универсальные алиасы для вызова анализа
get_analysis = get_analysis_from_yandexgpt
get_analysis_from_qwen = get_analysis_from_yandexgpt