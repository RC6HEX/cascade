# Cascade

> Автономная команда разработки ПО. На входе — бизнес-требования и бизнес-процесс. На выходе — рабочее веб-приложение, документация, тесты.

Pipeline:

```
БТ + БП + Features
   ↓
Use Cases  →  НФТ  →  ФТ  →  Код  →  Тесты  →  README
   (с трассировкой ID между уровнями)
```

Каждый артефакт нижнего уровня ссылается на источник из верхнего: `ФТ-04` → `БТ-04`. Это и есть «каскад».

---

## Быстрый старт (3 команды)

```bash
git clone https://github.com/<USER>/cascade.git
cd cascade
bash install.sh           # на Windows: powershell -ExecutionPolicy Bypass -File install.ps1
```

Затем открой `.env` и впиши свой ключ от OpenRouter:

```ini
OPENROUTER_API_KEY=sk-or-v1-...
```

Получить ключ: <https://openrouter.ai/keys> (есть free-tier).

И запусти веб-интерфейс:

```bash
# Linux / macOS
.venv/bin/python -m ui

# Windows
.venv\Scripts\python.exe -m ui
```

Открой в браузере: <http://127.0.0.1:8000>

---

## Что в веб-интерфейсе

- **3 готовых пресета** (Веб-калькулятор / Таск-трекер / Конвертер валют) — нажми и БТ/БП/Features подгрузятся одним кликом.
- **Свободный ввод** — три текстовых поля для своих БТ/БП/Features.
- **Live-прогресс через SSE**: 6 шагов пайплайна обновляются в реальном времени, видишь время каждого шага.
- **Settings (⚙)**: меняй модели на лету — отдельно для дешёвых шагов (документация) и для тяжёлых (код, ФТ). Выбор сохраняется в браузере.
- **Файловое дерево** с превью и **скачиванием в ZIP** после генерации.

---

## Как пользоваться без UI (CLI)

```bash
# Готовые задания
python -m generator --task task_a    # калькулятор
python -m generator --task task_b    # таск-трекер
python -m generator --task task_c    # конвертер валют

# Своё задание
python -m generator \
  --input ./input/my_task \
  --output ./output/my_task

# С другими моделями
python -m generator --task task_b \
  --model-fast "qwen/qwen-2.5-7b-instruct" \
  --model-smart "deepseek/deepseek-chat-v3-0324"
```

Для своего задания создай папку `input/my_task/` и положи туда:

- `business_requirements.md` (обязательно)
- `business_process.md` (обязательно)
- `features.md` (опционально — UI-стиль, ограничения, название)

---

## Поддерживаемые модели через OpenRouter

Все они уже есть в дропдауне Settings. Цены — за 1M токенов вход / выход.

| ID | Применение | Контекст | $ in / out |
|---|---|---|---|
| `deepseek/deepseek-chat-v3-0324` | Дефолт **smart** (код, ФТ) | 64K | 0.27 / 1.10 |
| `deepseek/deepseek-r1` | Reasoning (логика, граничные случаи) | 64K | 0.55 / 2.19 |
| `qwen/qwen-2.5-72b-instruct` | Дефолт **fast** (документация) | 32K | 0.13 / 0.40 |
| `qwen/qwen-2.5-7b-instruct` | Стресс-тест на слабой модели | 32K | 0.04 / 0.10 |
| `qwen/qwen-2.5-coder-32b-instruct` | Заточен под код | 32K | 0.07 / 0.16 |
| `meta-llama/llama-3.3-70b-instruct` | Универсальная Meta LLM | 128K | 0.13 / 0.40 |
| `meta-llama/llama-3.2-3b-instruct` | Самая мелкая, для отладки пайплайна | 128K | 0.02 / 0.04 |
| `mistralai/mistral-small-3.2-24b-instruct` | Компактная и быстрая | 96K | 0.10 / 0.30 |
| `minimax/minimax-01` | 1M контекст — для больших БТ | 1M | 0.20 / 1.10 |
| `google/gemini-2.5-flash` | Хороший баланс | 1M | 0.30 / 2.50 |
| `google/gemini-2.5-pro` | Максимальное качество | 1M | 1.25 / 10.00 |
| `anthropic/claude-3.5-haiku` | Стабильно, но дороже | 200K | 0.80 / 4.00 |

> Технически работает любой OpenRouter-совместимый ID — впиши в `.env` (`MODEL_FAST=...`, `MODEL_SMART=...`) или передай через `--model-fast/--model-smart`. UI просто выводит этот список как удобный.

**Стоимость одного полного прогона** (6 шагов, ~25K input + 30K output tokens) — ориентир:

- DeepSeek V3 + Qwen 72B (дефолт): ~$0.05
- Llama 3.3 70B + Qwen 7B: ~$0.02
- Gemini Pro + Flash: ~$0.30
- Claude Haiku + Mistral Small: ~$0.15

---

## Структура артефактов на выходе

```
output/<task>/
├── docs/
│   ├── use-cases.md            # юз-кейсы со ссылками на БТ
│   ├── non-functional-req.md   # НФТ с измеримыми критериями
│   └── functional-req.md       # ФТ со ссылками БТ → UC → ФТ
├── src/
│   ├── index.html              # точка входа
│   ├── styles.css              # стили
│   ├── app.js                  # bootstrap
│   └── <feature>.js            # модули по фичам
├── tests/
│   └── *.test.js               # Vitest unit-тесты
├── package.json                # для npm test
├── README.md                   # инструкция к сгенерированному приложению
└── _generator_log.md           # учёт токенов и моделей
```

