# ntFAST — карта проекта

Анализ банковских выписок и обнаружение финансового мошенничества для
следственных органов Казахстана. Читает выписку, нормализует транзакции,
прогоняет через 11 модулей скоринга и выдаёт объяснимую оценку риска 0–100.

**Прочитай этот файл перед любой правкой.** Он существует потому, что раньше на
вопрос «где код парсинга выписок» проект давал три разных верных ответа, и
правки уходили не в тот файл.

---

## Ядро — трогать осторожно

| Что | Где | Почему ядро |
|---|---|---|
| Антифрод-движок | `backend/app/services/fraud/` | 11 модулей, веса, калибровка под казахстанские реалии. Главная ценность проекта |
| Парсеры выписок | `backend/app/services/bank_analyzer/` | Знание реальных форматов Kaspi/Halyk/Binance на трёх языках |
| Бенчмарк | `scripts/benchmark.py` | Воспроизводимые метрики; на них строится доказательная база |
| Приватность | `backend/app/services/privacy/` | Гарантия, что ПД не покидают периметр |

---

## Единственный путь анализа

Развилок нет. Любой формат идёт одним маршрутом:

```
POST /api/analyses/upload  (единственная точка входа)
        │  создаёт Analysis(status=pending), кладёт файл, ставит задачу
        ▼
Celery: process_file_task                      tasks/file_processing_tasks.py
        ▼
FileProcessingService.process_file             services/file_processing_service.py
        ▼
BankAnalyzer.analyze()                         services/bank_analyzer/analyzer.py
        │
        ├─ BankDetector          определяет банк (для CSV — пропускается)
        ├─ parsers/{kaspi,halyk,binance,generic}
        ├─ TransactionCategorizer                services/kaspi_analyzer/categorizer.py
        ├─ FinancialAnalytics                    services/kaspi_analyzer/analytics.py
        ├─ enrich_transactions()                 services/enrichment/pipeline.py
        └─ FraudEngine.full_analysis()           services/fraud/engine.py
             └─ annotate_patterns()              services/legal/annotate.py
        ▼
save_analysis_to_db()                          services/analysis_persistence.py
        ▼
Analysis(status=completed) + Transaction[] + Subject[]
```

Прогресс: воркер публикует шаги в Redis → `/ws/analysis/{session_id}` пересылает
их в браузер. Отдельный процесс не может писать в сокет напрямую — отсюда мост.

**Фронтенд** читает готовый отчёт через `services/reportBuilder.ts`. Это
единственный способ отрисовать анализ: и сразу после загрузки, и при повторном
открытии из списка. Не собирай отчёт инлайном — иначе два экрана разойдутся.

---

## Структура

### Backend (`backend/app/`)

| Каталог | Отвечает за |
|---|---|
| `api/` | REST-роутеры: auth, analyses, transactions, subjects, users, notifications, websocket, bank_analysis |
| `core/` | config, database, security (JWT + bcrypt), celery_app |
| `models/` | SQLAlchemy: user, analysis, transaction, subject, notification, login_history, email_verification |
| `schemas/` | Pydantic-схемы запросов и ответов |
| `middleware/` | activity_tracker, rate_limiter, security_headers |
| `services/bank_analyzer/` | detector + parsers + analyzer + `base_parser.py` (модели `Transaction`, `AccountInfo`) |
| `services/fraud/` | engine + 11 детекторов + account_profiler + whitelist |
| `services/kaspi_analyzer/` | categorizer, analytics. **Парсинга здесь нет**, несмотря на имя |
| `services/privacy/` | anonymizer — маскирование ПД перед выходом за периметр |
| `services/ai/` | AIManager, Claude/Ollama провайдеры. Используется обогащением и разметкой колонок |
| `services/enrichment/` | тип контрагента, зарплата по регулярности, слова-операции. Работает и без модели |
| `services/legal/` | корпус НПА, поиск, проверка цитат. Корпус собирается локально, в репозиторий не кладётся |
| `services/agent/` | инструменты следователя, петля, заключение по делу, провайдеры Ollama/Claude |
| `services/pdf_export/` | генерация PDF-отчёта (reportlab) |
| `tasks/` | Celery: `process_file_task`, `cleanup_old_files_task` |
| `utils/` | helpers (нормализация имён, `is_organization`), security_info |

### Frontend (`frontend/src/`)

