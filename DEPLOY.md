# Деплой

Все три демки лежат в папке `deploy/` и готовы к публикации как статический сайт. Выбери любой из трёх вариантов.

## Вариант 1: GitHub Pages (рекомендуется)

В репо уже настроен GitHub Actions workflow `.github/workflows/pages.yml`, который автоматически публикует `deploy/` на каждый push в `main`.

```bash
# 1. Создай пустой репо на GitHub (через сайт или gh CLI)
#    например: https://github.com/<ты>/autonomous-team

# 2. Привяжи remote и запушь
git remote add origin https://github.com/<ты>/autonomous-team.git
git push -u origin main

# 3. На GitHub: Settings → Pages → Source: GitHub Actions
#    Workflow запустится автоматически на push.

# 4. Через 1-2 минуты сайт будет на:
#    https://<ты>.github.io/autonomous-team/
```

## Вариант 2: Netlify (одна кнопка)

1. Зайди на https://app.netlify.com/start
2. Подключи GitHub-репо (или drag-and-drop папку `deploy/`)
3. Netlify прочитает `netlify.toml`, опубликует `deploy/`
4. Получишь URL вида `https://<random>.netlify.app`

CLI-вариант:

```bash
npm i -g netlify-cli   # требует Node.js
netlify deploy --dir=deploy --prod
```

## Вариант 3: Vercel

1. https://vercel.com/new → импорт репо
2. Vercel прочитает `vercel.json`
3. Готово

CLI-вариант:

```bash
npm i -g vercel
vercel deploy deploy --prod
```

## Локальный запуск (без деплоя)

```bash
# Из корня проекта
python -m http.server 8765 --directory deploy
# Открыть http://localhost:8765/
```

## Обновление демок

После любых изменений в `input/` или промптах:

```bash
# 1. Перегенерировать
python -m generator --task task_a
python -m generator --task task_b
python -m generator --task task_c

# 2. Скопировать в deploy/
cp -r output/task_a deploy/
cp -r output/task_b deploy/
cp -r output/task_c deploy/

# 3. Закоммитить
git add deploy/
git commit -m "regenerate demos"
git push
```

## ВАЖНО: безопасность

- `.env` НЕ попадает в репо (он в `.gitignore`)
- В коммите только `.env.example` с плейсхолдерами
- Перед публикацией репо ещё раз проверь:
  ```bash
  git log --all --full-history -- .env       # должно быть пусто
  git ls-files | grep -i env                 # должно быть только .env.example
  ```
