# ntFAST
### Financial Analysis System for Transactions

**Версия:** 2.0.0
**Дата обновления:** 5 апреля 2026
**Автор:** Нурдаулет

---

## О проекте

**ntFAST** — корпоративная платформа для анализа финансовых транзакций и выявления мошенничества, разработанная для Республики Казахстан.

### Ключевые возможности

- **FraudEngine v4** — 15+ модулей детекции мошенничества (графовый анализ, поведенческий анализ, NLP, структурирование, velocity-проверки и др.)
- **Умный парсинг** — автоматический разбор банковских выписок (PDF, CSV, XLSX, XLS), включая Kaspi Bank
- **Мультиязычность** — русский, казахский, английский
- **Real-time мониторинг** — WebSocket обновления прогресса анализа
- **Email верификация** — подтверждение регистрации по email
- **Управление пользователями** — роли (admin/user), блокировка, история входов
- **Мониторинг активности** — автоматический выход при неактивности
- **PDF-отчёты** — генерация отчётов через ReportLab
- **Тёмная/светлая тема**
- **Часовой пояс** — Asia/Almaty

---

## Технологический стек

| Компонент | Технология |
|-----------|-----------|
| **Backend** | FastAPI + Python 3.11 |
| **Frontend** | React 18 + TypeScript 5 + Vite 5 |
| **База данных** | PostgreSQL 16 (основная) / SQLite (fallback) |
| **Кэш / Очереди** | Redis 7 + Celery |
| **UI** | Tailwind CSS 3 + Framer Motion + Recharts |
| **Деплой** | Railway / Docker Compose |

---

## Структура проекта

```
FinancialAnalysisSystem/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/                # API роутеры
│   │   │   ├── auth.py         # /api/auth — авторизация, JWT
│   │   │   ├── email_verification.py  # /api/email-verification
│   │   │   ├── users.py        # /api/users — управление пользователями
│   │   │   ├── analyses.py     # /api/analyses — анализы
│   │   │   ├── transactions.py # /api/transactions
│   │   │   ├── subjects.py     # /api/subjects — субъекты
│   │   │   ├── bank_analysis.py    # /api/bank — банковские выписки
│   │   │   ├── pdf_analysis.py     # /api/pdf-analysis
│   │   │   ├── kaspi_analysis.py   # Kaspi Bank анализ
│   │   │   └── websocket.py    # /ws — WebSocket
│   │   ├── core/               # Конфигурация, БД, безопасность
│   │   ├── models/             # SQLAlchemy модели
│   │   ├── schemas/            # Pydantic схемы
│   │   ├── services/
│   │   │   ├── fraud/          # FraudEngine v4 (15+ модулей)
│   │   │   │   ├── engine.py           # Главный движок
│   │   │   │   ├── graph_analysis.py   # Графовый анализ связей
│   │   │   │   ├── behavioral.py       # Поведенческий анализ
│   │   │   │   ├── nlp_analyzer.py     # NLP анализ описаний
│   │   │   │   ├── velocity.py         # Velocity-проверки
│   │   │   │   ├── structuring.py      # Детекция структурирования
│   │   │   │   ├── pattern_detector.py # Паттерны мошенничества
│   │   │   │   ├── duplicate_detector.py # Дубликаты транзакций
│   │   │   │   ├── merchant_risk.py    # Риск контрагентов
│   │   │   │   ├── night_transactions.py # Ночные транзакции
│   │   │   │   ├── round_amounts.py    # Круглые суммы
│   │   │   │   ├── cross_reference.py  # Перекрёстные проверки
│   │   │   │   ├── account_profiler.py # Профилирование счетов
│   │   │   │   ├── profile_mismatch.py # Несоответствие профилей
│   │   │   │   └── models.py           # ML модели
│   │   │   ├── bank_analyzer/  # Анализатор банковских выписок
│   │   │   ├── kaspi_analyzer/ # Kaspi Bank интеграция
│   │   │   ├── pdf_analyzer/   # PDF анализ + fraud detector
│   │   │   ├── parsers.py      # PDF, CSV, XLSX парсеры
│   │   │   ├── smart_parser.py # Умный парсинг с автоопределением
│   │   │   ├── auth_service.py
│   │   │   ├── email_service.py
│   │   │   ├── user_service.py
│   │   │   ├── file_processing_service.py
│   │   │   ├── login_history_service.py
│   │   │   ├── websocket_manager.py
│   │   │   └── storage.py
│   │   └── main.py             # Точка входа FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env
│
├── frontend/                   # React SPA
│   ├── src/
│   │   ├── pages/              # Dashboard, Analyses, Settings, Landing
│   │   ├── components/         # UI компоненты
│   │   ├── context/            # Auth, Theme, Language контексты
│   │   ├── services/           # API клиент (axios)
│   │   ├── hooks/              # useActivityMonitor, useAnalysisProgress
│   │   ├── locales/            # ru.json, en.json, kk.json
│   │   └── i18n.ts
│   ├── Dockerfile
│   ├── Dockerfile.railway
│   └── package.json
│
├── docker-compose.yml          # PostgreSQL 16 + Redis 7 + Backend + Frontend
├── scripts/                    # Вспомогательные скрипты (генераторы документов)
└── README.md
```

---

## Быстрый старт

### Вариант 1: Docker Compose (рекомендуется)