| Что | Где |
|---|---|
| Главный экран отчёта | `components/analysis/BankAnalysisReport.tsx` (5 секций) |
| Сборка отчёта из БД | `services/reportBuilder.ts` |
| API-клиент | `services/api.ts` |
| Страницы | `pages/`: Landing, Dashboard, Analyses, Settings |
| Состояние | `context/`: Auth, Theme, Language, Activity, BackgroundAnalysis, Notifications |
| WebSocket | `hooks/useAnalysisProgress.ts`, `hooks/useActivityMonitor.ts` |
| Локали | `locales/{ru,en,kk}.json` — **правь все три сразу** |

---

## Правила

**Выписки на трёх языках.** Kaspi и Halyk выдают один и тот же документ на
русском, казахском и английском. Никогда не сравнивай с русским литералом —
используй словари алиасов в `services/bank_analyzer/parsers/kaspi.py` и
`services/bank_analyzer/parsers/halyk.py`. Kaspi
печатает казахскую шва латиницей (`Ə` U+018F вместо `Ә` U+04D8), для этого есть
нормализация. Проверка корректности: три языковые версии обязаны давать
идентичный результат.

**Провал должен быть громким.** Ноль транзакций — это `StatementParsingError`,
а не пустой успешный отчёт. Нераспознанная дата — исключение, а не
`datetime.now()`. Система, которая молча говорит «риск низкий» о непрочитанном
документе, для следователя опаснее, чем упавшая.

**Персональные данные.** Всё, что уходит во внешнюю модель, проходит через
`services/privacy/anonymizer.py`. Маскируются ФИО, ИИН/ЖСН, IBAN, карты,
телефоны и имена контрагентов-физлиц, включая ФИО внутри названий ИП.
Названия организаций сохраняются намеренно — без них анализ риска мерчанта
теряет смысл. Гарантия проверяется тестом, а не обещанием.

Маскирование защищает путь **к** модели, а не обратно. Ответ агента и
заключение проходят через `Anonymizer.deanonymize()` перед показом: следователь
видит те же имена, что и в таблице транзакций. Подстановка идёт после сверки
чисел и цитат — проверка работает по тому тексту, который видела модель.

**Реальные выписки — только локально.** Каталог `Выписки/` в `.gitignore`.
В репозиторий кладётся генератор синтетики, но не файлы.

**Модели и alembic.** Каждая модель обязана быть импортирована в
`alembic/env.py`, иначе автогенерация выпишет для её таблицы `DROP TABLE`.
Проверяется тестом `tests/test_schema_and_privacy.py`.

**Проценты.** Бэкенд отдаёт доли (0..1), форматирование в проценты — на
фронтенде. Не умножай на 100 дважды.

---

## Проверка

```bash
cd backend && pytest
```

```bash
cd frontend && npx tsc --noEmit
```

```bash
python scripts/benchmark.py --runs 3 --transactions 200
```

Полная проверка парсинга — прогнать все файлы из `Выписки/`: каждый должен дать
либо транзакции, либо явную ошибку. Ни одного «успеха» с нулём транзакций.

---

## Состояние

Фаза 0 (консолидация) завершена. Дальше по плану:

1. **Ф1** — LLM-экстрактор + eval-набор. Подключить `services/ai/`, обязательная
   анонимизация, метрики в README.
2. **Ф1.5** — довести до UI то, что уже считается: `explained_flags`,
   `flagged_patterns` со ссылками на ЗРК, граф контрагентов.
3. **Ф2** — RAG по нормативке РК.
4. **Ф3** — агент-следователь поверх Ф1 и Ф2.
5. **Ф4** — публичный стенд.

**Где стоит языковая модель.** Она не считает балл риска — это правила и
статистика, и `nlp_analyzer.py` по-прежнему не подключён к скорингу. Модель
делает три вещи, каждая замерена:

1. **Заключение по делу** (`agent/conclusion.py`) — связный вывод из фактов
   одиннадцати модулей, графа и норм. Единственное, что нельзя написать
   правилами. Числа в готовом тексте сверяются с фактами, ссылки — с корпусом.
2. **Разметка незнакомой выписки** (`bank_analyzer/llm_layout.py`) — понимает,
   что означают колонки, когда словарь заголовков не знает банка. На таком
   файле было 0 верных строк из 200, стало 200 из 200.
3. **Классификация контрагентов** (`enrichment/`) — 58.5% правилами против
   89.0% с моделью на эталонном наборе.

Правило, выведенное замером: где детерминированный код отвечает точно, модель
не спрашивают. ИП, каналы поступлений и бренды решаются правилами именно
потому, что на них модель ошибалась чаще.
