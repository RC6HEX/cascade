# Автономная команда разработки ПО

Генератор приложений по бизнес-требованиям. Принимает на вход БТ + БП + Features (опц.), на выходе выдаёт готовое веб-приложение с документацией и тестами.

## Что делает

Каскад артефактов:

```
БТ + БП + Features
  → Use Cases (юз-кейсы)
  → НФТ (нефункциональные требования)
  → ФТ (функциональные требования с трассировкой к БТ/UC/Features)
  → Исходный код (HTML + CSS + Vanilla JS, модульный)
  → Тесты (Vitest)
  → README
```

Каждый ниже-уровневый артефакт ссылается на источники из верхнего уровня.

## Стек

- **Генератор:** Python 3.11+, httpx, dotenv
- **LLM-провайдер:** Google Gemini API (по умолчанию) или OpenRouter
- **Модели:** `gemini-2.5-flash` (документация) + `gemini-2.5-pro` (ФТ и код)
- **Стек генерируемого приложения:** HTML5 + CSS + Vanilla JavaScript ESM (без сборки, без зависимостей)
- **Тесты приложения:** Vitest + happy-dom

## Требования

- Python 3.11+
- API-ключ Google Gemini (https://aistudio.google.com/apikey) **или** OpenRouter (https://openrouter.ai/keys)
- (опц.) Node.js 18+ для запуска тестов сгенерированного приложения

## Установка

```bash
# 1. Клонируем репозиторий
git clone <repo>
cd autonomous-team

# 2. Создаём виртуальное окружение
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Зависимости
pip install -r requirements.txt

# 4. Настраиваем .env
copy .env.example .env
# открыть .env и вставить GEMINI_API_KEY
```

## Запуск

Есть **два режима** — CLI (для пакетной генерации) и веб-интерфейс (для интерактива и демо).

### 🌐 Веб-интерфейс

```bash
python -m ui                        # http://127.0.0.1:8000
python -m ui --port 9000 --reload   # другой порт + auto-reload
```

Что умеет:

- Подгружает 3 готовых пресета (Task A / B / C) одним кликом
- Принимает БТ + БП + Features текстом — без файлов
- Показывает **прогресс по шагам** в реальном времени через Server-Sent Events: каждый шаг — карточка с цветовой индикацией (running / done / error / skipped) и таймингом
- После генерации — дерево всех файлов с превью и **скачиванием в ZIP**
- Health-индикатор LLM-провайдера и моделей в шапке

### 💻 CLI

```bash
python -m generator --task task_a   # Веб-калькулятор
python -m generator --task task_b   # Таск-трекер
python -m generator --task task_c   # Конвертер валют
```

Результат окажется в `output/task_a/`, `output/task_b/`, `output/task_c/` соответственно.

### Своё задание

Создай папку `input/my_task/` и положи туда:
- `business_requirements.md` (обязательно)
- `business_process.md` (обязательно)
- `features.md` (опционально)

Запусти:

```bash
python -m generator --input ./input/my_task --output ./output/my_task
```

### Дополнительные опции

```bash
python -m generator --task task_a --no-tests          # без тестов
python -m generator --task task_a --no-use-cases      # без юз-кейсов
python -m generator --task task_a --provider openrouter
python -m generator --task task_a -v                  # verbose
```

## Структура проекта

```
autonomous-team/
├── generator/                     # Сам генератор (Python)
│   ├── __main__.py                # CLI entry
│   ├── config.py                  # Конфиг + модели
│   ├── llm.py                     # Обёртка над Gemini / OpenRouter
│   ├── parser.py                  # Парсер multi-file output
│   ├── io_utils.py                # Чтение/запись артефактов
│   ├── pipeline.py                # Каскад: БТ → ... → код
│   └── prompts/                   # Промпты к LLM
│       ├── use_cases.md
│       ├── nfr.md
│       ├── fr.md
│       ├── code.md
│       ├── tests.md
│       └── readme.md
├── input/
│   ├── task_a/                    # Веб-калькулятор: БТ, БП, features
│   ├── task_b/                    # Таск-трекер
│   └── task_c/                    # Конвертер валют
├── output/                        # Результат генерации (gitignored)
│   └── task_a/
│       ├── docs/
│       │   ├── use-cases.md
│       │   ├── non-functional-req.md
│       │   └── functional-req.md
│       ├── src/                   # Код приложения
│       ├── tests/                 # Vitest тесты
│       ├── package.json
│       ├── README.md
│       └── _generator_log.md      # Логи и токены
├── .env                           # ключи (gitignored)
├── .env.example
├── requirements.txt
└── README.md
```

## Стоимость одного прогона

С моделями по умолчанию (`gemini-2.5-flash` для лёгких шагов + `gemini-2.5-pro` для ФТ и кода):

- ~6 LLM-вызовов
- ~13 000 input tokens, ~14 000 output tokens
- **~$0.09 за полный прогон**

Можно сменить модели через `MODEL_FAST` / `MODEL_SMART` в `.env`.

## Архитектурные решения

- **Без LangChain/CrewAI.** Pipeline линейный, контроль над промптами и retry важнее «магии» агентов.
- **Multi-file output через markdown-маркеры** (`### FILE: path/to/file`). Гарантирует чистое разделение, никаких JSON-escape проблем.
- **Per-step model selection.** Текстовые шаги — на дешёвой Flash, кодогенерация и ФТ — на Pro.
- **Сохранение артефактов между шагами** — каждый следующий шаг получает все предыдущие как контекст. Это и обеспечивает трассировку.
- **Стабильность через retry с экспоненциальным бэкоффом** в `llm.py`.

## Что дальше (roadmap)

- [x] Этап 1: сквозной прогон БТ → код (Задание A)
- [x] Этап 2: документация + тесты (полный каскад)
- [ ] Этап 3:
  - [ ] Self-check цикл (валидация ФТ → регенерация)
  - [ ] Refinement mode (короткий комментарий → точечные правки)
  - [ ] CI на GitHub Actions

## Лицензия

MIT
