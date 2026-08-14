"""Тесты классификатора контрагентов на подставном провайдере.

Ключа API в окружении нет и в CI не будет, поэтому провайдер здесь —
двойник. Это не обход проверки, а её условие: тесты фиксируют поведение
при *сломанной* модели (недоступна, вернула мусор, промахнулась индексом,
не уверена), а такие ответы от настоящего провайдера воспроизвести
надёжно нельзя.

Правило, за которое отвечают эти тесты: сомнительная классификация
отбрасывается и уходит в правило. Композитный балл риска попадает в
материалы уголовного дела, и «модель что-то предположила» там не годится.
"""
import pytest

from app.services.bank_analyzer.base_parser import (
    CounterpartyType, Transaction, TransactionType,
)
from app.services.enrichment import Classification, CounterpartyClassifier, classify_by_rule


class FakeAI:
    """Провайдер с заранее заданными ответами. Считает вызовы."""

    def __init__(self, responses, provider="FakeProvider"):
        self._responses = list(responses)
        self._provider = provider
        self.prompts = []

    async def generate_structured(self, prompt, schema, system_prompt=""):
        self.prompts.append(prompt)
        if not self._responses:
            raise AssertionError("провайдер вызван больше раз, чем ожидалось")
        payload = self._responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return payload, self._provider


def entry(index, kind, confidence=0.9, **extra):
    return {"index": index, "kind": kind, "confidence": confidence, **extra}


def wrap(*entries):
    return {"counterparties": list(entries)}


# ── Дешёвые пути: без обращения к модели ─────────────────────────

@pytest.mark.anyio
async def test_placeholders_never_reach_the_model():
    """Обезличенное имя уже опознано как физлицо. Отправлять наружу нечего,
    и спрашивать не о чем.

    Теги здесь ровно те, что ставит `privacy/anonymizer.py`. Это важно:
    пока паттерн ждал выдуманный «[ФИО-1]», настоящий «[PERSON_1]» не
    распознавался, и обезличенная строка уходила в облако — запрос без
    смысла, зато с сетевым вызовом.
    """
    ai = FakeAI([])  # любой вызов провайдера — падение теста
    classifier = CounterpartyClassifier(ai_manager=ai)

    result = await classifier.classify(["[PERSON_1]", "[CUSTOMER]"])

    assert ai.prompts == []
    assert all(c.counterparty_type is CounterpartyType.PERSON for c in result.values())
    assert classifier.stats.from_anonymizer == 2


@pytest.mark.anyio
async def test_non_person_placeholders_are_not_people():
    """«[IBAN_1]» обезличен, но человеком от этого не стал. Наружу он тоже
    не уходит — гадать по такому тегу нечего."""
    ai = FakeAI([])
    classifier = CounterpartyClassifier(ai_manager=ai)

    result = await classifier.classify(["[IBAN_1]", "[CARD_2]"])

    assert ai.prompts == []
    assert all(c.counterparty_type is CounterpartyType.UNKNOWN for c in result.values())


@pytest.mark.anyio
async def test_duplicates_are_classified_once():
    """1320 транзакций Kaspi дают 329 уникальных контрагентов — дедупликация
    экономит вчетверо ещё до кэша."""
    ai = FakeAI([wrap(entry(0, "merchant"))])
    classifier = CounterpartyClassifier(ai_manager=ai)

    await classifier.classify(["Magnum", "Magnum", " Magnum ", "Magnum"])

    assert len(ai.prompts) == 1
    assert classifier.stats.total == 1


@pytest.mark.anyio
async def test_merchants_are_cached_but_people_are_not():
    """Название организации персональными данными не является и кэшируется.
    Имя человека — является, и в общий кэш попасть не должно никогда."""
    cache = {}
    ai = FakeAI([wrap(entry(0, "merchant"), entry(1, "person"))])
    classifier = CounterpartyClassifier(ai_manager=ai, cache=cache)

    await classifier.classify(["ТОО Астана Строй", "Ержан Омаров"])

    assert "ТОО Астана Строй" in cache
    assert "Ержан Омаров" not in cache


