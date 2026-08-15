"""Сборка контекста агента из сохранённого анализа.

Проверяется стык между базой и инструментами. Он тихий: если поля не сойдутся,
инструменты не упадут — они вернут пустые контрагенты и нули, а модель уверенно
опишет выписку, которой не видела. Поэтому соответствие полей фиксируется
тестом, а не проверяется глазами.

И главное — анонимизатор. Контекст строится вместе с ним, потому что ответы
инструментов уходят в языковую модель: не замаскировав имена здесь, мы отдадим
их наружу при первом же вызове.
"""
from datetime import datetime

import pytest

from app.services.agent import from_analysis, from_db_transactions, run_tool


class Row:
    """Строка таблицы transactions — имена полей как в модели БД."""

    def __init__(self, amount, counterparty_name="", transaction_date=None,
                 counterparty_type="unknown", description="", is_salary=False,
                 merchant_name="", is_cash_operation=False):
        self.amount = amount
        self.counterparty_name = counterparty_name
        self.transaction_date = transaction_date or datetime(2025, 1, 5)
        self.counterparty_type = counterparty_type
        self.description = description
        self.is_salary = is_salary
        self.merchant_name = merchant_name
        self.is_cash_operation = is_cash_operation


class StoredAnalysis:
    def __init__(self, owner=None, fraud_report=None):
        self.account_owner = owner
        self.fraud_report = fraud_report


@pytest.fixture
def rows():
    return [
        Row(-150_000, "Ержан О.", counterparty_type="person"),
        Row(-3_500, "Magnum", counterparty_type="merchant"),
        Row(500_000, "ТОО Астана Строй", counterparty_type="merchant", is_salary=True),
    ]


def test_db_fields_map_onto_tool_fields(rows):
    """`counterparty_name` в базе, `counterparty` в инструментах: разойдутся —
    и агент увидит выписку без контрагентов."""
    ctx = from_db_transactions(rows)
    result = run_tool("query_transactions", ctx, direction="income")

    assert result["found"] == 1
    row = result["transactions"][0]
    assert row["counterparty"] == "ТОО Астана Строй"
    assert row["is_salary"] is True
    assert row["date"] == "05.01.2025"


def test_counterparty_type_survives_as_a_filter(rows):
    ctx = from_db_transactions(rows)

    assert run_tool("query_transactions", ctx, counterparty_type="merchant")["found"] == 2


def test_names_are_masked_before_any_tool_returns_them(rows):
    ctx = from_db_transactions(rows)
    payload = str(run_tool("summarise_counterparties", ctx))

    assert "Ержан" not in payload
    assert "PERSON_" in payload
    assert "Magnum" in payload


def test_account_owner_is_masked_too(rows):
    """Владелец счёта фигурирует и среди контрагентов — переводом себе."""
    owner = "Тажибаев Нурдаулет Ерланович"
    rows.append(Row(-50_000, owner, counterparty_type="person"))

    ctx = from_analysis(StoredAnalysis(owner=owner), rows)
    payload = str(run_tool("summarise_counterparties", ctx))

    assert "Тажибаев" not in payload


def test_fraud_report_reaches_the_risk_tool(rows):
    report = {"composite_score": 63.0, "risk_level": "high", "flagged_patterns": []}

    ctx = from_analysis(StoredAnalysis(fraud_report=report), rows)
    result = run_tool("get_risk_breakdown", ctx)

    assert result["available"] is True
    assert result["composite_score"] == 63.0


def test_analysis_without_fraud_report_is_not_an_error(rows):
    ctx = from_analysis(StoredAnalysis(), rows)

    assert run_tool("get_risk_breakdown", ctx)["available"] is False


def test_empty_analysis_produces_a_usable_context():
    """Ноль транзакций — не повод падать: агент должен ответить, что данных нет."""
    ctx = from_db_transactions([])

    assert run_tool("query_transactions", ctx)["found"] == 0
    assert run_tool("get_period_totals", ctx)["months"] == []


def test_null_columns_do_not_break_the_context():
    """В базе почти все поля nullable, и пустая строка приходит как None."""
    ctx = from_db_transactions([Row(-100, None, description=None)])

    result = run_tool("query_transactions", ctx)
    assert result["found"] == 1
    assert result["transactions"][0]["counterparty"] == ""


# ── Провайдер модели ─────────────────────────────────────────────

class _Settings:
    """Настройки с явным выбором провайдера.

    `AGENT_PROVIDER="cloud"` здесь обязателен: в режиме `auto` результат
    зависел бы от того, установлена ли на машине Ollama, и тест проходил бы
    на CI и падал у разработчика с локальной моделью — или наоборот.
    """

    def __init__(self, enabled=True, key="sk-test", model="claude-sonnet-5",
                 preference="cloud"):
        self.AI_ENRICHMENT_ENABLED = enabled
        self.AGENT_PROVIDER = preference
        self.CLAUDE_API_KEY = key
        self.CLAUDE_REASONING_MODEL = model
        self.OLLAMA_MODEL = "qwen2.5:3b"
        self.OLLAMA_HOST = "http://localhost:11434"
        self.AI_MAX_TOKENS = 1024


def test_provider_is_absent_when_disabled():
    """Выключенный агент — рабочее состояние, а не сбой: отправка данных во
    внешний сервис должна быть осознанным решением владельца системы."""
    from app.services.agent import build_agent_provider

    assert build_agent_provider(_Settings(enabled=False)) is None


def test_provider_is_absent_without_a_key():
    from app.services.agent import build_agent_provider

    assert build_agent_provider(_Settings(key="")) is None


def test_provider_is_built_when_configured():
    from app.services.agent import build_agent_provider

    provider = build_agent_provider(_Settings())

    assert provider is not None
    assert "claude-sonnet-5" in provider.name


def test_provider_refuses_an_empty_key_explicitly():
    """Молча собрать провайдера без ключа значило бы отложить ошибку до
    первого запроса — уже внутри анализа."""
    from app.services.agent import ClaudeAgentProvider

    with pytest.raises(ValueError):
        ClaudeAgentProvider(api_key="", model="claude-sonnet-5")
