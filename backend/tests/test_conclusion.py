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
    finalise_conclusion,
    split_ready_text,
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


def test_verified_article_text_reaches_the_model():
    """Заземление: текст подтверждённой нормы попадает в факты, чтобы модель
    квалифицировала по нему, а не по памяти. Непроверенную норму не показываем
    вовсе — вместе с её текстом."""
    analysis = {
        "summary": {}, "account": {}, "enrichment": {},
        "fraud_report": {
            "flagged_patterns": [{
                "display_name": "Схема",
                "legal_articles": [
                    {"citation": "УК РК ст. 218", "title": "Легализация",
                     "text": "1. Вовлечение в законный оборот денег, полученных "
                             "преступным путём, посредством совершения сделок.",
                     "verified": True},
                    {"citation": "УК РК ст. 9999", "title": "", "text": "",
                     "verified": False},
                ],
            }],
        },
    }
    articles = collect_facts(analysis)["patterns"][0]["articles"]

    assert len(articles) == 1, "непроверенная норма не должна попадать в факты"
    assert articles[0]["citation"] == "УК РК ст. 218"
    assert "Вовлечение" in articles[0]["text"], "текст нормы должен дойти до модели"


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


# ── Разбор чисел: запятая как разделитель разрядов ───────────────────

def test_thousands_separator_is_not_a_decimal_point():
    """«84,000» — это 84 000, а не 84.

    Модель обучена в основном на английском и ставит запятую между
    разрядами. Пока проверка считала её десятичной, верные суммы попадали
    в список выдуманных: заключение объявлялось недостоверным за то, что
    в нём всё правильно.
    """
    facts = {"total_income": "84 000 ₸", "net_flow": "4 500 ₸"}
    text = "Поступления составили 84,000 ₸, итог — 4,500 ₸."
    assert find_invented_numbers(text, facts) == []


def test_decimal_comma_still_works():
    """Запятая с коротким хвостом остаётся десятичной: «63,5» — это 63.5."""
    facts = {"risk_score": 63.5}
    assert find_invented_numbers("Балл риска 63,5.", facts) == []


def test_number_lists_do_not_merge():
    """«12, 15» — два числа, а не одно."""
    facts = {"a": 12, "b": 15}
    assert find_invented_numbers("Признаки 12, 15 сработали.", facts) == []


def test_invented_number_is_still_caught():
    """Починка разбора не должна ослабить саму проверку."""
    facts = {"total_income": "84 000 ₸"}
    assert "158" in find_invented_numbers("Доход 84,000 ₸, а также 158 переводов.", facts)


# ── Оборванный текст ─────────────────────────────────────────────────

def test_truncated_conclusion_is_not_trustworthy():
    """Заключение, упёршееся в потолок длины, оборвано на полуслове.

    Выглядит оно законченным, поэтому признак обязателен: следователь
    должен видеть, что текст неполон, а не догадываться об этом.
    """
    truncated = Conclusion(text="Заключение по делу: установлено, что", truncated=True)
    assert not truncated.is_trustworthy
    assert truncated.to_dict()["truncated"] is True


# ── Потоковая выдача ─────────────────────────────────────────────────

def test_incomplete_tag_is_held_back():
    """Начало метки не показывают: имя подставляется по целой метке.

    Модель присылает «[PERSON» одним куском, «_1]» следующим. Покажи мы
    первую половину — следователь увидел бы обрывок, который через миг
    сменился бы именем.
    """
    ready, pending = split_ready_text("Крупнейший получатель — [PERS")
    assert ready == "Крупнейший получатель — "
    assert pending == "[PERS"


def test_complete_tag_goes_out_at_once():
    ready, pending = split_ready_text("Получатель [PERSON_1] и далее")
    assert ready == "Получатель [PERSON_1] и далее"
    assert pending == ""


def test_text_without_tags_is_never_delayed():
    """Обычный текст не должен ждать: иначе поток теряет смысл."""
    ready, pending = split_ready_text("За период проведено 214 операций.")
    assert pending == ""
    assert ready == "За период проведено 214 операций."


def test_stream_and_plain_paths_check_the_same_way():
    """Оба пути обязаны проверять текст одинаково.

    Разойдись они, «достоверно» значило бы разное в зависимости от того,
    как заключение было доставлено.
    """
    facts = {"transactions": 214, "total_income": "84 000 ₸"}
    text = "За период 214 операций на 84 000 ₸, а также 158 переводов."

    checked = finalise_conclusion(text, facts, provider_name="test")
    assert checked.invented_numbers == ["158"]
    assert not checked.is_trustworthy