---

## Архитектура генератора

```
cascade/
├── generator/
│   ├── __main__.py             # CLI: python -m generator
│   ├── config.py               # .env, реестр моделей
│   ├── llm.py                  # обёртка Gemini / OpenRouter + retry
│   ├── parser.py               # парсер multi-file LLM output
│   ├── pipeline.py             # каскад БТ → ФТ → код
│   ├── io_utils.py             # чтение/запись артефактов
│   └── prompts/                # системные промпты с персонами
│       ├── use_cases.md        # «Senior Business Analyst, 15 лет опыта…»
│       ├── nfr.md              # «Solution Architect…»
│       ├── fr.md               # «техлид + системный аналитик…»
│       ├── code.md             # «Senior Frontend Engineer L7…»
│       ├── tests.md            # «QA-инженер, ломает прод раньше юзеров…»
│       └── readme.md           # «технический писатель…»
├── ui/
│   ├── __main__.py             # запуск: python -m ui
│   ├── server.py               # FastAPI + SSE
│   └── static/                 # HTML / CSS / JS фронтенда
├── input/
│   ├── task_a/                 # калькулятор
│   ├── task_b/                 # таск-трекер
│   └── task_c/                 # конвертер валют
├── install.sh / install.ps1
├── requirements.txt
├── .env.example
└── README.md
```

### Ключевые архитектурные решения

- **Без LangChain / CrewAI**. Pipeline линейный, контроль над промптами и retry важнее «магии» агентов.
- **Multi-file output через markdown-маркеры** (`### FILE: path/to/file`). Гарантирует чистое разделение, никаких JSON-escape проблем при генерации кода.
- **Per-step model selection**. Текстовые шаги — на дешёвой модели, кодогенерация и ФТ — на сильной. Можно переопределить через UI или CLI без рестарта.
- **Стабильность через retry с экспоненциальным бэкоффом** (см. `llm.py`). LLM может временно вернуть пустой ответ — клиент повторит до 3 раз.
- **Персоны в промптах**. Каждый шаг — отдельный «эксперт» с кодексом правил. Это резко поднимает качество: модель пишет ФТ как продакт, код как сеньор, тесты как параноидальный QA.
- **Жёсткие чек-листы в промптах**: «перед отправкой проверь что у каждого ФТ есть Источник», «не пиши число с запятой в `<input type=number>`», и т.п. Это правит конкретные баги, найденные на ранних прогонах.

---

## Endpoints веб-сервера

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/` | UI |
| `GET` | `/api/health` | статус и текущие модели |
| `GET` | `/api/presets` | список пресетов A/B/C |
| `GET` | `/api/preset/{name}` | контент БТ+БП+Features пресета |
| `GET` | `/api/models` | реестр моделей для дропдауна |
| `POST` | `/api/jobs` | старт генерации, возвращает `{id}` |
| `GET` | `/api/jobs/{id}/stream` | SSE-поток прогресса |
| `GET` | `/api/jobs/{id}/files` | дерево файлов |
| `GET` | `/api/jobs/{id}/file?path=` | содержимое файла |
| `GET` | `/api/jobs/{id}/zip` | скачать всё как ZIP |

---

## Требования

- Python 3.11+ (тестировали на 3.13)
- Любая OS: Linux, macOS, Windows
- API-ключ от **OpenRouter** (или Gemini, если хочешь напрямую)
- (Опционально) Node.js 18+ — только если хочешь запускать сгенерированные `npm test` тесты

---

## Альтернативный провайдер: прямой Gemini

Если хочешь использовать Gemini API напрямую (минуя OpenRouter), в `.env`:

```ini
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...
MODEL_FAST=gemini-2.5-flash
MODEL_SMART=gemini-2.5-pro
```

Получить ключ: <https://aistudio.google.com/apikey>

---

## FAQ

**Q: Как добавить свою модель в дропдаун?**
A: Открой `generator/config.py`, добавь запись в `OPENROUTER_MODELS`, перезапусти сервер. Или просто впиши ID в `.env` (`MODEL_SMART=...`) — тогда она появится в дропдауне сверху.

**Q: Что если генерация падает на половине?**
A: Перезапусти. Pipeline идемпотентный, `output/<task>/` каждый раз очищается. Если падает повторно — посмотри в `output/<task>/_generator_log.md` и в логах сервера.

**Q: Можно ли запускать без интернета?**
A: Нет, все модели — облачные. Оффлайн-режим возможен только если поднимешь свой OpenRouter-совместимый прокси (например, через Ollama + LiteLLM).

**Q: Есть ли self-check / refinement mode?**
A: На roadmap. Сейчас pipeline — линейный одиночный проход. Self-check цикл (генерация → валидация → переделка) и режим точечных доработок — следующая итерация.

**Q: Где спрятались мои API-ключи?**
A: Только в `.env`. Файл в `.gitignore`. В коммиты не попадает. Если случайно закоммитил — отзови ключ и сгенерируй новый.

---

## Лицензия

MIT
