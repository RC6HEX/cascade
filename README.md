# Cascade

> Автономная команда разработки ПО. На входе — бизнес-требования и бизнес-процесс. На выходе — рабочее веб-приложение, документация, тесты.

```
БТ + БП + Features
   ↓
Use Cases  →  НФТ  →  ФТ  →  Код  →  Тесты  →  README
   (с трассировкой ID между уровнями + self-check на каждом шаге)
```

Каждый артефакт нижнего уровня ссылается на источник из верхнего: `ФТ-04` → `БТ-04`, `@implements ФТ-04` в коде. После каждого шага — **self-check**: автоматическая проверка, что все обязательные требования покрыты. Если нет — модель получает обратную связь и переделывает шаг.

---

## Быстрый старт (Linux/MacOs/Windows)

```bash
git clone https://github.com/RC6HEX/cascade.git
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

> **Альтернатива без скрипта-установщика** (если bash/ps1 не подходит):
> ```bash
> python -m venv .venv
> .venv/bin/pip install -r requirements.txt   # Windows: .venv\Scripts\pip
> cp .env.example .env                         # затем впиши OPENROUTER_API_KEY
> .venv/bin/python -m ui
> ```

---

## Что в веб-интерфейсе

- **3 готовых пресета** (Веб-калькулятор / Таск-трекер / Конвертер валют) — нажми и БТ/БП/Features подгрузятся одним кликом.
- **Свободный ввод** — три текстовых поля для своих БТ/БП/Features.
- **Live-прогресс через SSE**: 6 шагов пайплайна обновляются в реальном времени, видишь время каждого шага.
- **Streaming кода**: на шаге code код пишется прямо в UI на лету (не ждёшь 2 минуты с пустым экраном).
- **Параллелизм**: use_cases и nfr запускаются одновременно — экономит до 30 секунд на прогон.
- **Self-check визуально**: жёлтый пульсирующий шаг = модель сейчас исправляет недостачу. Зелёный = прошло с первого раза или после ретраев.
- **Settings (⚙)**: меняй модели на лету — отдельно для дешёвых шагов (документация) и для тяжёлых (код, ФТ). Внутри есть **продвинутый режим** с выбором модели на каждый из 6 шагов отдельно. Выбор сохраняется в браузере.
- **Refinement panel**: после успешной генерации внизу появляется поле «Доработка» — впиши короткий комментарий («поменяй цветовую схему на синюю», «добавь валидацию email») и модель применит точечные правки только к нужным файлам.
- **▶ Запустить**: одной кнопкой открывается iframe со сгенерированным приложением — реально работающим. 7+3=10 в QuickCalc прямо из UI генератора.
- **🔗 Трассировка**: матрица БТ → юз-кейсы → ФТ → файлы кода с `@implements`. Видно сколько ФТ покрыто кодом (например, 5/8 = 63%), и какие БТ остались без покрытия.
- **⏱ История**: панель с прошлыми генерациями (живёт после рестарта сервера). Открой любую — увидишь файлы, можешь снова запустить, сделать refinement или удалить.
- **💰 Cost estimator**: пока вводишь БТ — внизу панели live-оценка стоимости прогона на текущих моделях.
- **Файловое дерево** с превью и **скачиванием в ZIP** после генерации.

---

## Архитектура

```
┌──────────────┐
│  Web UI      │  FastAPI + SSE        ├── /api/jobs       (start)
│  (браузер)   │ ◄────────────────►    ├── /api/.../stream (SSE progress)
└──────┬───────┘                       └── /api/.../zip    (download)
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  generator/pipeline.py                                          │
│                                                                 │
│  ┌────────┐  ┌─────┐  ┌────┐  ┌──────┐  ┌───────┐  ┌────────┐ │
│  │use_cases│→│ nfr │→│ fr │→│ code │→│ tests │→│ readme │ │
│  └───┬────┘  └─────┘  └─┬──┘  └──┬───┘  └───────┘  └────────┘ │
│      │                  │        │                              │
│      │      ┌───────────▼────┐  ┌▼─────────────────┐            │
│      └─────►│ validators.py  │◄─┤ validators.py    │            │
│             │ ✓ БТ → UC      │  │ ✓ ФТ → @implements│            │
│             │ self-check loop│  │ self-check loop   │            │
│             └────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  generator/llm.py             │
│  Provider: OpenRouter / Gemini│
│  + retry с backoff на 429/5xx │
└──────────────────────────────┘
```

### Ключевые архитектурные решения

- **Без LangChain / CrewAI**. Pipeline линейный, контроль над промптами и retry важнее «магии» агентов.
- **Multi-file output через markdown-маркеры** (`### FILE: path/to/file`). Парсер проходит хедерами, не страдает от вложенных backticks в коде.
- **Self-check loops**. После шагов FR и code запускается валидатор: для FR — все ли обязательные БТ покрыты, для code — на каждое ли ФТ есть `@implements ФТ-XX`. Если нет — модели передаётся feedback и шаг переделывается. До 2 ретраев по умолчанию.
- **Per-step model selection**. Текстовые шаги — на дешёвой модели, кодогенерация и ФТ — на сильной. Можно переопределить через UI или CLI без рестарта.
- **Backoff по типу ошибки**: сетевые таймауты — экспоненциально, 429 — длиннее (15s → 30s → 60s), 5xx — средне.
- **Персоны в промптах**. Каждый шаг — отдельный «эксперт» с кодексом правил. Это резко поднимает качество: модель пишет ФТ как продакт, код как сеньор, тесты как параноидальный QA.