```bash
git clone https://github.com/your-repo/FinancialAnalysisSystem.git
cd FinancialAnalysisSystem

# Запустить все сервисы
docker-compose up -d

# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

### Вариант 2: Локальный запуск

**Требования:**
- Python 3.11+
- Node.js 18+
- PostgreSQL 16 (или SQLite для разработки)
- Redis 7 (для Celery задач)

**Backend:**
```bash
cd backend

# Виртуальное окружение
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/macOS

# Зависимости
pip install -r requirements.txt

# Настроить .env (см. раздел "Переменные окружения")

# Запустить
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend

# Зависимости
npm install

# Запустить dev-сервер
npm run dev
# Откроется на http://localhost:5173
```

### Вариант 3: Railway (Production)

Проект настроен для деплоя на Railway:
- **Backend** — Python сервис с Dockerfile
- **Frontend** — Node.js сервис с Dockerfile.railway
- **PostgreSQL** — Railway managed PostgreSQL
- **Redis** — Railway managed Redis

Необходимые переменные Railway:
- `DATABASE_URL` — автоматически от Railway PostgreSQL
- `REDIS_HOST`, `REDIS_PORT` — автоматически от Railway Redis
- `VITE_API_URL` — URL backend-сервиса (для frontend, задаётся ДО сборки)
- `SECRET_KEY` — секрет для JWT
- `BACKEND_CORS_ORIGINS` — URL frontend-сервиса

---

## Тестовый пользователь

| Поле | Значение |
|------|----------|
| Email | admin@example.com |
| Пароль | admin123 |
| Роль | admin |

---

## API

**Базовый префикс:** `/api`

| Endpoint | Описание |
|----------|----------|
| `POST /api/auth/login` | Авторизация, получение JWT токена |
| `POST /api/auth/register` | Регистрация нового пользователя |
| `GET /api/auth/me` | Текущий пользователь |
| `POST /api/email-verification/send-code` | Отправка кода верификации |
| `POST /api/email-verification/verify-code` | Проверка кода |
| `GET /api/users/` | Список пользователей (admin) |
| `GET /api/analyses/` | Список анализов |
| `GET /api/analyses/stats` | Статистика анализов |
| `POST /api/analyses/upload` | Загрузка файла для анализа |
| `GET /api/transactions/` | Список транзакций |
| `POST /api/bank/upload` | Загрузка банковской выписки |
| `POST /api/pdf-analysis/upload` | Загрузка PDF для анализа |
| `GET /health` | Проверка здоровья сервиса |
| `WS /ws` | WebSocket (прогресс анализа, активность) |

Swagger UI: `http://localhost:8000/docs`

---

## Модули FraudEngine

| Модуль | Описание |
|--------|----------|
| `graph_analysis` | Графовый анализ связей между счетами |
| `behavioral` | Поведенческий анализ паттернов пользователя |
| `nlp_analyzer` | NLP анализ описаний транзакций |
| `velocity` | Проверка скорости/частоты транзакций |
| `structuring` | Детекция структурирования (дробление сумм) |
| `pattern_detector` | Обнаружение известных схем мошенничества |
| `duplicate_detector` | Поиск дублирующихся транзакций |
| `merchant_risk` | Оценка риска контрагентов |
| `night_transactions` | Анализ ночных транзакций |
| `round_amounts` | Детекция подозрительных круглых сумм |
| `cross_reference` | Перекрёстная проверка данных |
| `account_profiler` | Профилирование поведения счёта |
| `profile_mismatch` | Несоответствие профилю клиента |

Каждый модуль возвращает оценку риска (0-10), итоговый `risk_score` — взвешенная агрегация всех модулей.

---

## Поддерживаемые форматы файлов

| Формат | Описание |
|--------|----------|
| PDF | Банковские выписки (парсинг через pdfplumber) |
| CSV | Табличные данные транзакций |
| XLSX | Excel файлы |
| XLS | Старый формат Excel |

Поддержка банков: **Kaspi Bank** (специализированный анализатор), универсальный парсинг для других банков.

---

## Переменные окружения

### Backend (.env)

```env
# База данных (PostgreSQL рекомендуется)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/financial_analysis

# JWT секрет
SECRET_KEY=your-secret-key-change-in-production

# CORS
BACKEND_CORS_ORIGINS=["http://localhost:5173"]

# Email (SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
USE_REAL_EMAIL=true
REQUIRE_EMAIL_VERIFICATION=false

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Приложение
PROJECT_NAME=ntFAST
API_PREFIX=/api
```

### Frontend

```env
VITE_API_URL=http://localhost:8000
```

> **Важно:** `VITE_API_URL` инлайнится при сборке (Vite). При деплое задавайте ДО `npm run build`.

---

## Устранение проблем

### Backend не запускается

```bash
# ModuleNotFoundError — установить зависимости
pip install -r requirements.txt

# Port 8000 занят
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Frontend не запускается

```bash
# Установить зависимости
npm install

# Очистить кэш
rm -rf node_modules/.vite
npm run dev
```

### CORS ошибки

Убедитесь что `BACKEND_CORS_ORIGINS` в backend .env содержит URL frontend (включая порт).

### WebSocket не подключается

1. Backend запущен
2. CORS настроен
3. Проверить DevTools -> Network -> WS

### Email не отправляются

На Railway порты SMTP (465/587) заблокированы. Используйте HTTP API провайдеры (Resend, Mailjet) или временно отключите верификацию: `REQUIRE_EMAIL_VERIFICATION=false`.

---

## Лицензия

ntFAST — Financial Analysis System for Transactions
Copyright 2025-2026
