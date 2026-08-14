"""Определение зарплаты по поведению платежа, а не по его подписи.

Почему это оказалось важнее всего остального. Абляция на бенчмарке (200
транзакций, незнакомый формат) даёт однозначный результат: композитный
балл риска поднимается с 17.4 LOW до 63.0 HIGH ровно тогда, когда
проставлен `is_salary`. Классификация контрагента не двигает его вообще,
тип операции — на 0.4. Одно булево поле решает, LOW или HIGH.

Причина не в весе флага, а в том, что от него зависит тип счёта.
`AccountProfiler` без зарплаты видит счёт UNKNOWN, с зарплатой —
SALARY_EMPLOYEE, а контекстные веса детекторов у этих профилей разные:
поток P2P-переводов на зарплатной карте аномален, на счёте неизвестного
назначения — нет. Так и работает следователь: ищет несоответствие
заявленному источнику дохода.

Существующий способ проставить флаг — искать слово «зарплата» в тексте
(`account_profiler.SALARY_KEYWORDS`, `halyk.py:384`). На реальной выписке
этого слова обычно нет: приходит `Пополнение` от `ТОО Астана Строй`, и
всё. Ту же картину даёт бенчмарк — 21 зарплатная строка из 200, ни в
одной слово «зарплата» не встречается.

Здесь флаг выводится из поведения: одна и та же организация переводит
сопоставимые суммы примерно в один день месяца несколько месяцев подряд.
Формулировка и язык при этом не важны — на казахском `Толықтыру` от того
же ТОО распознаётся так же, как русское `Пополнение`.
"""
from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from app.services.bank_analyzer.base_parser import CounterpartyType

logger = logging.getLogger(__name__)

#: Меньше трёх поступлений — не ряд, а совпадение. Две подряд одинаковые
#: суммы бывают у возвратов, переводов между своими счетами и рассрочек.
MIN_PAYMENTS = 3

#: Зарплату платят раз в месяц, иногда двумя частями (аванс и остаток).
#: Больше трёх поступлений в месяц от одного источника — уже не зарплата,
#: а выручка или транзит.
MAX_PER_MONTH = 3

#: Допустимый разброс дня выплаты. Аванс 10-го и зарплата 25-го дают
#: разброс около 7 дней, случайные поступления — заметно больше.
MAX_DAY_STDEV = 8.0

#: Коэффициент вариации суммы. Оклад колеблется из-за премий и налогов,
#: но не в разы.
MAX_AMOUNT_CV = 0.6

#: Строки, которые стоят в поле контрагента, но контрагентом не являются:
#: это канал или вид операции. Выписка Kaspi пишет «С карты другого банка»
#: там же, где обычно имя отправителя, и по поведению такие поступления
#: неотличимы от зарплаты — регулярные, сопоставимые, в один день месяца.
#:
#: Проверено на реальных выписках: без этого списка «С карты другого
#: банка» и «Пенсия/пособие» попадали в работодатели. Синтетика такого не
#: показывала — там у каждой строки честное имя контрагента.
#:
#: Список ручной, и в этом его слабость: он покрывает формулировки тех
#: банков, чьи выписки кто-то держал в руках. Другой банк напишет иначе,
#: на казахском или английском, и запись снова станет «работодателем».
GENERIC_SOURCES = (
    # русский
    "с карты другого банка", "с карты", "пополнение", "перевод",
    "входящий перевод", "зачисление", "поступление",
    "пенсия", "пособие", "выплата пособия", "пенсия/пособие",
    # казахский (после приведения латинской Ə к кириллической Ә)
    "басқа банк картасынан", "басқа банктің картасынан", "толықтыру",
    "аударым", "түсім", "зейнетақы", "жәрдемақы", "зейнетақы/жәрдемақы",
    # английский
    "from another bank", "from card of other banks", "top up", "topup",
    "incoming transfer", "deposit", "replenishment",
    "pension", "allowance", "pension/allowance",
)

#: Латинская Ə (U+018F) вместо казахской Ә (U+04D8) — так казахский текст
#: печатается в выписках Kaspi и Halyk.
_SCHWA_NORMALISE = str.maketrans({"Ə": "Ә", "ə": "ә"})


@dataclass
class SalaryFinding:
    """Найденный источник зарплаты — с обоснованием, а не просто флагом."""

    counterparty: str
    payments: int
    months: int
    median_amount: float
    day_of_month: int
    day_stdev: float
    amount_cv: float

    def reason(self) -> str:
        """Формулировка для отчёта следователю."""
        return (
            f"{self.payments} поступлений за {self.months} мес. от «{self.counterparty}», "
            f"медиана {self.median_amount:,.0f} ₸, обычно {self.day_of_month}-го числа "
            f"(разброс {self.day_stdev:.1f} дн., отклонение суммы {self.amount_cv:.0%})"
        ).replace(",", " ")

    def as_dict(self) -> Dict[str, Any]:
        return {
            "counterparty": self.counterparty,
            "payments": self.payments,
            "months": self.months,
            "median_amount": self.median_amount,
            "day_of_month": self.day_of_month,
            "reason": self.reason(),
        }


