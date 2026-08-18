"""Регресс-гейт поиска по НПА на коммитабельной фикстуре.

Настоящий корпус в CI недоступен, поэтому здесь маленькая фикстура из реальных
статей (15 профильных + дистракторы, см. scripts/build_retrieval_fixture.py).
Проверяется два разных вопроса: цел ли размеченный набор и не просел ли поиск.

Модель не нужна: поиск детерминированный (лексический), тест быстрый и
воспроизводимый. Развёрнутый отчёт с цифрами даёт scripts/eval_retrieval.py.
"""
import json
from pathlib import Path

import pytest

from app.services.legal import corpus

DATA = Path(__file__).parent / "data" / "retrieval_eval.json"
FIXTURE_DIR = str(Path(__file__).parent / "data")


@pytest.fixture(autouse=True)
def _clear_corpus_cache():
    corpus.clear_cache()
    yield
    corpus.clear_cache()


def load_queries():
    return json.loads(DATA.read_text(encoding="utf-8"))["queries"]


def test_dataset_integrity():
    queries = load_queries()
    ids = [q["id"] for q in queries]
    assert len(ids) == len(set(ids)), "дублирующиеся id запросов"
    assert len(queries) >= 12, "набор слишком мал, чтобы что-то измерять"
    for q in queries:
        assert q["query"].strip(), f"{q['id']}: пустой запрос"
        assert q["expected"], f"{q['id']}: не задана ожидаемая статья"
        for citation in q["expected"]:
            assert " ст. " in citation, \
                f"{q['id']}: цитата не в формате 'КОД ст. НОМЕР': {citation}"


def test_every_expected_article_is_present_in_the_fixture():
    """Разметка бессмысленна, если ожидаемой статьи нет в корпусе поиска."""
    available = {a.citation for a in corpus.load_articles(FIXTURE_DIR)}
    assert available, "фикстура-корпус пуст или не читается"
    for q in load_queries():
        for citation in q["expected"]:
            assert citation in available, \
                f"{q['id']}: ожидаемой статьи нет в фикстуре: {citation}"


def test_retrieval_quality_floor():
    """Правильная статья обязана быть в top-5 для каждого запроса, и в среднем
    близко к первому месту. Порог по-язычно: русское ранжирование держим на
    MRR 1.0 (BM25 ставит нужную статью первой), а казахский запрос обязан хотя
    бы находить норму в top-5 — казахский текст статей в корпусе отсутствует,
    поиск идёт по названию, поэтому ранг ниже, но находимость полная. Просадка
    любого языка уронит тест красным, а не молча зеленеет."""
    hits = {"ru": 0, "kk": 0}
    rr_sum = {"ru": 0.0, "kk": 0.0}
    totals = {"ru": 0, "kk": 0}
    for q in load_queries():
        lang = q.get("lang", "ru")
        totals[lang] += 1
        ranked = [a.citation for a, _ in
                  corpus.search(q["query"], limit=5, corpus_dir=FIXTURE_DIR)]
        expected = set(q["expected"])
        if set(ranked) & expected:
            hits[lang] += 1
        for i, citation in enumerate(ranked, 1):
            if citation in expected:
                rr_sum[lang] += 1.0 / i
                break

    ru_hit = hits["ru"] / totals["ru"]
    ru_mrr = rr_sum["ru"] / totals["ru"]
    kk_hit = hits["kk"] / totals["kk"] if totals["kk"] else 1.0

    assert ru_hit == 1.0, f"RU hit@5={ru_hit:.1%}: русский поиск потерял норму"
    assert ru_mrr >= 0.95, f"RU MRR={ru_mrr:.3f} < 0.95: русское ранжирование просело"
    assert kk_hit == 1.0, \
        f"KK hit@5={kk_hit:.1%}: казахский поиск не нашёл норму (title_kk не индексируется?)"