@pytest.mark.anyio
async def test_cache_hit_skips_the_provider():
    cache = {"Magnum": Classification(CounterpartyType.MERCHANT, "Magnum", source="llm")}
    ai = FakeAI([])
    classifier = CounterpartyClassifier(ai_manager=ai, cache=cache)

    result = await classifier.classify(["Magnum"])

    assert ai.prompts == []
    assert classifier.stats.from_cache == 1
    assert result["Magnum"].merchant_name == "Magnum"


# ── Сломанная модель: система обязана деградировать, а не падать ──

@pytest.mark.anyio
async def test_provider_failure_falls_back_to_rules():
    """Нет ключа, нет сети, упал Ollama — анализ продолжается."""
    ai = FakeAI([ConnectionError("provider is down")])
    classifier = CounterpartyClassifier(ai_manager=ai)

    result = await classifier.classify(["ТОО Астана Строй"])

    assert result["ТОО Астана Строй"].counterparty_type is CounterpartyType.MERCHANT
    assert result["ТОО Астана Строй"].source == "rule"
    assert classifier.stats.llm_failures == 1


@pytest.mark.anyio
async def test_no_provider_at_all_still_classifies():
    classifier = CounterpartyClassifier(ai_manager=None)

    result = await classifier.classify(["ТОО Астана Строй", "Ержан О."])

    assert result["ТОО Астана Строй"].counterparty_type is CounterpartyType.MERCHANT
    assert classifier.stats.from_rule == 2


@pytest.mark.parametrize("bad", [
    {"counterparties": "не массив"},
    {"нет нужного ключа": []},
    "просто строка",
    None,
    {"counterparties": ["строка вместо объекта"]},
])
@pytest.mark.anyio
async def test_malformed_responses_are_discarded(bad):
    ai = FakeAI([bad])
    classifier = CounterpartyClassifier(ai_manager=ai)

    result = await classifier.classify(["Нечто"])

    assert result["Нечто"].source == "rule"


@pytest.mark.anyio
async def test_index_out_of_range_is_ignored():
    """Модель промахнулась номером — приписать классификацию чужому
    контрагенту хуже, чем не приписать никакой."""
    ai = FakeAI([wrap(entry(7, "merchant"))])
    classifier = CounterpartyClassifier(ai_manager=ai)

    result = await classifier.classify(["Magnum"])

    assert result["Magnum"].source == "rule"


@pytest.mark.anyio
async def test_invented_kind_is_ignored():
    ai = FakeAI([wrap(entry(0, "криптобиржа-инопланетян"))])
    classifier = CounterpartyClassifier(ai_manager=ai)

    result = await classifier.classify(["Нечто"])

    assert result["Нечто"].source == "rule"


@pytest.mark.anyio
async def test_low_confidence_is_rejected():
    """Порог по уверенности — не украшение: балл риска идёт в дело."""
    ai = FakeAI([wrap(entry(0, "merchant", confidence=0.1))])
    classifier = CounterpartyClassifier(ai_manager=ai, min_confidence=0.4)

    result = await classifier.classify(["Нечто"])

    assert result["Нечто"].source == "rule"


@pytest.mark.anyio
async def test_partial_batch_keeps_what_is_valid():
    """Одна плохая запись не должна обесценивать остальной батч."""
    ai = FakeAI([wrap(entry(0, "merchant"), entry(1, "выдумка"))])
    classifier = CounterpartyClassifier(ai_manager=ai)

    result = await classifier.classify(["Magnum", "Загадка"])

    assert result["Magnum"].source == "llm"
    assert result["Загадка"].source == "rule"


@pytest.mark.anyio
async def test_batching_splits_large_inputs():
    ai = FakeAI([wrap(entry(0, "merchant")), wrap(entry(0, "merchant"))])
    classifier = CounterpartyClassifier(ai_manager=ai, batch_size=1)

    await classifier.classify(["Первый", "Второй"])

    assert len(ai.prompts) == 2
    assert classifier.stats.llm_batches == 2


