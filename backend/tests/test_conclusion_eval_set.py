"""Проверки самого размеченного набора для заключений.

Набор — это данные, а данные портятся тихо. Опечатка в ключе, задвоенный
id, кейс без разметки — всё это не уронит прогон, а исказит метрику: eval
покажет число, которому нельзя верить. Дешевле проверять набор тестом, чем
потом объяснять, почему цифры в README не воспроизводятся.

Отдельная проверка — отсутствие персональных данных. Набор лежит в
репозитории, и настоящей фамилии в нём быть не должно.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.agent.conclusion import collect_facts  # noqa: E402
from app.services.privacy import Anonymizer  # noqa: E402

EVAL_PATH = Path(__file__).parent / "data" / "conclusion_eval.json"


@pytest.fixture(scope="module")
def cases():
    with EVAL_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)["cases"]


def test_set_is_large_enough(cases):
    """Меньше десятка дел — не шкала, а несколько примеров."""
    assert len(cases) >= 12


def test_ids_are_unique(cases):
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))


def test_every_case_has_markup(cases):
    for case in cases:
        expect = case.get("expect")
        assert expect, f"{case['id']}: нет разметки"
        assert expect.get("must_include"), f"{case['id']}: нечего проверять на полноту"
        assert "needs_counter_evidence" in expect, f"{case['id']}: не указано, нужны ли доводы против"
        for variants in expect["must_include"]:
            assert isinstance(variants, list) and variants, (
                f"{case['id']}: элемент полноты должен быть непустым списком синонимов"
            )


def test_facts_are_collectable(cases):
    """Каждый кейс обязан проходить через collect_facts.

    Если структура разойдётся с тем, что строит анализ, eval будет мерить
    не то, что работает в системе.
    """
    for case in cases:
        facts = collect_facts(case["analysis"])
        assert facts["transactions"], f"{case['id']}: не собралось число операций"
        assert facts["total_income"] != "—", f"{case['id']}: не собрался доход"


def test_forbidden_strings_are_really_absent_from_facts(cases):
    """То, что запрещено в тексте, не должно встречаться в самих фактах.

    Иначе проверка «модель добавила от себя» ловила бы модель на том, что
    ей же и передали.
    """
    for case in cases:
        blob = json.dumps(case["analysis"], ensure_ascii=False).lower()
        for forbidden in case["expect"].get("forbidden", []):
            assert forbidden.lower() not in blob, (
                f"{case['id']}: «{forbidden}» есть в фактах, запрещать его нельзя"
            )


def test_counter_evidence_markup_matches_facts(cases):
    """needs_counter_evidence обязан соответствовать наличию контрдоводов."""
    for case in cases:
        report = case["analysis"]["fraud_report"]
        has_counter = any(
            item.get("counter_evidence")
            for item in (report.get("explained_flags") or []) + (report.get("flagged_patterns") or [])
        )
        assert case["expect"]["needs_counter_evidence"] == has_counter, (
            f"{case['id']}: разметка доводов против расходится с фактами"
        )


def test_no_personal_data_in_the_set():
    """В наборе нет ИИН, IBAN, карт, телефонов и ФИО физлиц."""
    raw = EVAL_PATH.read_text(encoding="utf-8")
    assert Anonymizer().leaks(raw) == []
