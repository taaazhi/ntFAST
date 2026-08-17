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
    близко к первому месту. Если тронут стеммер или скоринг и качество
    просядет — тест падает красным, а не молча зеленеет."""
    queries = load_queries()
    hits = 0
    rr_sum = 0.0
    for q in queries:
        ranked = [a.citation for a, _ in
                  corpus.search(q["query"], limit=5, corpus_dir=FIXTURE_DIR)]
        expected = set(q["expected"])
        if set(ranked) & expected:
            hits += 1
        for i, citation in enumerate(ranked, 1):
            if citation in expected:
                rr_sum += 1.0 / i
                break

    n = len(queries)
    hit_at_5 = hits / n
    mrr = rr_sum / n
    assert hit_at_5 == 1.0, \
        f"hit@5={hit_at_5:.1%}: поиск перестал находить норму для части запросов"
    assert mrr >= 0.80, \
        f"MRR={mrr:.3f} < 0.80: ранжирование просело (нужная статья ушла вниз)"