---

## Использование без UI (CLI)

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

# Без self-check (быстрее, но без валидации трассировки)
python -m generator --task task_a --no-self-check

# Больше ретраев self-check
python -m generator --task task_c --check-retries 3

# Refinement mode — точечная правка ранее сгенерированного приложения
python -m generator --refine output/task_a \
  --comment "поменяй цветовую схему на синюю"
# или: --comment "добавь валидацию email на форме"
```

Для своего задания создай папку `input/my_task/` и положи туда:

- `business_requirements.md` (обязательно)
- `business_process.md` (обязательно)
- `features.md` (опционально — UI-стиль, ограничения, название)

---

## Поддерживаемые модели через OpenRouter

Все они уже есть в дропдауне Settings (⚙). Цены — за 1M токенов вход / выход.

### Рекомендуемые комбинации

| Сценарий | Smart (код, ФТ) | Fast (документация) | Прогон, $ |
|---|---|---|---|
| **Дефолт — баланс** | `deepseek/deepseek-chat-v3-0324` | `qwen/qwen-2.5-72b-instruct` | ~$0.05 |
| **Минимум денег** | `deepseek/deepseek-chat-v3-0324` | `qwen/qwen-2.5-7b-instruct` | ~$0.02 |
| **Стресс-тест на слабой** | `qwen/qwen-2.5-coder-32b-instruct` | `meta-llama/llama-3.2-3b-instruct` | ~$0.01 |
| **Максимум качества** | `google/gemini-2.5-pro` | `google/gemini-2.5-flash` | ~$0.30 |
| **Reasoning-режим** | `deepseek/deepseek-r1` | `qwen/qwen-2.5-72b-instruct` | ~$0.10 |
| **Длинный контекст** | `minimax/minimax-01` | `minimax/minimax-01` | ~$0.15 |

### Полный список

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
└── _generator_log.md           # учёт токенов, моделей и self-check
```

`_generator_log.md` — полезный артефакт: видно, какая модель использовалась, сколько токенов потрачено, и какие шаги проходили self-check с первого раза, а какие — после ретраев.

---

## Структура проекта

