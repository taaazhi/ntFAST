"""Корпус НПА, поиск по нему и проверка ссылок.

Тесты работают на маленьком поддельном корпусе, а не на настоящем. Причина не
в удобстве: настоящий корпус в репозиторий не кладётся (тексты кодексов —
мегабайты, поправки выходят по нескольку раз в год), поэтому в CI его не будет,
и тест, требующий его, там просто не запустится. Здесь же проверяется логика:
что считать подтверждённым, что выдуманным и как вести себя, когда проверять
нечем.

Отдельно закреплено поведение без корпуса. «Проверить невозможно» — это не
«ссылка неверна»: система обязана продолжать анализ выписки, просто без цитат.
"""
import json

import pytest

from app.services.legal import corpus, verifier
from app.services.legal.verifier import Verdict


@pytest.fixture
def fake_corpus(tmp_path):
    """Три статьи, достаточные, чтобы различить все вердикты."""
    articles = [
        {
            "code": "УК РК", "number": "218",
            "title": "Легализация (отмывание) денег и (или) иного имущества, "
                     "полученных преступным путем",
            "text": "1. Вовлечение в законный оборот денег и (или) иного имущества, "
                    "полученных преступным путем, посредством совершения сделок.",
            "url": "https://adilet.zan.kz/rus/docs/K1400000226#z100",
        },
        {
            "code": "УК РК", "number": "205",
            "title": "Неправомерный доступ к информации",
            "text": "1. Неправомерный доступ к охраняемой законом информации.",
            "url": "https://adilet.zan.kz/rus/docs/K1400000226#z200",
        },
        {
            "code": "ЗРК О ПОД/ФТ", "number": "4",
            "title": "Операции с деньгами и (или) иным имуществом, подлежащие "
                     "финансовому мониторингу",
            "text": "1. Операция подлежит финансовому мониторингу, если сумма "
                    "операции равна или превышает 1 000 000 тенге.",
            "url": "https://adilet.zan.kz/rus/docs/Z090000191_#z34",
        },
    ]
    path = tmp_path / "test_corpus.jsonl"
    path.write_text(
        "\n".join(json.dumps(a, ensure_ascii=False) for a in articles),
        encoding="utf-8",
    )
    corpus.clear_cache()
    yield str(tmp_path)
    corpus.clear_cache()


@pytest.fixture
def empty_corpus(tmp_path):
    corpus.clear_cache()
    yield str(tmp_path / "nothing-here")
    corpus.clear_cache()


# ── Вердикты ────────────────────────────────────────────────────

def test_real_article_is_verified(fake_corpus):
    check = verifier.verify_citation("УК РК", "218", corpus_dir=fake_corpus)

    assert check.verdict is Verdict.VERIFIED
    assert check.is_trustworthy
    assert check.url.endswith("#z100")


def test_invented_article_is_caught(fake_corpus):
    """Модель охотно назовёт номер статьи, которой нет."""
    check = verifier.verify_citation("УК РК", "9999", corpus_dir=fake_corpus)

    assert check.verdict is Verdict.ARTICLE_NOT_FOUND
    assert not check.is_trustworthy


def test_article_exists_but_is_about_something_else(fake_corpus):
    """Худший случай: номер настоящий, но норма другая.

    Ровно так и было в отчёте — ст. 205 приводилась как «мошенничество»,
    хотя это «Неправомерный доступ к информации». Такую ошибку не видно,
    пока кто-нибудь не откроет кодекс.
    """
    check = verifier.verify_citation(
        "УК РК", "205", expected_title="мошенничество", corpus_dir=fake_corpus
    )

    assert check.verdict is Verdict.TITLE_MISMATCH
    assert "Неправомерный доступ" in check.detail


def test_shortened_title_still_verifies(fake_corpus):
    """В отчёте название сокращают — это не расхождение."""
    check = verifier.verify_citation(
        "УК РК", "218",
        expected_title="легализация (отмывание) денег",
        corpus_dir=fake_corpus,
    )

    assert check.verdict is Verdict.VERIFIED


def test_invented_quote_is_caught(fake_corpus):
    """Пересказ «своими словами» — самый правдоподобный вид выдумки."""
    check = verifier.verify_citation(
        "УК РК", "218",
        quote="карается лишением свободы на срок до двадцати лет",
        corpus_dir=fake_corpus,
    )

    assert check.verdict is Verdict.QUOTE_NOT_FOUND


def test_genuine_quote_passes(fake_corpus):
    check = verifier.verify_citation(
        "ЗРК О ПОД/ФТ", "4",
        quote="равна или превышает 1 000 000 тенге",
        corpus_dir=fake_corpus,
    )

    assert check.verdict is Verdict.VERIFIED


# ── Без корпуса система работает, но молчит о нормах ────────────

def test_missing_corpus_is_not_a_wrong_citation(empty_corpus):
    """«Проверить нечем» и «ссылка неверна» — разные вещи, и путать их
    нельзя: из первого следует скрыть цитату, из второго — исправить код."""
    check = verifier.verify_citation("УК РК", "218", corpus_dir=empty_corpus)

    assert check.verdict is Verdict.CORPUS_UNAVAILABLE
    assert not check.is_trustworthy
    assert "fetch_legal_corpus" in check.detail


def test_search_without_corpus_returns_nothing(empty_corpus):
    assert corpus.search("отмывание денег", corpus_dir=empty_corpus) == []


# ── Разбор строки отчёта ────────────────────────────────────────

def test_second_article_inherits_the_code(fake_corpus):
    """«УК РК ст. 218 (…); ст. 205 (…)» — вторая статья из того же кодекса.

    Регресс: пока код требовался у каждой ссылки, проверялась только первая
    в строке, а остальные тихо выпадали из проверки.
    """
    report = verifier.verify_reference_line(
        "УК РК ст. 218 (легализация); ст. 205 (мошенничество)",
        corpus_dir=fake_corpus,
    )

    assert [c.number for c in report.checks] == ["218", "205"]
    assert all(c.code == "УК РК" for c in report.checks)


def test_non_kazakh_sources_are_not_treated_as_articles(fake_corpus):
    """FATF Recommendation 10 — не статья казахстанского акта, и проверять
    её по корпусу бессмысленно."""
    report = verifier.verify_reference_line(
        "ЗРК О ПОД/ФТ ст. 4; FATF Recommendation 10", corpus_dir=fake_corpus
    )

    assert len(report.checks) == 1
    assert report.all_verified


def test_article_without_any_code_is_skipped(fake_corpus):
    """«ст. 190» без указания кодекса: угадывать в правовом документе нельзя."""
    report = verifier.verify_reference_line("ст. 190 (мошенничество)", corpus_dir=fake_corpus)

    assert report.checks == []


# ── Поиск ───────────────────────────────────────────────────────

def test_search_finds_the_article_by_its_subject(fake_corpus):
    results = corpus.search("легализация отмывание денег", corpus_dir=fake_corpus)

    assert results
    assert results[0][0].number == "218"


def test_search_ranks_title_matches_above_body_matches(fake_corpus):
    """Название статьи информативнее тела, где слово может встретиться
    в перечислении исключений."""
    results = corpus.search("финансовому мониторингу", corpus_dir=fake_corpus)

    assert results[0][0].number == "4"
