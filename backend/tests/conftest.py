"""
Shared fixtures for fraud engine tests
"""
import sys
import os
import pytest
from datetime import datetime, timedelta
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.bank_analyzer.base_parser import (
    Transaction, TransactionType, CounterpartyType, AccountInfo
)
from app.services.fraud.models import AccountProfile, AccountType


# ── Helper: create transactions ──────────────────────────────────

def make_tx(
    amount: float,
    days_ago: int = 0,
    hours: int = 12,
    description: str = "",
    counterparty: str = "",
    tx_type: TransactionType = TransactionType.OTHER,
    cp_type: CounterpartyType = CounterpartyType.UNKNOWN,
    merchant_name: str = "",
    is_salary: bool = False,
    is_pension: bool = False,
    is_atm: bool = False,
    is_deposit: bool = False,
    is_cash: bool = False,
) -> Transaction:
    return Transaction(
        date=datetime(2025, 6, 15, hours, 0) - timedelta(days=days_ago),
        amount=amount,
        type=tx_type,
        description=description or f"TX {amount}",
        counterparty=counterparty,
        counterparty_type=cp_type,
        merchant_name=merchant_name,
        is_salary=is_salary,
        is_pension_benefit=is_pension,
        is_atm=is_atm,
        is_deposit_operation=is_deposit,
        is_cash_operation=is_cash,
    )


# ── Fixture: clean salary employee (normal person) ──────────────

@pytest.fixture
def clean_salary_transactions() -> List[Transaction]:
    """Normal salary employee: monthly salary + daily shopping"""
    txs = []
    for month in range(6):
        # Salary income on 5th of each month
        txs.append(make_tx(
            500_000, days_ago=month * 30 + 5,
            description="Зарплата ТОО Компания",
            counterparty="ТОО Компания",
            tx_type=TransactionType.INCOME,
            is_salary=True,
        ))
        # Regular expenses throughout month
        for day in range(20):
            txs.append(make_tx(
                -3_500, days_ago=month * 30 + day,
                description="Magnum Cash&Carry",
                counterparty="Magnum",
                tx_type=TransactionType.EXPENSE,
                merchant_name="Magnum",
            ))
            txs.append(make_tx(
                -1_200, days_ago=month * 30 + day,
                description="YANDEX.GO поездка",
                counterparty="Yandex.Go",
                tx_type=TransactionType.EXPENSE,
            ))
        # Rent payment
        txs.append(make_tx(
            -150_000, days_ago=month * 30 + 1,
            description="Перевод Аренда квартира",
            counterparty="Марат К.",
        ))
    return txs


@pytest.fixture
def clean_salary_profile() -> AccountProfile:
    return AccountProfile(
        account_type=AccountType.SALARY_EMPLOYEE,
        avg_monthly_income=500_000,
        avg_monthly_expense=350_000,
        income_regularity_score=0.9,
        monthly_income_cv=0.05,
        has_salary_flag=True,
        income_source_count=1,
        unique_income_sources=1,
        unique_expense_destinations=15,
    )


# ── Fixture: fraudster (money laundering patterns) ──────────────

@pytest.fixture
def fraudster_transactions() -> List[Transaction]:
    """Fraudster: many P2P transfers, round amounts, shell companies, night activity"""
    txs = []
    for month in range(6):
        # Large P2P inflows from many sources
        for i in range(15):
            txs.append(make_tx(
                500_000, days_ago=month * 30 + i,
                description=f"Перевод от Person_{i}",
                counterparty=f"Person_{i}",
                tx_type=TransactionType.TRANSFER_IN,
            ))
        # Rapid outflows to shell companies
        for i in range(10):
            txs.append(make_tx(
                -500_000, days_ago=month * 30 + i,
                description=f"ТОО Global Invest Consult {i}",
                counterparty=f"ТОО Global Invest Consult {i}",
                tx_type=TransactionType.TRANSFER_OUT,
            ))
        # Gambling
        txs.append(make_tx(
            -200_000, days_ago=month * 30 + 2,
            description="1XBET ставка",
            counterparty="1XBET",
            tx_type=TransactionType.EXPENSE,
        ))
        # Structuring: amounts just under 1M threshold
        for i in range(5):
            txs.append(make_tx(
                -950_000 + i * 1000, days_ago=month * 30 + 3,
                description=f"Перевод Person_out_{i}",
                counterparty=f"Person_out_{i}",
            ))
        # Night transfers
        txs.append(make_tx(
            -800_000, days_ago=month * 30 + 5, hours=3,
            description="Ночной перевод",
            counterparty="Unknown Person",
        ))
    return txs


@pytest.fixture
def fraudster_profile() -> AccountProfile:
    return AccountProfile(
        account_type=AccountType.UNKNOWN,
        avg_monthly_income=200_000,
        avg_monthly_expense=5_000_000,
        income_regularity_score=0.1,
        monthly_income_cv=1.5,
        has_salary_flag=False,
        income_source_count=15,
        unique_income_sources=15,
        unique_expense_destinations=40,
    )


# ── Fixture: account info ──────────────────────────────────────

@pytest.fixture
def default_account_info() -> AccountInfo:
    return AccountInfo(
        owner="Test User",
        account_number="KZ123456789",
        bank_name="Kaspi Bank",
        currency="KZT",
    )