```
cascade/
├── generator/
│   ├── __main__.py             # CLI: python -m generator
│   ├── config.py               # .env, реестр моделей
│   ├── llm.py                  # обёртка Gemini / OpenRouter + retry
│   ├── parser.py               # парсер multi-file LLM output
│   ├── pipeline.py             # каскад БТ → ФТ → код
│   ├── validators.py           # self-check: трассировка БТ → ФТ → @implements
│   ├── io_utils.py             # чтение/запись артефактов
│   └── prompts/                # системные промпты с персонами
│       ├── use_cases.md        # «Senior Business Analyst, 15 лет опыта»
│       ├── nfr.md              # «Solution Architect»
│       ├── fr.md               # «техлид + системный аналитик»
│       ├── code.md             # «Senior Frontend Engineer L7»
│       ├── tests.md            # «QA-инженер, ломает прод раньше юзеров»
│       └── readme.md           # «технический писатель»
├── ui/
│   ├── __main__.py             # запуск: python -m ui
│   ├── server.py               # FastAPI + SSE
│   └── static/                 # HTML / CSS / JS фронтенда
├── tests/                      # pytest для парсера и валидаторов
│   ├── test_parser.py
│   └── test_validators.py
├── input/
│   ├── task_a/                 # калькулятор
│   ├── task_b/                 # таск-трекер
│   └── task_c/                 # конвертер валют
├── install.sh / install.ps1
├── requirements.txt
├── .env.example
└── README.md
```

---

## Тесты генератора

```bash
.venv/bin/python -m pytest tests/ -v
```

23 теста на парсер и валидаторы. Покрывают:

- разбор multi-file LLM-вывода (включая разные header levels, backticks внутри кода, normalization путей);
- извлечение ID требований с разными вариантами тире (`-` / `‑`);
- проверку трассировки БТ → UC → ФТ → `@implements`;
- сортировку missing-списков численно (ФТ-02 перед ФТ-10).

---

## API веб-сервера

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
| `GET` | `/api/jobs/{id}/app/{path}` | static-сервинг сгенерированного приложения для iframe |
| `GET` | `/api/jobs/{id}/traceability` | матрица БТ → UC → ФТ → @implements |
| `GET` | `/api/jobs` | список всех job'ов с диска (для history panel) |
| `DELETE` | `/api/jobs/{id}` | удалить job вместе с артефактами |
| `POST` | `/api/jobs/{id}/refine` | refinement mode на готовом job |

### SSE-события

| Событие | Когда | Полезная нагрузка |
|---|---|---|
| `start` | старт пайплайна | `task`, `provider`, `model_fast`, `model_smart`, `total` |
| `step_start` | начало шага | `step`, `index`, `total` |
| `step_done` | шаг закончен успешно | `step`, `chars` или `file_count` |
| `self_check_retry` | self-check нашёл пропуски, переделываем | `step`, `attempt`, `missing` |
| `self_check_pass` | self-check прошёл | `step`, `attempt` |
| `self_check_fail` | self-check исчерпал ретраи | `step`, `missing` |
| `done` | пайплайн закончен | `files`, `calls`, `input_tokens`, `output_tokens` |
| `error` | критическая ошибка | `error` |

---

## Требования

- **Python 3.11+** (тестировали на 3.13)
- Любая OS: Linux, macOS, Windows
- API-ключ от **OpenRouter** (или Gemini, если хочешь напрямую)
- (Опционально) Node.js 18+ — только если хочешь запускать сгенерированные `npm test` тесты

---

## Альтернативный провайдер: Gemini напрямую

Если хочешь использовать Gemini API напрямую (минуя OpenRouter), в `.env`:

```ini
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...
MODEL_FAST=gemini-2.5-flash
MODEL_SMART=gemini-2.5-pro
```

Получить ключ: <https://aistudio.google.com/apikey>

---

## Troubleshooting

**❌ `OPENROUTER_API_KEY is missing`**
В корне проекта нет `.env` или в нём пустой `OPENROUTER_API_KEY`. Сделай `cp .env.example .env` и впиши ключ.

**❌ `LLM call failed: HTTP 401`**
Ключ невалидный или истёк. Зайди на <https://openrouter.ai/keys>, проверь.

