"""Шаг обогащения: то, что нужно детекторам, но чего нет в тексте выписки.

Ставится между разбором и антифродом. Порядок внутри важен: сначала
классификация контрагентов, потом зарплата — детектор зарплаты смотрит на
`counterparty_type`, чтобы не записать в работодатели физлицо.

Работает без языковой модели. Это не заглушка на будущее, а рабочий режим:
на бенчмарке одни только правила поднимают композитный балл незнакомого
формата с 17.4 LOW до 63.0 HIGH, то есть до уровня банк-специфичного
парсера. Модель, когда она подключена, уточняет классификацию — заменяет
рукописные словари мерчантов и стоп-листы, а не создаёт результат с нуля.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Sequence

from .counterparty_classifier import Classification, CounterpartyClassifier, classify_by_rule
from .salary_detector import mark_salary_transactions

logger = logging.getLogger(__name__)


def build_ai_manager() -> Optional[Any]:
    """Собрать провайдера из настроек — или ничего, если он не разрешён.

    Выключено по умолчанию (`AI_ENRICHMENT_ENABLED=False`). Отправка
    выписки во внешний сервис — решение владельца системы, а не побочный
    эффект обновления кода: закон РК «О персональных данных» (№94-V)
    относит эти данные к охраняемым, и включаться такое должно осознанно.

    Для извлечения берётся Haiku: классификация контрагентов — это тысячи
    коротких однотипных решений, и модель для рассуждений здесь не нужна.
    """
    from app.core.config import settings

    if not getattr(settings, "AI_ENRICHMENT_ENABLED", False):
        return None

    from app.services.ai.ai_manager import AIManager

    return AIManager(
        claude_api_key=settings.CLAUDE_API_KEY,
        claude_model=settings.CLAUDE_EXTRACTION_MODEL,
        ollama_host=settings.OLLAMA_HOST,
        ollama_model=settings.OLLAMA_MODEL,
    )


#: Сколько имён отдавать модели. Остальные разбираются правилом.
#:
#: Не произвольное число, а следствие замера. На выписке Kaspi 1320
#: транзакций дают 329 уникальных контрагентов — это 28 батчей, около
#: двенадцати минут на локальной модели. Ждать столько ради разбора одной
#: выписки нельзя.
#:
#: Отбор идёт по обороту, и это осмысленно, а не просто дёшево: следователю
#: важно, кому ушли крупные суммы, а не как классифицированы триста мелких
#: покупок в разных магазинах. Крупные контрагенты уходят модели, хвост —
#: правилу, которое и так узнаёт бренды на 13 из 13.
MAX_LLM_NAMES = 60


def _names_of(transactions: Sequence[Any]) -> List[str]:
    return [
        (getattr(t, "counterparty", None) or getattr(t, "description", None) or "")
        for t in transactions
    ]


def _names_by_turnover(transactions: Sequence[Any], limit: int) -> List[str]:
    """Имена контрагентов, отсортированные по обороту, не длиннее limit."""
    turnover: Dict[str, float] = {}
    for tx in transactions:
        name = (
            getattr(tx, "counterparty", None) or getattr(tx, "description", None) or ""
        ).strip()
        if not name:
            continue
        turnover[name] = turnover.get(name, 0.0) + abs(float(getattr(tx, "amount", 0) or 0))

    ranked = sorted(turnover, key=lambda n: turnover[n], reverse=True)
    return ranked[:limit]


def _classify_offline(transactions: Sequence[Any]) -> Dict[str, Classification]:
    """Классификация правилами — без сети и без ключа."""
    return {
        name.strip(): classify_by_rule(name)
        for name in _names_of(transactions)
        if name and name.strip()
    }


def _run_async(coro):
    """Выполнить корутину из синхронного кода.

    `BankAnalyzer.analyze()` синхронный и вызывается в том числе из Celery.
    Если цикл событий уже крутится (сервер FastAPI), `asyncio.run` бросит
    исключение — в этом случае обогащение через модель пропускаем и
    остаёмся на правилах, вместо того чтобы уронить анализ.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    coro.close()
    raise RuntimeError("event loop is already running")


def _anonymised_names(
    transactions: Sequence[Any], owner_name: Optional[str]
) -> tuple[List[str], Any]:
    """Имена контрагентов в виде, пригодном для отправки наружу.

    Шлюз, а не украшение. Всё, что уходит в облачную модель, проходит
    здесь: ФИО, ИИН/ЖСН, IBAN, номера карт и телефоны заменяются на теги.
    Названия организаций сохраняются намеренно — без них оценка риска
    мерчанта теряет смысл, а персональными данными они не являются.

    Возвращает список в том же порядке, что и транзакции, и сам
    анонимизатор: по нему потом проверяется, что утечки не было.
    """
    from app.services.privacy.anonymizer import Anonymizer

    anonymizer = Anonymizer(owner_name=owner_name)
    raw = _names_of(transactions)
    # Первый проход обязателен: одно и то же имя встречается и в поле
    # контрагента, и внутри описания. Без него имя, вычищенное из одного
    # места, осталось бы открытым в другом.
    anonymizer.register(raw)
    return [anonymizer.counterparty(name) for name in raw], anonymizer


def enrich_transactions(
    transactions: Sequence[Any],
    ai_manager: Optional[Any] = None,
    cache: Optional[Dict[str, Classification]] = None,
    owner_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Обогатить транзакции на месте. Возвращает сводку для отчёта."""
    if not transactions:
        return {"classified": 0, "salary_sources": [], "classifier": None}

    classifier = CounterpartyClassifier(ai_manager=ai_manager, cache=cache)
    stats: Optional[Dict[str, Any]] = None
    privacy: Optional[Dict[str, Any]] = None

    if ai_manager is not None:
        try:
            safe_names, anonymizer = _anonymised_names(transactions, owner_name)
            raw_names = _names_of(transactions)

            # Модели достаются только значимые по обороту имена. Остальные
            # разбираются правилом — сразу, чтобы у каждого контрагента был
            # хоть какой-то тип, а не пустота.
            significant = set(_names_by_turnover(transactions, MAX_LLM_NAMES))
            for_model = [
                safe for raw, safe in zip(raw_names, safe_names)
                if raw.strip() in significant
            ]

            safe_mapping = _run_async(classifier.classify(for_model))
            # Классификации получены по обезличенным именам — возвращаем их
            # к исходным, чтобы проставить в транзакции.
            mapping = _classify_offline(transactions)
            mapping.update({
                raw.strip(): safe_mapping[safe.strip()]
                for raw, safe in zip(raw_names, safe_names)
                if raw.strip() and safe.strip() in safe_mapping
            })
            stats = classifier.stats.as_dict()
            stats["names_total"] = len({n.strip() for n in raw_names if n.strip()})
            stats["names_to_model"] = len(significant)
            privacy = anonymizer.report().to_dict()
        except Exception as exc:
            # Недоступная модель не должна ломать анализ — она его улучшает.
            logger.warning("Обогащение через модель не выполнено (%s), работаем по правилам", exc)
            mapping = _classify_offline(transactions)
    else:
        mapping = _classify_offline(transactions)

    classified = classifier.apply(transactions, mapping)
    salary_sources = mark_salary_transactions(transactions)

    return {
        "classified": classified,
        "salary_sources": [f.as_dict() for f in salary_sources],
        "classifier": stats,
        # Что именно было замаскировано перед отправкой наружу. Пустое,
        # когда модель не вызывалась и данные периметр не покидали.
        "privacy": privacy,
    }
