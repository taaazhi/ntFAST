"""Заключение по выписке: связный вывод и всё, что его проверяет.

Это единственное место, где языковая модель делает работу, которую нечем
заменить: собрать факты из одиннадцати модулей, обогащения, графа связей и
корпуса норм в текст, который читает следователь. Правилами такой текст не
пишется.

Поэтому и проверок здесь больше, чем где-либо. Заключение идёт в материалы
дела: выдуманная сумма или норма в нём опаснее, чем отсутствие заключения
вовсе. Каждый тест ниже соответствует ошибке, которую живая модель уже
допустила на реальной выписке.
"""
import pytest

from app.services.agent.conclusion import (
    Conclusion,
    build_conclusion,
    collect_facts,
    find_invented_numbers,
)


class FakeProvider:
    """Отдаёт заранее заданный текст. Считает вызовы."""

    def __init__(self, text="", raises=None, provider="FakeLLM"):
        self._text = text
        self._raises = raises
        self._provider = provider
        self.calls = []

    def run(self, system, messages, tools=None):
        self.calls.append({"system": system, "messages": messages})
        if self._raises:
            raise self._raises
        return {
            "content": [{"type": "text", "text": self._text}],
            "provider": self._provider,
        }


ANALYSIS = {
    "summary": {
        "total_transactions": 1320,
        "total_income": 5540137.44,
        "total_expense": 5558666.95,
        "net_flow": -18529.51,
    },
    "account": {"period": {"from": "2025-08-14", "to": "2026-08-14"}},
    "fraud_report": {
        "composite_score": 12.4,
        "risk_level": "low",
        "graph": {"node_count": 284, "edge_count": 283},
        "account_profile": {"account_type": "unknown"},
        "explained_flags": [
            {"module": "velocity", "reason": "Burst транзакций: 3",
             "counter_evidence": "", "score_contribution": 3.75},
        ],
        "flagged_patterns": [
            {
                "display_name": "Признаки кардинга",
                "reason": "5 мелких покупок за 2 часа.",
                "counter_evidence": "туристические покупки.",
                "confidence": 0.6,
                "legal_articles": [
                    {"citation": "УК РК ст. 232", "title": "Поддельные карточки",
                     "verified": True},
                    {"citation": "УК РК ст. 9999", "title": "", "verified": False},
                ],
            }
        ],
    },
    "enrichment": {"salary_sources": []},
}


# ── Факты, которые получает модель ───────────────────────────────

def test_amounts_are_preformatted_strings():
    """Сырое число модель переводит в миллионы и ошибается: 5 540 137,44
    превращалось в «55,4013744 млн». Готовая строка не оставляет поводов
    считать."""
    facts = collect_facts(ANALYSIS)

    assert facts["total_income"] == "5 540 137 ₸"
    assert facts["net_flow"] == "-18 530 ₸"


def test_account_holder_is_named_explicitly():
    """Без этой строки модель принимала метку контрагента за владельца и
    писала «[PERSON_1] совершил покупки», хотя покупки совершал владелец."""
    assert "владелец" in collect_facts(ANALYSIS)["account_holder"]


def test_unverified_articles_are_not_shown_to_the_model():
    """Непроверенную норму модель процитирует как установленную, поэтому до
    неё она не доходит вовсе."""
    facts = collect_facts(ANALYSIS)
    citations = [a["citation"] for p in facts["patterns"] for a in p["articles"]]

    assert "УК РК ст. 232" in citations
    assert "УК РК ст. 9999" not in citations


def test_counterparties_are_masked_in_facts():
    class _Anon:
        def counterparty(self, name):
            return "[PERSON_1]"

    analysis = dict(ANALYSIS)
    analysis["enrichment"] = {"salary_sources": [{"counterparty": "Ержан О.", "reason": "…"}]}
    facts = collect_facts(analysis, anonymizer=_Anon())

    assert facts["income_sources"][0]["counterparty"] == "[PERSON_1]"