def _date_of(tx: Any) -> Optional[datetime]:
    value = getattr(tx, "date", None)
    return value if isinstance(value, datetime) else None


def _source_of(tx: Any) -> str:
    for attr in ("counterparty", "merchant_name", "description"):
        value = getattr(tx, attr, None)
        if value and str(value).strip():
            return str(value).strip()
    return ""


#: Длинные маркеры ищутся в любом месте строки, короткие — только целиком
#: или в начале. Причина в порядке слов: русское «Пополнение Kaspi Gold с
#: карты другого банка» начинается с маркера, а казахский вариант той же
#: операции — «Kaspi Gold-ты басқа банктің картасынан толықтыру» — держит
#: его в середине. Искать подстроку для коротких слов нельзя: «перевод»
#: совпадёт с «ТОО Переводчик».
_SUBSTRING_MARKER_LENGTH = 12


def _is_generic_source(name: str) -> bool:
    """Строка описывает канал поступления, а не того, кто платит."""
    normalised = " ".join(name.translate(_SCHWA_NORMALISE).lower().split())
    parts = [p.strip() for p in normalised.split("/")]
    for marker in GENERIC_SOURCES:
        if normalised == marker or normalised.startswith(marker + " ") or marker in parts:
            return True
        if len(marker) >= _SUBSTRING_MARKER_LENGTH and marker in normalised:
            return True
    return False


def _looks_like_employer(transactions: Sequence[Any]) -> bool:
    """Может ли этот источник быть работодателем.

    Отсекаем два случая, найденных на настоящих выписках:

    * физлицо — регулярные переводы от человека это не зарплата;
    * пенсия и пособие — по поведению неотличимы от оклада, но профиль
      счёта задают другой, а от профиля зависят веса всех детекторов.
      Пометить пенсионера наёмным работником значит исказить вывод по
      всему делу, а не одну строку.

    Тип контрагента `UNKNOWN` пропускаем: детектор обязан работать и без
    классификатора.
    """
    kinds = {getattr(t, "counterparty_type", None) for t in transactions}
    if CounterpartyType.PERSON in kinds:
        return False
    if any(getattr(t, "is_pension_benefit", False) for t in transactions):
        return False
    return True


def find_salary_sources(transactions: Sequence[Any]) -> List[SalaryFinding]:
    """Найти источники регулярного дохода, похожие на зарплату."""
    incoming: Dict[str, List[Any]] = defaultdict(list)
    for tx in transactions:
        amount = getattr(tx, "amount", 0) or 0
        source = _source_of(tx)
        if (
            amount > 0
            and source
            and not _is_generic_source(source)
            and _date_of(tx) is not None
        ):
            incoming[source].append(tx)

    findings: List[SalaryFinding] = []
    for source, group in incoming.items():
        if len(group) < MIN_PAYMENTS or not _looks_like_employer(group):
            continue

        dates = [_date_of(t) for t in group]
        months = {(d.year, d.month) for d in dates}
        if len(months) < MIN_PAYMENTS:
            continue
        if len(group) / len(months) > MAX_PER_MONTH:
            continue

        # Разброс дня считаем по первому поступлению каждого месяца:
        # аванс и основная выплата иначе выглядят как хаос.
        first_by_month: Dict[tuple, int] = {}
        for d in dates:
            key = (d.year, d.month)
            first_by_month[key] = min(first_by_month.get(key, 31), d.day)
        days = list(first_by_month.values())
        day_stdev = statistics.stdev(days) if len(days) > 1 else 0.0
        if day_stdev > MAX_DAY_STDEV:
            continue

        amounts = [abs(getattr(t, "amount", 0) or 0) for t in group]
        mean_amount = statistics.mean(amounts)
        if mean_amount <= 0:
            continue
        amount_cv = (statistics.stdev(amounts) / mean_amount) if len(amounts) > 1 else 0.0
        if amount_cv > MAX_AMOUNT_CV:
            continue

        findings.append(SalaryFinding(
            counterparty=source,
            payments=len(group),
            months=len(months),
            median_amount=statistics.median(amounts),
            day_of_month=round(statistics.median(days)),
            day_stdev=day_stdev,
            amount_cv=amount_cv,
        ))

    # Основной работодатель первым: по числу выплат, затем по сумме.
    findings.sort(key=lambda f: (f.payments, f.median_amount), reverse=True)
    return findings


def mark_salary_transactions(transactions: Sequence[Any]) -> List[SalaryFinding]:
    """Проставить `is_salary` по найденным источникам.

    Уже стоящий флаг не снимаем: его мог поставить банк-специфичный
    парсер, увидев прямое указание в выписке, и это надёжнее вывода по
    поведению.
    """
    findings = find_salary_sources(transactions)
    if not findings:
        return []

    salary_sources = {f.counterparty for f in findings}
    for tx in transactions:
        if (getattr(tx, "amount", 0) or 0) > 0 and _source_of(tx) in salary_sources:
            tx.is_salary = True

    logger.info(
        "Зарплатных источников найдено: %d (%s)",
        len(findings), ", ".join(f.counterparty for f in findings[:3]),
    )
    return findings