# ── Перенос в транзакции ─────────────────────────────────────────

@pytest.mark.anyio
async def test_apply_fills_only_empty_fields():
    """Банк-специфичный парсер знает свою выписку лучше, чем модель — общий
    текст. Уже заполненное не перезаписываем."""
    ai = FakeAI([wrap(entry(0, "merchant", merchant_name="Yandex Go", category="транспорт"))])
    classifier = CounterpartyClassifier(ai_manager=ai)

    def tx(**overrides):
        return Transaction(
            date=None, amount=-100.0, type=TransactionType.EXPENSE,
            description="", counterparty="Yandex Go poezdka", **overrides
        )

    fresh = tx()
    known = tx(
        counterparty_type=CounterpartyType.BANK,
        merchant_name="уже известно",
        category="уже категоризовано",
    )

    mapping = await classifier.classify(["Yandex Go poezdka"])
    changed = classifier.apply([fresh, known], mapping)

    # Пустая транзакция заполнена целиком…
    assert fresh.counterparty_type is CounterpartyType.MERCHANT
    assert fresh.merchant_name == "Yandex Go"
    assert fresh.category == "транспорт"

    # …а у заполненной не тронуто ни одно поле.
    assert known.counterparty_type is CounterpartyType.BANK
    assert known.merchant_name == "уже известно"
    assert known.category == "уже категоризовано"
    assert changed == 1


@pytest.mark.anyio
async def test_merchant_name_not_carried_over_for_people():
    """Модель может заполнить merchant_name у физлица. В транзакцию это
    попасть не должно: там окажется имя человека."""
    ai = FakeAI([wrap(entry(0, "person", merchant_name="Ержан Омаров"))])
    classifier = CounterpartyClassifier(ai_manager=ai)

    mapping = await classifier.classify(["Ержан Омаров"])

    assert mapping["Ержан Омаров"].merchant_name is None


def test_rule_recognises_kazakh_legal_forms():
    """ЖШС и АҚ — казахские написания ТОО и АО."""
    assert classify_by_rule('ЖШС "Астана Строй"').merchant_type == "ТОО"
    assert classify_by_rule('АҚ "Казпочта"').merchant_type == "АО"


def test_rule_separates_organisations_from_people():
    """Что правило действительно умеет — и это стоит зафиксировать, чтобы не
    приписывать модели чужую заслугу. Бинарное разделение «организация или
    человек» оно делает почти безошибочно."""
    for name in ("Yandex Go poezdka", "Магнум", "ТОО Астана Строй", "Kaspi Gold"):
        assert classify_by_rule(name).counterparty_type is CounterpartyType.MERCHANT, name
    for name in ("Ержан О.", "Ержан Омаров", "Аружан С."):
        assert classify_by_rule(name).counterparty_type is not CounterpartyType.MERCHANT, name


def test_rule_cannot_tell_a_bank_from_a_shop():
    """А вот здесь оно бессильно, и это настоящая граница.

    `is_organization` возвращает bool: организация или нет. Банк, госорган и
    магазин для него неразличимы, хотя детекторы взвешивают их по-разному —
    перевод в госорган это налог, а такой же перевод в незнакомое ТОО может
    быть выводом средств.
    """
    for name in ("Kaspi Gold", "Комитет госдоходов", "Магнум"):
        assert classify_by_rule(name).counterparty_type is CounterpartyType.MERCHANT, name


def test_rule_keeps_technical_noise_in_the_merchant_name():
    """Мерчант из выписки приходит с мусором. Правило переносит строку как
    есть, поэтому «Yandex Go poezdka 12.05» и «Yandex Go poezdka» станут
    двумя разными узлами в графе контрагентов."""
    assert classify_by_rule("Yandex Go poezdka").merchant_name == "Yandex Go poezdka"
