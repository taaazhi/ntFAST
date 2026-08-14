"""Исполняемые гарантии по схеме БД и приватности.

Оба класса проверок закрывают ошибки, которые уже случались в проекте и
которые невозможно заметить глазами: они не роняют приложение, а тихо
приводят к потере данных или к утечке персональных данных.
"""
import glob
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import Base
from app.services.privacy import Anonymizer
from app.services.privacy.anonymizer import anonymize_transactions
from app.services.bank_analyzer.base_parser import (
    Transaction, TransactionType, CounterpartyType,
)
from datetime import datetime

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "models")
ALEMBIC_ENV = os.path.join(os.path.dirname(__file__), "..", "alembic", "env.py")


class TestSchemaRegistration:
    """Каждая модель обязана быть видима для alembic.

    Autogenerate сравнивает БД с Base.metadata. Модель, не импортированная в
    alembic/env.py, выглядит как таблица, которой нет в коде, — и в миграцию
    попадает DROP TABLE. Так едва не потерялась таблица notifications.
    """

    def _model_modules(self):
        return {
            os.path.basename(f)[:-3]
            for f in glob.glob(os.path.join(MODELS_DIR, "*.py"))
        } - {"__init__"}

    def test_every_model_module_is_imported_by_alembic(self):
        env_src = open(ALEMBIC_ENV, encoding="utf-8").read()
        imported = set(re.findall(r'from app\.models\.(\w+) import', env_src))
        missing = self._model_modules() - imported
        assert not missing, (
            f"Модели не импортированы в alembic/env.py: {sorted(missing)}. "
            f"Autogenerate выпишет для их таблиц DROP TABLE."
        )

    def test_metadata_covers_every_model_module(self):
        # Импорт ради регистрации в Base.metadata
        from app.models import (  # noqa: F401
            analysis, email_verification, login_history,
            notification, subject, transaction, user,
        )
        assert len(Base.metadata.tables) >= len(self._model_modules())
        assert "notifications" in Base.metadata.tables


def _tx(amount: float, description: str, counterparty: str) -> Transaction:
    return Transaction(
        date=datetime(2026, 3, 14, 12, 0),
        amount=amount,
        type=TransactionType.TRANSFER_OUT if amount < 0 else TransactionType.INCOME,
        description=description,
        counterparty=counterparty,
        counterparty_type=CounterpartyType.PERSON,
    )


class TestAnonymizerBlocksPII:
    """Ничто, идентифицирующее физлицо, не должно попасть в исходящий payload.

    Это техническая половина обещания «персональные данные не покидают
    сервер», на котором стоит вся схема с облачной моделью.
    """

    OWNER = "Тажи Нурдаулет Ерланович"

    def test_owner_name_is_masked(self):
        anon = Anonymizer(self.OWNER)
        out = anon.text(f"Перевод от {self.OWNER} по договору")
        assert self.OWNER not in out
        assert "[CUSTOMER]" in out

    def test_iin_iban_card_phone_are_masked(self):
        anon = Anonymizer(self.OWNER)
        raw = "ИИН 901231300123 счёт KZ90722C000042630910 карта 4400 4302 1234 5678 тел +7 701 234 56 78"
        out = anon.text(raw)
        assert anon.leaks(out) == []
        for secret in ("901231300123", "KZ90722C000042630910", "4400", "701"):
            assert secret not in out

    def test_counterparty_person_is_tagged_and_stable(self):
        """Один человек — всегда один тег, чтобы модель видела повторные связи."""
        anon = Anonymizer(self.OWNER)
        first = anon.counterparty("Ержан О.")
        second = anon.counterparty("Ержан О.")
        other = anon.counterparty("Айгуль С.")
        assert first == second != other
        assert first.startswith("[PERSON_")

    def test_organisations_survive(self):
        """Мерчанты нужны модели для оценки риска и не являются ПД."""
        anon = Anonymizer(self.OWNER)
        for org in ("1XBET", 'TOO "KASPI MAGAZIN"', "Magnum Cash&Carry", "Binance"):
            assert anon.counterparty(org) == org

    def test_sole_trader_keeps_legal_form_but_loses_the_name(self):
        """ИП — физлицо: ФИО маскируем, правовую форму оставляем."""
        anon = Anonymizer(self.OWNER)
        out = anon.counterparty('ИП "КОНДРАТОВА А.Н."')
        assert "КОНДРАТОВА" not in out
        assert "ИП" in out

    def test_person_name_ending_in_period_is_caught(self):
        """Регресс: `\\b` не срабатывает после точки, и «Ержан О.» утекал."""
        anon = Anonymizer(self.OWNER)
        anon.register(["Ержан О."])
        out = anon.text("Перевод Ержан О. на карту")
        assert "Ержан" not in out

    def test_pipeline_leaves_no_identifiers(self):
        """Сквозная проверка: описание и контрагент чистятся согласованно."""
        txs = [
            _tx(-1300, "Ержан О.", "Ержан О."),
            _tx(4000, "Айнель У.", "Айнель У."),
            _tx(-995, 'TOO "KASPI MAGAZIN"', 'TOO "KASPI MAGAZIN"'),
            _tx(-500, f"Перевод {self.OWNER} ИИН 901231300123", self.OWNER),
        ]
        safe, report = anonymize_transactions(txs, self.OWNER)

        payload = str(safe)
        checker = Anonymizer(self.OWNER)
        checker.register(t.counterparty for t in txs)
        assert checker.leaks(payload) == [], f"Утечка ПД в payload: {payload}"

        # Мерчант остался — иначе анализ риска потеряет смысл
        assert any("KASPI MAGAZIN" in s["counterparty"] for s in safe)
        assert report.total > 0

    def test_amounts_and_dates_survive(self):
        """Маскирование не должно портить данные, нужные для анализа."""
        txs = [_tx(-1300, "Ержан О.", "Ержан О.")]
        safe, _ = anonymize_transactions(txs, self.OWNER)
        assert safe[0]["amount"] == -1300
        assert safe[0]["date"].startswith("2026-03-14")
