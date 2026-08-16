"""Проверки набора вопросов для агента.

Набор ценен только тем, что его эталоны верны. Ошибись разметка — и eval
покажет число, которому нельзя верить, причём молча. Поэтому эталоны здесь
не переписаны руками, а пересчитываются из тех же операций: если кто-то
поправит набор и забудет обновить ожидаемый ответ, тест это заметит.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.privacy import Anonymizer  # noqa: E402

EVAL_PATH = Path(__file__).parent / "data" / "agent_eval.json"


@pytest.fixture(scope="module")
def data():
    with EVAL_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def test_questions_have_markup(data):
    for case in data["questions"]:
        assert case.get("question"), f"{case['id']}: нет вопроса"
        assert "must_include" in case, f"{case['id']}: нет разметки ответа"
        if not case.get("expect_refusal"):
            assert case["must_include"], (
                f"{case['id']}: вопрос без ожидаемого значения и без ожидания отказа "
                "ничего не проверяет"
            )


def test_ids_are_unique(data):
    ids = [c["id"] for c in data["questions"]]
    assert len(ids) == len(set(ids))


def test_expected_totals_match_the_transactions(data):
    """Ожидаемые суммы пересчитываются из операций набора."""
    rows = data["transactions"]
    income = sum(r["amount"] for r in rows if r["amount"] > 0)
    expense = sum(-r["amount"] for r in rows if r["amount"] < 0)

    expected = {c["id"]: c for c in data["questions"]}
    assert str(len(rows)) in expected["total_count"]["must_include"][0]
    assert str(int(income)) in expected["total_income"]["must_include"][0]
    assert str(int(expense)) in expected["total_expense"]["must_include"][0]


def test_expected_counts_match_the_transactions(data):
    rows = data["transactions"]
    expected = {c["id"]: c for c in data["questions"]}

    salary = sum(1 for r in rows if r["is_salary"])
    cash = [r for r in rows if r["is_cash"]]
    march = [r for r in rows if r["date"].startswith("2025-03")]
    large = [r for r in rows if abs(r["amount"]) > 500000]

    assert str(salary) in expected["salary_count"]["must_include"][0]
    assert str(len(cash)) in expected["cash_operations"]["must_include"][0]
    assert str(int(sum(-r["amount"] for r in cash))) in \
        expected["cash_operations"]["must_include"][1]
    assert str(len(march)) in expected["march_count"]["must_include"][0]
    assert str(len(large)) in expected["large_transfers"]["must_include"][0]


def test_dates_are_parseable(data):
    for row in data["transactions"]:
        datetime.strptime(row["date"], "%Y-%m-%d")


def test_refusal_questions_have_no_answer_in_the_data(data):
    """Вопрос «на отказ» не должен случайно иметь ответ в наборе.

    Иначе агент, ответивший по существу, был бы наказан за правоту.
    """
    years = {row["date"][:4] for row in data["transactions"]}
    assert "2019" not in years


def test_no_personal_data_in_the_set():
    assert Anonymizer().leaks(EVAL_PATH.read_text(encoding="utf-8")) == []
