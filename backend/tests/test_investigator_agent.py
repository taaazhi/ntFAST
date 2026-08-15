"""Петля следственного агента на подставной модели.

Двойник здесь не компромисс, а условие проверки: тесты описывают поведение
при *плохо работающей* модели — она зациклилась, вызвала несуществующий
инструмент, сослалась на статью, не проверив её. Настоящая модель такие
сценарии по заказу не выдаст, а закладываться на них нужно, потому что
именно они портят вывод в материалах дела.
"""
from datetime import datetime

import pytest

from app.services.agent import AgentAnswer, InvestigatorAgent, ToolContext
from app.services.bank_analyzer.base_parser import (
    CounterpartyType, Transaction, TransactionType,
)
from app.services.privacy.anonymizer import Anonymizer


class ScriptedProvider:
    """Отдаёт заранее записанные ответы модели по одному на вызов."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def run(self, system, messages, tools):
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        if not self._responses:
            raise AssertionError("модель вызвана больше раз, чем ожидалось")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def say(text):
    return {"content": [{"type": "text", "text": text}], "provider": "Scripted"}


def call(tool, params=None, block_id="tu_1"):
    return {
        "content": [{
            "type": "tool_use", "id": block_id,
            "name": tool, "input": params or {},
        }],
        "provider": "Scripted",
    }


@pytest.fixture
def ctx():
    transactions = [
        Transaction(
            date=datetime(2025, 1, 5), amount=-150_000,
            type=TransactionType.EXPENSE, description="",
            counterparty="Ержан О.", counterparty_type=CounterpartyType.PERSON,
        ),
        Transaction(
            date=datetime(2025, 1, 6), amount=500_000,
            type=TransactionType.INCOME, description="",
            counterparty="ТОО Астана Строй", counterparty_type=CounterpartyType.MERCHANT,
        ),
    ]
    anonymizer = Anonymizer(owner_name="Тажибаев Нурдаулет Ерланович")
    anonymizer.register([t.counterparty for t in transactions])
    return ToolContext(transactions=transactions, anonymizer=anonymizer)


# ── Нормальный ход ───────────────────────────────────────────────

def test_answer_without_tools_is_returned_as_is(ctx):
    agent = InvestigatorAgent(ScriptedProvider([say("Данных достаточно: расход один.")]))

    answer = agent.ask("Сколько было расходов?", ctx)

    assert "расход один" in answer.text
    assert answer.steps == 1
    assert answer.stopped_early is False


def test_tool_result_is_fed_back_to_the_model(ctx):
    provider = ScriptedProvider([
        call("query_transactions", {"direction": "expense"}),
        say("Один расход на 150 000 ₸ в пользу [PERSON_1]."),
    ])
    agent = InvestigatorAgent(provider)

    answer = agent.ask("Куда уходили деньги?", ctx)

    assert answer.tool_calls[0]["tool"] == "query_transactions"
    assert answer.tool_calls[0]["ok"] is True
    # Второй запрос к модели уже содержит результат инструмента.
    assert "tool_result" in str(provider.calls[1]["messages"])


def test_tool_results_never_carry_real_names(ctx):
    """То, что вернул инструмент, уходит обратно в модель — значит и там
    имён быть не должно."""
    provider = ScriptedProvider([
        call("summarise_counterparties"),
        say("Готово."),
    ])

    InvestigatorAgent(provider).ask("Кому платили?", ctx)

    transmitted = str(provider.calls[1]["messages"])
    assert "Ержан" not in transmitted
    assert "PERSON_" in transmitted


# ── Плохо работающая модель ──────────────────────────────────────

def test_loop_stops_and_says_so(ctx):
    """Модель, не находящая ответа, ходит по кругу. Отдать половину
    рассуждения как результат нельзя — надо признать, что вывод неполон."""
    provider = ScriptedProvider([call("get_period_totals") for _ in range(3)])
    agent = InvestigatorAgent(provider, max_steps=3)

    answer = agent.ask("Что здесь не так?", ctx)

    assert answer.stopped_early is True
    assert answer.steps == 3


def test_unknown_tool_does_not_break_the_run(ctx):
    provider = ScriptedProvider([
        call("проанализируй_всё"),
        say("Инструмента нет, отвечаю по имеющемуся."),
    ])

    answer = InvestigatorAgent(provider).ask("Вопрос", ctx)

    assert answer.tool_calls[0]["ok"] is False
    assert "отвечаю" in answer.text


def test_provider_failure_is_reported_not_raised(ctx):
    """Недоступная модель не должна ронять разбор: анализ выписки от неё
    не зависит."""
    agent = InvestigatorAgent(ScriptedProvider([ConnectionError("нет сети")]))

    answer = agent.ask("Вопрос", ctx)

    assert answer.error and "нет сети" in answer.error
    assert answer.text == ""


# ── Проверка ссылок на выходе ────────────────────────────────────

def test_citations_in_the_answer_are_checked_even_if_the_agent_did_not(ctx, tmp_path):
    """Модель может сослаться на норму, не вызвав verify_citation.

    Поэтому итоговый текст сверяется здесь — независимо от того, что делал
    агент по дороге.
    """
    import json as json_lib
    from app.services.legal import corpus

    (tmp_path / "c.jsonl").write_text(json_lib.dumps({
        "code": "УК РК", "number": "218",
        "title": "Легализация (отмывание) денег",
        "text": "1. Вовлечение в законный оборот.",
        "url": "https://adilet.zan.kz/rus/docs/K1400000226#z100",
    }, ensure_ascii=False), encoding="utf-8")
    corpus.clear_cache()
    ctx.corpus_dir = str(tmp_path)

    agent = InvestigatorAgent(ScriptedProvider([
        say("Признаки подпадают под УК РК ст. 218 и УК РК ст. 9999.")
    ]))
    answer = agent.ask("Какая норма применима?", ctx)
    corpus.clear_cache()

    verdicts = {c["citation"]: c["verified"] for c in answer.citations}
    assert verdicts["УК РК ст. 218"] is True
    assert verdicts["УК РК ст. 9999"] is False
    assert answer.has_unverified_citations is True


def test_answer_without_citations_has_none_flagged(ctx):
    agent = InvestigatorAgent(ScriptedProvider([say("Ничего необычного не вижу.")]))

    answer = agent.ask("Есть ли нарушения?", ctx)

    assert answer.citations == []
    assert answer.has_unverified_citations is False


def test_answer_serialises_for_the_report(ctx):
    agent = InvestigatorAgent(ScriptedProvider([say("Ответ.")]))

    payload = agent.ask("Вопрос", ctx).to_dict()

    assert set(payload) >= {"text", "tool_calls", "citations", "steps", "provider"}


def test_system_prompt_forbids_inventing_citations(ctx):
    """Требование проверять норму — часть промпта, а не устная договорённость."""
    provider = ScriptedProvider([say("ok")])
    InvestigatorAgent(provider).ask("Вопрос", ctx)

    system = provider.calls[0]["system"]
    assert "verify_citation" in system
    assert "выдуманная ссылка" in system.lower()
