"""Маскирование персональных данных в банковских выписках.

Назначение: ни один прямой идентификатор физического лица не должен покидать
сервер. Модуль вызывается ПЕРЕД любой отправкой данных во внешнюю модель;
локальные (rule-based) модули анализа работают с исходными данными.

Что маскируется:
  * ФИО владельца счёта — во всех встречающихся вариантах написания
  * ИИН / ЖСН (12 цифр) — прямой идентификатор гражданина РК
  * IBAN и номера карт
  * телефоны
  * имена контрагентов-ФИЗИЧЕСКИХ ЛИЦ

Что НЕ маскируется — и это осознанно:
  названия организаций (ТОО, ИП, АО, торговые марки). Без «1XBET»,
  «Binance» или «ТОО Глобал Инвест» модель не сможет рассуждать о рисковых
  мерчантах и подставных фирмах, а это половина ценности анализа.
  Юридическое лицо персональными данными не является.

Граница формулируется одной фразой: наружу уходят суммы, даты, категории и
названия организаций; ни одно физическое лицо не идентифицируемо.

Замены детерминированы в пределах одного отчёта: один и тот же контрагент
всегда получает один и тот же тег ([COUNTERPARTY_3]), поэтому модель по-прежнему
видит связи «этот же человек снова получил перевод», не зная, кто это.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from app.utils.helpers import is_organization

# ── Паттерны прямых идентификаторов ───────────────────────────────
# ИИН (физлицо) и БИН (юрлицо) в РК — оба 12 цифр. Маскируем оба:
# различить их по одному номеру нельзя, а ошибиться в сторону утечки нельзя.
IIN_PATTERN = re.compile(r'\b\d{12}\b')
# Казахстанский IBAN: KZ + 2 контрольные + 16 буквенно-цифровых
IBAN_PATTERN = re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b')
CARD_PATTERN = re.compile(r'\b(?:\d{4}[\s*-]{0,3}){3}\d{4}\b|\*\d{4}\b')
PHONE_PATTERN = re.compile(r'\+?[78][\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}')

# Кириллица + казахские буквы, включая латинскую шва Ə/ə, которой Kaspi
# печатает казахские имена (см. parsers/kaspi.py).
_CYR = r'А-ЯЁӘҒҚҢӨҰҮІҺа-яёәғқңөұүіһƏə'

# «Ержан О.» / «Айгуль С.» — типичная форма контрагента-физлица в выписках РК
PERSON_INITIAL_PATTERN = re.compile(rf'^[{_CYR}][{_CYR}]+\s+[{_CYR}]\.?$')

# То же ФИО, но найденное ВНУТРИ строки: «ИП "КОНДРАТОВА А.Н."».
# Индивидуальный предприниматель — юридически физическое лицо, и его ФИО
# остаётся персональными данными, хотя формально это название бизнеса.
# Маскируем имя, сохраняя правовую форму: модели для оценки риска достаточно
# знать «это ИП», а не кто конкретно за ним стоит.
PERSON_IN_TEXT_PATTERN = re.compile(
    rf'[{_CYR}][{_CYR}]+\s+[{_CYR}]\.\s*(?:[{_CYR}]\.)?'
)

# Правовая форма индивидуального предпринимателя: русская, казахская и
# английская записи. Сохраняется в открытом виде — сама по себе она никого
# не идентифицирует, а для оценки риска знать «это ИП» полезно.
SOLE_TRADER_PREFIX = re.compile(
    r'^(ИП|ЖК|И\.П\.|IP)\s*[.\-—:]?\s*(.+)$', re.IGNORECASE
)

# Что стоит после «ИП» и должно быть скрыто.
#
# Проверка на реальных выписках показала, что маскировался лишь один формат —
# «ИП "КОНДРАТОВА А.Н."», с инициалами и точками. Остальные уходили наружу
# открытым текстом: «ИП КОНРАТБАЕВА МАДИНА БАГДАДОВНА», «ИП АБИШЕВ Р А»,
# «ИП КАРИМБЕКОВ». Индивидуальный предприниматель — физическое лицо, его ФИО
# защищено законом РК №94-V, и CLAUDE.md обещает его маскировать.
#
# Кириллическое слово после «ИП» скрывается даже одиночное: в Казахстане это
# практически всегда фамилия («КАРИМБЕКОВ») или имя («АЛИХАН», «ДИНАРА»).
# Ошибка в эту сторону стоит части аналитики по мерчанту, ошибка в обратную —
# нарушение закона в документе для следствия. Латиница остаётся: «ИП BEREKET»,
# «ИП SAVA BRANDS» — торговые марки, а не имена.
SOLE_TRADER_NAME = re.compile(rf'^["«\']?\s*[{_CYR}]')

#: Кавычки и пробелы, обрамляющие название: «ИП "КОНДРАТОВА А.Н."».
QUOTES_AND_SPACE = '"«»\'“” '


def _boundary(literal: str) -> re.Pattern:
    """Регистронезависимый поиск литерала с границами по НЕ-словным символам.

    `\\b` здесь не годится: типовое имя контрагента в выписках РК —
    «Ержан О.» — заканчивается точкой, а `\\b` после точки требует буквы
    следом. На конце строки такого символа нет, совпадения не происходит,
    и имя физлица утекает наружу. Lookaround работает независимо от того,
    какой символ стоит по краям.
    """
    return re.compile(rf'(?<!\w){re.escape(literal)}(?!\w)', re.IGNORECASE)


@dataclass
class AnonymizationReport:
    """Сводка о проделанном маскировании — для аудита, без самих значений."""

    customer_masked: bool = False
    counterparties: int = 0
    iins: int = 0
    ibans: int = 0
    cards: int = 0
    phones: int = 0

    @property
    def total(self) -> int:
        return (
            int(self.customer_masked)
            + self.counterparties + self.iins + self.ibans + self.cards + self.phones
        )

    def to_dict(self) -> Dict[str, int | bool]:
        return {
            "customer_masked": self.customer_masked,
            "counterparties_masked": self.counterparties,
            "iins_masked": self.iins,
            "ibans_masked": self.ibans,
            "cards_masked": self.cards,
            "phones_masked": self.phones,
            "total_replacements": self.total,
        }


class Anonymizer:
    """Заменяет персональные данные на стабильные теги.

    Использование::

        anon = Anonymizer(owner_name=account.owner)
        safe_text = anon.text(tx.description)
        safe_name = anon.counterparty(tx.counterparty)
        report = anon.report()
    """

    CUSTOMER_TAG = "[CUSTOMER]"

    def __init__(self, owner_name: Optional[str] = None):
        self._owner_variants: List[str] = []
        self._counterparties: Dict[str, str] = {}
        self._iins: Dict[str, str] = {}
        self._ibans: Dict[str, str] = {}
        self._cards: Dict[str, str] = {}
        self._phones: Dict[str, str] = {}
        self._customer_hit = False

        if owner_name:
            self._owner_variants = self._name_variants(owner_name)

    # ── Владелец счёта ───────────────────────────────────────────

    @staticmethod
    def _name_variants(full_name: str) -> List[str]:
        """Варианты написания ФИО, которые встречаются в одной выписке.

        Один и тот же человек фигурирует как «Иванов Иван Иванович» в шапке
        и как «Иван И.» в строке перевода самому себе.
        """
        parts = [p for p in full_name.split() if len(p) > 1]
        variants = {full_name}
        if len(parts) >= 2:
            variants.update({
                f"{parts[0]} {parts[1]}",
                f"{parts[0]} {parts[1][0]}.",
                f"{parts[1]} {parts[0][0]}.",
            })
        if len(parts) >= 3:
            variants.add(f"{parts[0]} {parts[1]} {parts[2]}")
        variants.update(p for p in parts if len(p) >= 4)
        # Длинные варианты первыми: иначе короткий вариант съест часть длинного
        return sorted((v for v in variants if len(v) >= 4), key=len, reverse=True)

    # ── Публичный API ────────────────────────────────────────────

    def register(self, names: Iterable[Optional[str]]) -> None:
        """Заранее присвоить теги контрагентам-физлицам.

        Обязательный первый проход перед маскированием описаний. В выписках
        Kaspi поле «Детали» содержит то же имя, что и контрагент («Ержан О.»),
        поэтому маскировать эти поля независимо нельзя: имя, вычищенное из
        counterparty, осталось бы открытым в description.
        """
        for name in names:
            if name and self.is_person(name.strip()) and not self._is_owner(name.strip()):
                self.counterparty(name)

    def text(self, value: Optional[str]) -> str:
        """Замаскировать произвольный текст (описание операции, назначение)."""
        if not value:
            return ""
        result = str(value)

        for variant in self._owner_variants:
            result, n = _boundary(variant).subn(self.CUSTOMER_TAG, result)
            if n:
                self._customer_hit = True

        # Имена контрагентов, зарегистрированные на первом проходе. Длинные
        # первыми, иначе «Ержан» подменится раньше, чем «Ержан О.».
        for original, tag in sorted(
            self._counterparties.items(), key=lambda kv: len(kv[0]), reverse=True
        ):
            result = _boundary(original).sub(tag, result)

        result = self._replace(result, IBAN_PATTERN, self._ibans, "IBAN")
        result = self._replace(result, CARD_PATTERN, self._cards, "CARD")
        result = self._replace(result, PHONE_PATTERN, self._phones, "PHONE")
        # ИИН последним: остальные паттерны длиннее и не должны быть
        # разорваны заменой вложенной 12-значной последовательности.
        result = self._replace(result, IIN_PATTERN, self._iins, "IIN")

        # Финальная сеть: ФИО, оставшееся внутри более длинной строки —
        # прежде всего названия ИП вида «ИП "КОНДРАТОВА А.Н."». Тег берётся
        # из общего словаря, поэтому один человек всегда получает один номер,
        # как бы он ни был записан.
        result = self._mask_person_names(result)
        return result

    def _mask_person_names(self, text: str) -> str:
        def _sub(match: re.Match) -> str:
            key = re.sub(r'\s+', ' ', match.group(0)).strip().upper()
            if key not in self._counterparties:
                self._counterparties[key] = f"[PERSON_{len(self._counterparties) + 1}]"
            return self._counterparties[key]

        return PERSON_IN_TEXT_PATTERN.sub(_sub, text)

    def counterparty(self, name: Optional[str]) -> str:
        """Замаскировать контрагента, если это физическое лицо.

        Организации возвращаются как есть — они не персональные данные и
        нужны модели для оценки риска мерчанта.
        """
        if not name or not name.strip():
            return ""
        raw = name.strip()

        if self._is_owner(raw):
            self._customer_hit = True
            return self.CUSTOMER_TAG

        # ИП проверяется до is_person(): формально это название бизнеса, и
        # is_organization() относит его к организациям, из-за чего ФИО
        # предпринимателя уходило наружу открытым текстом.
        sole_trader = self._mask_sole_trader(raw)
        if sole_trader is not None:
            return sole_trader

        if not self.is_person(raw):
            # Организация: имя сохраняем, но чистим вкрапления ПД
            return self.text(raw)

        return self._tag_for(raw)

    def _tag_for(self, name: str) -> str:
        """Стабильная метка для одного человека: одно имя — один номер."""
        key = name.strip().upper()
        if key not in self._counterparties:
            self._counterparties[key] = f"[PERSON_{len(self._counterparties) + 1}]"
        return self._counterparties[key]

    def _mask_sole_trader(self, name: str) -> Optional[str]:
        """«ИП КАРИМБЕКОВ» → «ИП [PERSON_1]». Не ИП — вернуть None.

        Правовая форма сохраняется намеренно: она не идентифицирует человека,
        а для оценки риска отличать ИП от ТОО полезно.
        """
        match = SOLE_TRADER_PREFIX.match(name)
        if not match:
            return None

        form, remainder = match.group(1).upper(), match.group(2).strip()
        if not SOLE_TRADER_NAME.match(remainder):
            # Латинское название — торговая марка, а не ФИО.
            return None

        form = {"И.П.": "ИП", "IP": "ИП"}.get(form, form)
        bare_name = remainder.strip(QUOTES_AND_SPACE)
        return f"{form} {self._tag_for(bare_name)}"

    @staticmethod
    def is_person(name: str) -> bool:
        """Физическое лицо или организация.

        Переиспользует is_organization() из utils.helpers — единый источник
        правды о юрлицах в проекте (ТОО/АО/ИП/LLC + известные бренды).
        """
        cleaned = name.strip()
        if not cleaned:
            return False
        if PERSON_INITIAL_PATTERN.match(cleaned):
            return True
        return not is_organization(cleaned)

    def _is_owner(self, name: str) -> bool:
        upper = name.upper()
        return any(v.upper() == upper for v in self._owner_variants)

    def report(self) -> AnonymizationReport:
        return AnonymizationReport(
            customer_masked=self._customer_hit,
            counterparties=len(self._counterparties),
            iins=len(self._iins),
            ibans=len(self._ibans),
            cards=len(self._cards),
            phones=len(self._phones),
        )

    def leaks(self, payload: str) -> List[str]:
        """Проверить, что в готовом тексте не осталось прямых идентификаторов.

        Возвращает список найденных нарушений — пустой список означает, что
        текст безопасно отправлять во внешнюю модель. Используется в тестах
        как исполняемая гарантия приватности.
        """
        found: List[str] = []
        for label, pattern in (
            ("IIN", IIN_PATTERN), ("IBAN", IBAN_PATTERN),
            ("CARD", CARD_PATTERN), ("PHONE", PHONE_PATTERN),
        ):
            if pattern.search(payload):
                found.append(label)
        for variant in self._owner_variants:
            if re.search(rf'\b{re.escape(variant)}\b', payload, re.IGNORECASE):
                found.append("OWNER_NAME")
                break
        # Остаточные имена физлиц в форме «Ержан О.» — типовой контрагент в
        # выписках РК. Ловим их отдельно: они не подпадают ни под один из
        # числовых паттернов выше, а именно так ПД третьих лиц и утекают.
        residual = re.findall(rf'\b[{_CYR}][{_CYR}]+\s+[{_CYR}]\.', payload)
        if residual:
            found.append(f"PERSON_NAME x{len(set(residual))}")
        return found

    # ── Внутреннее ───────────────────────────────────────────────

    @staticmethod
    def _replace(text: str, pattern: re.Pattern, store: Dict[str, str], tag: str) -> str:
        """Заменить все вхождения паттерна стабильными тегами."""

        def _sub(match: re.Match) -> str:
            original = match.group(0)
            key = re.sub(r'[\s*-]', '', original).upper()
            if key not in store:
                store[key] = f"[{tag}_{len(store) + 1}]"
            return store[key]

        return pattern.sub(_sub, text)


def anonymize_transactions(transactions: Iterable, owner_name: Optional[str] = None):
    """Вернуть (список обезличенных словарей, отчёт).

    Работает с Transaction из bank_analyzer.base_parser. Наружу отдаются
    только те поля, которые нужны модели для рассуждения.
    """
    transactions = list(transactions)
    anon = Anonymizer(owner_name)
    # Первый проход: раздать теги всем контрагентам-физлицам, чтобы второй
    # проход мог вычистить их имена и из описаний тоже.
    anon.register(getattr(tx, "counterparty", "") for tx in transactions)

    safe = []
    for tx in transactions:
        safe.append({
            "date": tx.date.isoformat() if getattr(tx, "date", None) else None,
            "amount": getattr(tx, "amount", 0),
            "currency": getattr(tx, "currency", "KZT"),
            "type": tx.type.value if getattr(tx, "type", None) else None,
            "category": getattr(tx, "category", "") or "",
            "description": anon.text(getattr(tx, "description", "")),
            "counterparty": anon.counterparty(getattr(tx, "counterparty", "")),
        })
    return safe, anon.report()