**❌ `LLM call failed: HTTP 429` (после ретраев)**
Free tier OpenRouter имеет лимиты. Подожди минуту, или пополни баланс на $1 (это снимает большинство rate-limit'ов), или переключись на платную модель.

**❌ `No files found in LLM output`**
Модель проигнорировала формат `### FILE: ...`. Это бывает на очень слабых моделях (3B). Попробуй `qwen-2.5-72b` или `deepseek-chat-v3-0324` для шага code.

**❌ Self-check `missing_after_retries` для ФТ или БТ**
Модель не справилась полностью покрыть требования за 2 ретрая. Не критично — артефакты сгенерированы, просто часть БТ не получила ФТ. Поднимай `--check-retries 3` или используй более сильную smart-модель.

**❌ Тесты падают: `ImportError: ../src/...`**
Сгенерированные тесты ссылаются на файлы из `src/`. Запускай `npm test` из корня сгенерированного проекта, не из `tests/`.

**❌ В Windows: `'.venv/bin/python' не является внутренней или внешней командой`**
В Windows venv лежит в `.venv\Scripts\python.exe` (а не `.venv/bin/...`). Используй `install.ps1` или соответствующие пути.

---

## FAQ

**Q: Что делает self-check?**
A: После генерации ФТ парсит документ, ищет ссылки на БТ. Сравнивает с обязательными БТ из входа. Если что-то не покрыто — отправляет модели feedback вида «Не покрыто: БТ-04, БТ-07, добавь их». Делает до 2 ретраев. Аналогично для кода — проверяет, что на каждое ФТ есть `@implements ФТ-XX` в JSDoc.

**Q: Как добавить свою модель в дропдаун?**
A: Открой `generator/config.py`, добавь запись в `OPENROUTER_MODELS`, перезапусти сервер. Или просто впиши ID в `.env` (`MODEL_SMART=...`) — она появится в дропдауне сверху.

**Q: Что если генерация падает на половине?**
A: Перезапусти. Pipeline идемпотентный, `output/<task>/` каждый раз очищается. Если падает повторно — посмотри в `output/<task>/_generator_log.md` и в логах сервера.

**Q: Можно ли запускать без интернета?**
A: Нет, все модели — облачные. Оффлайн-режим возможен только если поднимешь свой OpenRouter-совместимый прокси (Ollama + LiteLLM).

**Q: Есть ли refinement mode (короткий комментарий → точечные правки)?**
A: На roadmap (Wave 2). Сейчас pipeline — линейный одиночный проход с self-check.

**Q: Где спрятались мои API-ключи?**
A: Только в `.env`. Файл в `.gitignore`. В коммиты не попадает. Если случайно закоммитил — отзови ключ и сгенерируй новый.

---

## Roadmap

- [x] Self-check loops (валидация трассировки БТ → ФТ → @implements)
- [x] Live model picker в UI
- [x] Persona-driven prompts
- [x] Внутренние тесты для парсера и валидаторов
- [x] **Refinement mode** — короткий комментарий → точечные правки (CLI `--refine` + UI панель)
- [x] **Параллелизация** шагов use_cases + nfr (оба зависят только от input)
- [x] **Streaming partial output** — код стримится в реальном времени в UI
- [x] **Per-step model override** — отдельная модель на каждый шаг, не только fast/smart
- [x] **▶ Live app preview** — запуск сгенерированного приложения в iframe прямо из UI
- [x] **🔗 Traceability matrix** — визуализация БТ → UC → ФТ → @implements (% покрытия)
- [x] **⏱ Job history persistence** — генерации переживают рестарт сервера
- [x] **💰 Cost estimator** — live оценка стоимости пока вводишь БТ
- [ ] Diff view для refinement (показ что именно изменилось)
- [ ] Web Workers для оффлайн-режима через локальный LLM

---

## Комманда RoboTrekUz

---

## Лицензия

MIT
