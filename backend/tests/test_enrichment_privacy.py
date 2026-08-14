"""Гарантия приватности: что именно уходит в облачную модель.

Это не тест на аккуратность, а проверка обещания. ntFAST работает с
банковскими выписками граждан Казахстана в интересах следственных органов,
и закон РК «О персональных данных и их защите» (№94-V) не позволяет
пересылать эти данные третьей стороне просто потому, что так удобнее
классифицировать контрагентов.

Проверяем не код анонимизатора — у него свои тесты, — а стык: тот единственный
путь, по которому данные покидают периметр. Провайдер здесь подставной и
записывает всё, что ему передали; на этих записях и ищем утечку.

Организации маскировать не нужно и вредно: «ТОО Астана Строй» персональными
данными не является, а без названия оценка риска мерчанта бессмысленна. Тесты
это фиксируют отдельно, иначе «починка» утечки однажды заодно вычистит и их.
"""
from datetime import datetime

import pytest

from app.services.bank_analyzer.base_parser import Transaction, TransactionType
from app.services.enrichment import enrich_transactions

#: Персональные данные, которых в исходящем трафике быть не должно.
OWNER = "Тажибаев Нурдаулет Ерланович"
IIN = "950101300123"
IBAN = "KZ86125KZT5004100100"
CARD = "4400 4301 2345 6789"
PHONE = "+7 701 234 56 78"
PEOPLE = ("Ержан О.", "Аружан С.", "Омаров Ержан Болатович")

#: Организации — наоборот, обязаны доходить до модели без изменений.
ORGANISATIONS = ("ТОО Астана Строй", "Magnum", "Kaspi Gold")


class RecordingAI:
    """Провайдер, который ничего не решает, но всё запоминает."""

    def __init__(self):
        self.prompts = []
        self.system_prompts = []

    async def generate_structured(self, prompt, schema, system_prompt=""):
        self.prompts.append(prompt)
        self.system_prompts.append(system_prompt)
        return {"counterparties": []}, "RecordingAI"

    @property
    def outgoing(self) -> str:
        """Всё, что ушло наружу, одной строкой."""
        return "\n".join(self.prompts + self.system_prompts)


def tx(counterparty, description="", amount=-1000.0, day=5):
    return Transaction(
        date=datetime(2025, 1, day),
        amount=amount,
        type=TransactionType.EXPENSE if amount < 0 else TransactionType.INCOME,
        description=description,
        counterparty=counterparty,
    )


@pytest.fixture
def sensitive_transactions():
    """Выписка, где ПД разложены по всем полям, куда они реально попадают."""
    return [
        tx("Ержан О.", f"Перевод Ержан О., ИИН {IIN}"),
        tx("Аружан С.", f"Перевод на карту {CARD}"),
        tx("Омаров Ержан Болатович", f"Счёт {IBAN}"),
        tx(OWNER, f"Перевод себе, тел. {PHONE}", amount=50_000),
        tx("ТОО Астана Строй", "Оплата услуг", amount=500_000),
        tx("Magnum", "Покупка продуктов"),
        tx("Kaspi Gold", "Пополнение"),
    ]


def run(transactions, ai):
    return enrich_transactions(transactions, ai_manager=ai, owner_name=OWNER)


# ── Утечки ───────────────────────────────────────────────────────

@pytest.mark.parametrize("secret", [IIN, IBAN, CARD, PHONE])
def test_identifiers_never_leave(sensitive_transactions, secret):
    """ИИН/ЖСН, IBAN, номер карты и телефон — прямые идентификаторы."""
    ai = RecordingAI()
    run(sensitive_transactions, ai)

    assert secret not in ai.outgoing
    assert secret.replace(" ", "") not in ai.outgoing.replace(" ", "")


@pytest.mark.parametrize("person", PEOPLE)
def test_counterparty_names_never_leave(sensitive_transactions, person):
    """Имена контрагентов-физлиц — тоже персональные данные.

    Их легко упустить: маскируют владельца счёта и на этом останавливаются,
    хотя список контактов человека раскрывает не меньше.
    """
    ai = RecordingAI()
    run(sensitive_transactions, ai)

    assert person not in ai.outgoing


def test_account_owner_never_leaves(sensitive_transactions):
    ai = RecordingAI()
    run(sensitive_transactions, ai)

    assert OWNER not in ai.outgoing
    for part in OWNER.split():
        assert part not in ai.outgoing, part


def test_surname_alone_never_leaves(sensitive_transactions):
    """Владелец фигурирует в выписке и сокращённо — «Тажибаев Н.»."""
    ai = RecordingAI()
    run(sensitive_transactions, ai)

    assert "Тажибаев" not in ai.outgoing


# ── Обратная сторона: организации должны доходить ────────────────

@pytest.mark.parametrize("org", ORGANISATIONS)
def test_organisations_are_sent_intact(sensitive_transactions, org):
    """Маскировать их незачем, а без них модель бесполезна: весь смысл
    вызова — узнать, что такое «Magnum»."""
    ai = RecordingAI()
    run(sensitive_transactions, ai)

    assert org in ai.outgoing


# ── Отчёт о маскировании ─────────────────────────────────────────

def test_privacy_report_is_returned(sensitive_transactions):
    """Что замаскировано — часть результата анализа, а не деталь реализации:
    следователь должен видеть, что именно ушло наружу."""
    ai = RecordingAI()
    result = run(sensitive_transactions, ai)

    assert result["privacy"] is not None
    assert sum(v for v in result["privacy"].values() if isinstance(v, int)) > 0


def test_nothing_leaves_when_no_model_configured(sensitive_transactions):
    """Без провайдера сеть не трогается вовсе, и отчёта о маскировании нет —
    маскировать было нечего, данные периметр не покидали."""
    result = enrich_transactions(sensitive_transactions, ai_manager=None)

    assert result["privacy"] is None
    assert result["classified"] > 0


# ── Классификации всё ещё доезжают до транзакций ─────────────────

@pytest.mark.anyio
async def test_classifications_map_back_to_original_names():
    """Модель отвечает про обезличенные имена, а проставить нужно в исходные.

    Если сопоставление сломается, приватность формально соблюдена, но
    обогащение молча перестанет работать — худший вид отказа.
    """
    from app.services.bank_analyzer.base_parser import CounterpartyType

    class Classifying:
        async def generate_structured(self, prompt, schema, system_prompt=""):
            lines = [l for l in prompt.splitlines() if l and l[0].isdigit()]
            return {
                "counterparties": [
                    {"index": i, "kind": "merchant", "confidence": 0.9,
                     "merchant_name": "Magnum"}
                    for i, line in enumerate(lines) if "Magnum" in line
                ]
            }, "Classifying"

    transactions = [tx("Magnum", "Покупка"), tx("Ержан О.", "Перевод")]
    enrich_transactions(transactions, ai_manager=Classifying(), owner_name=OWNER)

    assert transactions[0].counterparty_type is CounterpartyType.MERCHANT
    assert transactions[0].merchant_name == "Magnum"
    assert transactions[1].counterparty_type is CounterpartyType.PERSON
