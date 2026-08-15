"""Ссылки на нормы права в отчёте должны существовать и называться верно.

История этих тестов. Ссылки писались по памяти прямо в строках детектора, и
сверка с официальными текстами на adilet.zan.kz показала, что пять из шести
указывают не на ту статью: мошенничество значилось как ст. 205 (на деле —
неправомерный доступ к информации), торговля людьми как ст. 135 (торговля
несовершеннолетними), финансовая пирамида как ст. 216 (фиктивные
счета-фактуры), доходы физлиц как НК ст. 320 (ставки налога), а уголовной
нормы про отмывание не было вовсе.

Отчёт читает следователь. Неверная ссылка выглядит как правовая квалификация,
которую никто не проверял, и обесценивает остальной анализ.

Тесты сверяют то, что печатается в отчёте, со справочником `legal_references`,
выверенным по официальным текстам. Сами тексты в репозиторий не кладутся: они
объёмны и меняются, а держать неактуальную копию закона хуже, чем не держать
никакой. Здесь проверяется целостность ссылок, а не содержание норм.
"""
import re

import pytest

from app.services.fraud.legal_references import (
    ARTICLES,
    MONITORING_THRESHOLD_KZT,
    LegalArticle,
)
from app.services.fraud.pattern_detector import PatternDetector

#: «УК РК ст. 218», «НК РК ст. 321», «ЗРК О ПОД/ФТ ст. 4»
CITATION = re.compile(r'(УК РК|НК РК|ЗРК О ПОД/ФТ)\s+ст\.\s*(\d+)')

#: Номера, которых в отчёте быть не должно: они уже были перепутаны однажды.
RETIRED = {
    ("УК РК", "205"): "неправомерный доступ к информации, а не мошенничество",
    ("УК РК", "135"): "торговля несовершеннолетними, а не торговля людьми",
    ("УК РК", "216"): "фиктивные счета-фактуры, а не финансовая пирамида",
    ("НК РК", "320"): "ставки налога, а не доходы физического лица",
}


def all_references() -> list[str]:
    """Все `regulatory_reference`, зашитые в детектор схем."""
    import inspect

    source = inspect.getsource(PatternDetector)
    return re.findall(r'regulatory_reference=\(?\s*((?:"[^"]*"\s*)+)', source)


def cited_articles() -> set[tuple[str, str]]:
    joined = " ".join(all_references())
    return set(CITATION.findall(joined))


def test_detector_cites_at_least_one_article():
    """Защита от тихой поломки самого теста: если regex перестанет находить
    ссылки, остальные проверки пройдут на пустом множестве."""
    assert len(cited_articles()) >= 5


@pytest.mark.parametrize("code,number", sorted(RETIRED))
def test_wrong_article_numbers_never_come_back(code, number):
    """Регресс: каждый из этих номеров стоял в отчёте и указывал не туда."""
    assert (code, number) not in cited_articles(), (
        f"{code} ст. {number} — {RETIRED[(code, number)]}"
    )


def test_every_cited_article_is_in_the_reference_table():
    """Ссылка, которой нет в выверенном справочнике, не проверена никем."""
    known = {(a.code, a.number) for a in ARTICLES.values()}
    unknown = cited_articles() - known

    assert not unknown, (
        f"в отчёте есть непроверенные ссылки: {sorted(unknown)}. "
        f"Сверьте с официальным текстом и внесите в legal_references.ARTICLES"
    )


@pytest.mark.parametrize("key", sorted(ARTICLES))
def test_reference_table_entries_are_complete(key):
    article: LegalArticle = ARTICLES[key]

    assert article.number.isdigit()
    assert len(article.title) > 10
    assert article.source_url.startswith("https://adilet.zan.kz/")


def test_structuring_threshold_matches_the_law():
    """Порог обязательного мониторинга задан ЗРК ст. 4, п. 1, пп. 1) —
    1 000 000 тенге. Детектор структурирования ищет суммы чуть ниже него, и
    если порог разойдётся с законом, весь модуль будет искать не то."""
    from app.services.fraud import structuring

    thresholds = [
        value for name, value in vars(structuring).items()
        if isinstance(value, (int, float)) and value == MONITORING_THRESHOLD_KZT
    ]
    assert thresholds, (
        "в structuring.py нет порога 1 000 000 ₸ из ЗРК ст. 4 — "
        "проверьте, на какое значение он опирается"
    )
