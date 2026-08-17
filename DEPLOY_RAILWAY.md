# ntFAST — Deploy to Railway.app

## Шаг 1: GitHub

Залить проект на GitHub (приватный репозиторий):

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/ntfast.git
git branch -M main
git push -u origin main
```

---

## Шаг 2: Railway.app

1. Зайди на https://railway.app и войди через GitHub
2. Нажми **"New Project"**

---

## Шаг 3: PostgreSQL

1. В проекте нажми **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Готово — Railway автоматически создаст базу данных
3. Скопируй `DATABASE_URL` из вкладки **Variables** (понадобится для backend)

---

## Шаг 4: Redis

1. Нажми **"+ New"** → **"Database"** → **"Redis"**
2. Скопируй `REDIS_URL` из вкладки **Variables**

---

## Шаг 5: Backend

1. Нажми **"+ New"** → **"GitHub Repo"** → выбери свой ntFAST репозиторий
2. Railway найдёт корневой `railway.json` и сам возьмёт `backend/Dockerfile`,
   прогонит `alembic upgrade head` при старте и поднимет uvicorn на `$PORT`.
   Root Directory оставь `/` — больше в Settings ничего править не нужно.
3. Перейди во вкладку **Variables** и добавь:

```
DATABASE_URL=<кнопка Reference → Postgres.DATABASE_URL>
SECRET_KEY=<сгенерируй: python -c "import secrets; print(secrets.token_hex(32))">
BACKEND_CORS_ORIGINS=["https://<домен-фронта>.up.railway.app"]
DEBUG=false

# За обратным прокси Railway — иначе rate-limiter обходится подменой X-Forwarded-For.
# startCommand уже поднимает uvicorn с --proxy-headers --forwarded-allow-ips=*.
TRUST_PROXY_HEADERS=true

# Read-only demo без модели: LLM-путь выключен (на Railway нет GPU/Ollama).
# Агент-заключение для demo предзаписывается сидером, а не считается вживую.
AI_ENRICHMENT_ENABLED=false

# Гостевой аккаунт стенда: видит всё, но загрузка/удаление/правки → 403.
DEMO_READONLY_EMAILS=demo@ntfast.kz
```

> Read-only demo не требует Celery и Redis — загрузки нет, всё уже посчитано
> сидером (Шаг 8). CELERY_*/REDIS_* нужны только для полного стенда с загрузкой.

> Совет: для `DATABASE_URL` жми **"Add Reference"** — Railway подставит связь
> с Postgres-сервисом автоматически.

5. Перейди в **Settings** → **Networking** → **Generate Domain**
6. Скопируй домен бэкенда (например: `ntfast-backend-production-abc123.up.railway.app`)

---

## Шаг 6: Frontend

1. Нажми **"+ New"** → **"GitHub Repo"** → тот же репозиторий
2. Перейди в **Settings**:
   - **Root Directory**: `frontend`
   - **Builder**: Dockerfile
   - **Dockerfile Path**: `Dockerfile.railway`
3. Во вкладке **Variables** добавь:

```
VITE_API_URL=https://ntfast-backend-production-abc123.up.railway.app
```

> Замени на реальный домен бэкенда из Шага 5!

4. **Settings** → **Networking** → **Generate Domain**
5. Это будет ссылка для доступа к ntFAST!

---

## Шаг 7: Обновить CORS

После создания frontend домена, вернись в **Backend** → **Variables** и обнови:

```
BACKEND_CORS_ORIGINS=["http://localhost:5173","https://ntfast-frontend-production-xyz.up.railway.app"]
```

Или просто добавь переменную — Railway подхватит автоматически через `RAILWAY_ENVIRONMENT`.

---

## Шаг 8: Засев demo (read-only стенд)

Стенд поднимается на пустой базе — нужно создать гостевой аккаунт и
предзагрузить синтетические анализы одним прогоном. Сидер идёт по тому же
пути, что и настоящая загрузка, поэтому отчёт выглядит как боевой.

С машины, где стоят зависимости бэкенда, укажи `DATABASE_URL` от Railway
(вкладка Postgres → Variables → `DATABASE_URL`, публичный URL) и запусти:

```bash
DATABASE_URL="postgresql://...railway..." python scripts/seed_demo.py
```

Создаст `demo@ntfast.kz` (пароль по умолчанию `ntFASTdemo!2026`,
переопределяется через `DEMO_EMAIL`/`DEMO_PASSWORD`) и три анализа: чистый
(риск низкий), мошеннический (высокий) и CSV. Заключение агента у каждого
предзаписано — на демо модель не вызывается. Аккаунт уже read-only через
`DEMO_READONLY_EMAILS` из Шага 5: гость смотрит, но не грузит и не удаляет.

`--force` пересоздаёт анализы демо-юзера, если нужно обновить.

---

## Шаг 9: Проверка

1. Открой домен фронтенда в браузере
2. Войди как `demo@ntfast.kz`
3. Открой любой из трёх анализов — все пять вкладок, включая заключение
4. Убедись, что загрузка выписки отдаёт 403 (демо только для просмотра)

---

## Бесплатный лимит

- Railway даёт **$5 бесплатных кредитов** при привязке карты (Trial)
- Read-only demo — 3 сервиса (Postgres + Backend + Frontend), без Celery/Redis:
  триал тратится медленнее, чем на полном стенде с загрузкой
- Без карты — **500 часов/месяц** (хватит на 1 сервис)

---

## Приватность

- Домен рандомный — никто не найдет через поиск
- `<meta name="robots" content="noindex, nofollow">` — Google не индексирует
- `X-Robots-Tag: noindex, nofollow` в nginx — дополнительная защита
- Репозиторий на GitHub — приватный