# ── Проверка чисел ───────────────────────────────────────────────

def test_invented_amount_is_caught():
    """Живая модель написала «12 переводов на 4 500 000 ₸» — таких фактов ей
    не давали, она взяла пример из системного промпта."""
    facts = collect_facts(ANALYSIS)

    invented = find_invented_numbers("Выявлено 12 переводов на 4 500 000 ₸.", facts)

    assert "4 500 000" in " ".join(invented)


def test_numbers_from_facts_pass():
    facts = collect_facts(ANALYSIS)

    assert find_invented_numbers(
        "Проведено 1320 операций, доходы 5 540 137 ₸, расходы 5 558 667 ₸.", facts
    ) == []


def test_dates_are_not_treated_as_invented_numbers():
    """Период «2025-08-14» модель законно перепишет как «14.08.2025».
    Регресс: без вырезания дат «14.08» считалось выдуманным числом."""
    facts = collect_facts(ANALYSIS)

    assert find_invented_numbers("В период с 14.08.2025 по 14.08.2026 …", facts) == []


def test_list_numbering_is_ignored():
    """«1.», «2.» — нумерация пунктов, а не факты."""
    facts = collect_facts(ANALYSIS)

    assert find_invented_numbers("1. Первое. 2. Второе. 3. Третье.", facts) == []


# ── Достоверность заключения ─────────────────────────────────────

def test_clean_conclusion_is_trustworthy():
    text = "Проведено 1320 операций. Признаки требуют проверки: УК РК ст. 232."
    conclusion = build_conclusion(ANALYSIS, FakeProvider(text))

    assert conclusion.text == text
    assert conclusion.invented_numbers == []
    assert conclusion.provider == "FakeLLM"


def test_conclusion_with_invented_numbers_is_not_trustworthy():
    conclusion = build_conclusion(
        ANALYSIS, FakeProvider("Оборот составил 99 999 999 ₸.")
    )

    assert conclusion.invented_numbers
    assert conclusion.is_trustworthy is False


def test_foreign_script_is_caught():
    """Qwen2.5 обучена в том числе на китайском, и он прорывается:
    «нулевому流入流出 (net_flow)». В документе для дела это брак."""
    conclusion = Conclusion(text="Итог: 流入流出 за период.")

    assert conclusion.foreign_script
    assert conclusion.is_trustworthy is False


def test_missing_model_produces_no_conclusion_rather_than_a_fake_one():
    """Подделка отсутствующего вывода хуже его отсутствия."""
    conclusion = build_conclusion(ANALYSIS, None)

    assert conclusion.text == ""
    assert conclusion.error
    assert conclusion.is_trustworthy is False


def test_provider_failure_is_reported_not_raised():
    conclusion = build_conclusion(ANALYSIS, FakeProvider(raises=ConnectionError("нет сети")))

    assert "нет сети" in conclusion.error
    assert conclusion.is_trustworthy is False


def test_empty_model_answer_is_an_error():
    conclusion = build_conclusion(ANALYSIS, FakeProvider(""))

    assert conclusion.error
    assert conclusion.is_trustworthy is False


def test_prompt_forbids_computing_and_accusing():
    """Требования — часть промпта, а не устная договорённость."""
    provider = FakeProvider("ok")
    build_conclusion(ANALYSIS, provider)

    # Промпт переносится по строкам, поэтому сравниваем по «схлопнутому» виду.
    system = " ".join(provider.calls[0]["system"].split())

    assert "не вычитай самостоятельно" in system
    assert "Не выноси обвинений" in system
    assert "не предрешай квалификацию" in system


def test_conclusion_serialises_for_the_report():
    payload = build_conclusion(ANALYSIS, FakeProvider("Текст.")).to_dict()

    assert set(payload) >= {"text", "citations", "invented_numbers", "is_trustworthy"}
