"""Разбор ссылок на нормы в найденных схемах — уже после детектирования.

Отдельный шаг, а не часть `PatternDetector`, по двум причинам. Детектор должен
работать без корпуса НПА: он ищет схемы в транзакциях, и отсутствие текстов
законов не может быть основанием не найти отмывание. И наоборот — проверка
ссылок нужна независимо от того, кто их поставил: человек в коде сегодня,
языковая модель завтра.

Результат — список статей с URL на первоисточник и признаком проверки. Ссылку
следователь открывает в один клик и читает норму сам; система не заменяет
правовую квалификацию, а сокращает путь до неё.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from .verifier import Verdict, verify_reference_line

logger = logging.getLogger(__name__)


def parse_reference(reference: str, corpus_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Строка `regulatory_reference` → список статей с проверкой.

    Непроверенные ссылки не выбрасываются, а помечаются. Скрыть их означало бы
    сделать вид, что детектор ни на что не ссылался; показать как достоверные —
    выдать непроверенное за подтверждённое. Верно третье: показать с оговоркой.
    """
    from . import corpus as corpus_module

    report = verify_reference_line(reference, corpus_dir=corpus_dir)
    articles: List[Dict[str, Any]] = []

    for check in report.checks:
        # Казахское название берётся из казахской редакции того же акта, а
        # не переводится на ходу: название нормы — часть официального
        # текста, и сочинять его в документе для следствия нельзя.
        article = corpus_module.get_article(check.code, check.number, corpus_dir)
        articles.append({
            "citation": check.citation,
            "title": check.title or "",
            "title_kk": getattr(article, "title_kk", "") if article else "",
            "url": check.url or "",
            "url_kk": getattr(article, "url_kk", "") if article else "",
            "verified": check.is_trustworthy,
            "verdict": check.verdict.value,
            # Пояснение нужно только когда что-то не так: у подтверждённой
            # ссылки объяснять нечего.
            "detail": "" if check.is_trustworthy else check.detail,
        })
    return articles


def annotate_patterns(
    patterns: Sequence[Any], corpus_dir: Optional[str] = None
) -> Dict[str, int]:
    """Заполнить `legal_articles` у найденных схем. Возвращает сводку.

    Изменяет объекты на месте. Сбой проверки не должен ломать отчёт: анализ
    транзакций от неё не зависит, поэтому исключение здесь только логируется.
    """
    summary = {"patterns": 0, "articles": 0, "verified": 0, "unavailable": 0}

    for pattern in patterns:
        reference = getattr(pattern, "regulatory_reference", "") or ""
        if not reference:
            continue

        try:
            articles = parse_reference(reference, corpus_dir=corpus_dir)
        except Exception as exc:
            logger.warning("Не удалось разобрать ссылку «%s»: %s", reference[:60], exc)
            continue

        pattern.legal_articles = articles
        summary["patterns"] += 1
        summary["articles"] += len(articles)
        summary["verified"] += sum(1 for a in articles if a["verified"])
        summary["unavailable"] += sum(
            1 for a in articles if a["verdict"] == Verdict.CORPUS_UNAVAILABLE.value
        )

    if summary["articles"]:
        logger.info(
            "Ссылки на НПА: %d из %d подтверждены официальным текстом",
            summary["verified"], summary["articles"],
        )
    return summary
