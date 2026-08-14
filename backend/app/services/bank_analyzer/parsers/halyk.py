"""
Парсер выписок Halyk Bank (Народный Банк Казахстана)
Поддерживает: Справка о наличии счета с выпиской операций
Формат: 9-колоночная таблица (дата, дата обработки, описание, сумма, валюта, приход, расход, комиссия, номер карты/счёта)
"""
import re
import pdfplumber
from datetime import datetime
from typing import List, Optional, Dict
import logging

from ..base_parser import BaseParser, Transaction, TransactionType, CounterpartyType, AccountInfo, ExpectedTotals

logger = logging.getLogger(__name__)


# ── Многоязычные метки (ru / kk / en) ─────────────────────────────
# «Справка о наличии счета» выдаётся Halyk на трёх языках с одинаковой
# структурой таблиц. Раньше распознавание шло по русским литералам, поэтому
# казахская и английская справки давали 0 транзакций при parse() == True.

# Заголовки транзакционной таблицы (сравниваются со снятыми пробелами)
TX_TABLE_MARKERS = (
    "датапроведенияоперации", "описаниеоперации",           # ru
    "операцияжүргізілгенкүн", "операцияныңсипаттамасы",      # kk
    "dateoftransaction", "transactiondescription",           # en
)

# Первая ячейка итоговой строки
TOTALS_MARKERS = ("всего", "барлығы", "total")

# Метки на титульной странице
RE_CLIENT = re.compile(r'(?:Клиент|Client)\s+(.+)')
RE_IIN = re.compile(r'(?:ИИН|ЖСН|IIN)\s+(\d{12})')
RE_CERT_NO = re.compile(r'(?:Справка|Анықтама|Certificate)\s*№\s*(\d+)')

# Заголовок таблицы счетов
ACCOUNTS_TABLE_MARKERS = ("номер счета", "шот нөмірі", "account number")
TOTAL_KZT_MARKERS = ("общая сумма в kzt", "жалпы сомасы kzt", "total amount kzt")

# Входящий / исходящий остаток. В PDF метка и значение слипаются без пробелов
# («Входящийостаток:62,15KZT;»), поэтому сравниваем по тексту со снятыми
# пробелами и собираем regex сразу по всем языковым вариантам.
OPENING_BALANCE_LABELS = ("Входящийостаток", "Кірісқалдығы", "Openingbalance")
CLOSING_BALANCE_LABELS = ("Исходящийостаток", "Шығысқалдығы", "Closingbalance")

RE_OPENING_BALANCE = re.compile(
    r'(?:' + "|".join(OPENING_BALANCE_LABELS) + r')\s*:\s*(-?[\d\s]+[.,]\d{2})\s*KZT',
    re.IGNORECASE,
)
RE_CLOSING_BALANCE = re.compile(
    r'(?:' + "|".join(CLOSING_BALANCE_LABELS) + r')\s*:\s*(-?[\d\s]+[.,]\d{2})\s*KZT',
    re.IGNORECASE,
)

# Kaspi/Halyk печатают казахскую шва латиницей: Ə (U+018F) / ə (U+0259).
_SCHWA_NORMALISE = str.maketrans({"Ə": "Ә", "ə": "ә"})


def _norm(text: str) -> str:
    """Нормализовать графику и регистр для сравнения меток."""
    return (text or "").translate(_SCHWA_NORMALISE).lower()


def _matches_any(text: str, needles: tuple) -> bool:
    low = _norm(text)
    return any(n in low for n in needles)


class HalykParser(BaseParser):
    """
    Парсер PDF выписок Halyk Bank
    Обрабатывает "Справка о наличии счета" с таблицами операций
    """

    # Halyk описания склеены без пробелов — нужна постобработка
    # Порядок важен: длинные фразы первыми
    DESCRIPTION_FIXES = {
        "Ежемесячнаякомиссияза": "Ежемесячная комиссия за ",
        "Переводмеждусвоимисчетами": "Перевод между своими счетами",
        "Переводсосчетанасчет": "Перевод со счета на счет",
        "Переводнадругуюкарту": "Перевод на другую карту",
        "Поступлениенасчет": "Поступление на счет ",
        "Поступлениеперевода": "Поступление перевода",
        "Зачислениезарплаты": "Зачисление зарплаты",
        "Зачислениепенсии": "Зачисление пенсии",
        "Зачислениепособия": "Зачисление пособия",
        "Снятиеналичных": "Снятие наличных",
        "Покупкатовара": "Покупка товара",
        "Оплатауслуг": "Оплата услуг",
        "Возвратсредств": "Возврат средств",
        "Финансовыйцентр": "Финансовый центр",
        "обслуживаниекарточки": "обслуживание карточки",
        "КАТИУимС": "КАТИУ им. С.",
    }

    # Маппинг типов операций
    TYPE_KEYWORDS = {
        TransactionType.INCOME: ["поступление", "зачисление", "возврат"],
        TransactionType.TRANSFER_OUT: ["перевод на другую", "перевод между"],
        TransactionType.TRANSFER_IN: ["поступление перевода"],
        TransactionType.WITHDRAWAL: ["снятие наличных"],
        TransactionType.EXPENSE: ["покупка", "оплата"],
        TransactionType.FEE: ["комиссия"],
    }

    # Паттерн для суммы: "47 135,00" или "-46 800,00"
    AMOUNT_PATTERN = re.compile(r'^[+-]?\s*[\d\s]+[.,]\d{2}$')

    def __init__(self, pdf_path: str):
        super().__init__(pdf_path)
        self.account.bank_name = "Halyk Bank"
        self.account.currency = "KZT"
        self._accounts_info: List[Dict] = []

    def parse(self) -> bool:
        """Основной метод парсинга"""
        try:
            logger.info(f"Парсинг Halyk PDF: {self.pdf_path}")

            with pdfplumber.open(self.pdf_path) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"PDF содержит {total_pages} страниц")

                # Страница 1 — информация о клиенте, счетах, балансах
                self._parse_header_page(pdf.pages[0])

                # Страница 2 (или 1) — текстовые данные выписки: входящий/исходящий остаток
                if len(pdf.pages) > 1:
                    self._parse_statement_header_text(pdf.pages[1])

                # Все страницы — таблицы операций
                for page_num, page in enumerate(pdf.pages):
                    self._parse_transactions_from_page(page, page_num)

            logger.info(f"Успешно спарсено {len(self.transactions)} транзакций Halyk")
            # Ноль транзакций — провал, а не успех (см. StatementParsingError).
            if not self.transactions:
                self.errors.append(
                    "Ни одной транзакции не извлечено: заголовки таблицы операций "
                    "не совпали с ожидаемыми (проверьте язык справки)"
                )
                return False
            return True

        except Exception as e:
            logger.error(f"Ошибка парсинга Halyk: {e}", exc_info=True)
            self.errors.append(str(e))
            return False

    def _parse_account_info(self) -> None:
        """Реализация абстрактного метода — вызывается через _parse_header_page"""
        pass

    def _parse_transactions(self) -> None:
        """Реализация абстрактного метода — вызывается через _parse_transactions_from_page"""
        pass

    def _parse_statement_header_text(self, page) -> None:
        """Извлечь входящий/исходящий остаток и период из текста выписки (стр. 2)"""
        text = page.extract_text() or ""

        # Метка и значение в PDF слипаются («Входящийостаток:62,15KZT»),
        # поэтому ищем по варианту текста без пробелов.
        compact = text.replace(" ", "")

        opening_match = RE_OPENING_BALANCE.search(compact) or RE_OPENING_BALANCE.search(text)
        if opening_match:
            bal = self._parse_amount(opening_match.group(1))
            if bal is not None:
                self.account.balance_start = bal
                logger.info(f"Halyk: входящий остаток = {bal}")

        closing_match = RE_CLOSING_BALANCE.search(compact) or RE_CLOSING_BALANCE.search(text)
        if closing_match:
            bal = self._parse_amount(closing_match.group(1))
            if bal is not None:
                self.account.balance_end = bal
                logger.info(f"Halyk: исходящий остаток = {bal}")

        # Период выписки: с 10.02.2025 по 10.02.2026
        period_match = re.search(r'с\s*(\d{2}\.\d{2}\.\d{4})\s*по\s*(\d{2}\.\d{2}\.\d{4})', text)
        if period_match:
            try:
                self.account.period_start = datetime.strptime(period_match.group(1), "%d.%m.%Y")
                self.account.period_end = datetime.strptime(period_match.group(2), "%d.%m.%Y")
            except ValueError:
                pass

    def _parse_header_page(self, page) -> None:
        """Извлечь информацию о клиенте и счетах с первой страницы"""
        text = page.extract_text() or ""

        # Клиент (ru/en; в казахской справке метка тоже "Клиент")
        client_match = RE_CLIENT.search(text)
        if client_match:
            self.account.owner = client_match.group(1).strip()

        # ИИН / ЖСН / IIN — прямой идентификатор, обязателен к маскированию
        # перед любой отправкой во внешнюю модель (см. anonymizer).
        iin_match = RE_IIN.search(text)
        if iin_match:
            self.account.extra["iin"] = iin_match.group(1)

        # Дата справки
        date_match = re.search(r'Дата\s+(\d{2}\.\d{2}\.\d{4})', text)
        if date_match:
            try:
                self.account.period_end = datetime.strptime(date_match.group(1), "%d.%m.%Y")
            except ValueError:
                pass

        # Номер справки
        ref_match = RE_CERT_NO.search(text)
        if ref_match:
            self.account.extra["reference_number"] = ref_match.group(1)

        # Таблицы первой страницы
        tables = page.extract_tables()

        for table in tables:
            if not table or len(table) < 2:
                continue

            header = [str(c or "").strip() for c in table[0]]
            header_text = _norm(" ".join(header))

            # Таблица общей суммы
            if any(m in header_text for m in TOTAL_KZT_MARKERS):
                row = table[1]
                if row:
                    total_str = str(row[0] or "").replace("₸", "").strip()
                    total = self._parse_amount(total_str)
                    if total is not None:
                        self.account.extra["total_kzt"] = total

            # Таблица счетов
            if any(m in header_text for m in ACCOUNTS_TABLE_MARKERS):
                for row in table[1:]:
                    if not row or not row[0]:
                        continue
                    acc_info = {
                        "account_number": str(row[0] or "").strip(),
                        "currency": str(row[1] or "").strip(),
                        "type": str(row[2] or "").strip(),
                        "balance": self._parse_amount(str(row[3] or "0")),
                    }
                    self._accounts_info.append(acc_info)

                    # Основной KZT счёт
                    if acc_info["currency"] == "KZT":
                        self.account.account_number = acc_info["account_number"]
                        self.account.balance_end = acc_info["balance"] or 0.0

        logger.info(f"Halyk: клиент={self.account.owner}, счетов={len(self._accounts_info)}")

    def _parse_transactions_from_page(self, page, page_num: int) -> None:
        """Извлечь транзакции из 9-колоночной таблицы"""
        tables = page.extract_tables()

        for table in tables:
            if not table or len(table) < 2:
                continue

            header = [str(c or "").strip().replace("\n", "") for c in table[0]]

            # Пропускаем не-транзакционные таблицы (счета, балансы)
            if not self._is_transaction_table(header):
                continue

            for row_idx, row in enumerate(table[1:], start=1):
                if not row or len(row) < 9:
                    continue

                # Пропускаем итоговую строку ("Всего" / "Барлығы" / "Total")
                first_cell = str(row[0] or "").strip()
                if _norm(first_cell).startswith(TOTALS_MARKERS):
                    self._parse_totals_row(row)
                    continue

                # Пропускаем пустые строки
                if not first_cell:
                    continue

                tx = self._parse_transaction_row(row, page_num, row_idx)
                if tx:
                    self.transactions.append(tx)

    def _is_transaction_table(self, header: List[str]) -> bool:
        """Проверить что таблица содержит транзакции (по заголовку, ru/kk/en)"""
        header_text = _norm(" ".join(header)).replace(" ", "")
        return any(marker in header_text for marker in TX_TABLE_MARKERS)

    def _parse_totals_row(self, row) -> None:
        """Извлечь итоги из строки 'Всего'"""
        try:
            credit = self._parse_amount(str(row[5] or "0"))
            debit = self._parse_amount(str(row[6] or "0"))
            commission = self._parse_amount(str(row[7] or "0"))

            if credit:
                self.expected_totals.deposits = credit
            if debit:
                self.expected_totals.withdrawals = abs(debit)
            if commission:
                self.account.extra["total_commission"] = commission

            logger.info(f"Halyk итоги: приход={credit}, расход={debit}, комиссия={commission}")
        except Exception as e:
            logger.debug(f"Не удалось распарсить итоги: {e}")

    def _parse_transaction_row(self, row, page_num: int, row_idx: int) -> Optional[Transaction]:
        """Распарсить одну строку транзакции"""
        try:
            # Колонки: 0=дата, 1=дата_обработки, 2=описание, 3=сумма, 4=валюта,
            #          5=приход, 6=расход, 7=комиссия, 8=номер_карты/счёта
            date_str = str(row[0] or "").strip()
            description_raw = str(row[2] or "").strip().replace("\n", " ")
            amount_str = str(row[3] or "0").strip()
            currency = str(row[4] or "KZT").strip()
            credit_str = str(row[5] or "0").strip()
            debit_str = str(row[6] or "0").strip()
            commission_str = str(row[7] or "0").strip()
            card_account = str(row[8] or "").strip()

            # Дата
            date = self._parse_date(date_str)
            if not date:
                return None

            # Описание — расклеить слова
            description = self._fix_description(description_raw)

            # Суммы
            credit = self._parse_amount(credit_str) or 0.0
            debit = self._parse_amount(debit_str) or 0.0
            commission = self._parse_amount(commission_str) or 0.0

            # Определить сумму и направление
            if commission != 0 and credit == 0 and debit == 0:
                # Чисто комиссия (например, ежемесячная за обслуживание)
                amount = commission
                tx_type = TransactionType.FEE
            elif credit > 0:
                amount = credit
                tx_type = self._determine_type(description, is_income=True)
            elif debit != 0:
                amount = debit  # debit уже отрицательный
                tx_type = self._determine_type(description, is_income=False)
            else:
                return None  # Нулевая транзакция

            # Определить период
            if not self.account.period_start or date < self.account.period_start:
                self.account.period_start = date
            if not self.account.period_end or date > self.account.period_end:
                self.account.period_end = date

            # Контрагент
            counterparty = self._extract_counterparty(description)
            cp_type = self._determine_counterparty_type(description)

            # Merchant type
            merchant_type = None
            for prefix in ["АО", "НАО", "ТОО", "ИП"]:
                if prefix in description:
                    merchant_type = prefix
                    break

            # Валюта (если не KZT)
            if not currency or currency == "":
                currency = "KZT"

            return Transaction(
                date=date,
                amount=round(amount, 2),
                type=tx_type,
                description=description,
                currency=currency,
                counterparty=counterparty,
                counterparty_type=cp_type,
                merchant_type=merchant_type,
                reference=card_account,
                is_salary="зарплат" in description.lower(),
                is_pension_benefit="пенси" in description.lower() or "пособи" in description.lower(),
                is_bank_transfer="другую карту" in description.lower() or "другой банк" in description.lower(),
                source_page=page_num,
                source_row=row_idx,
                raw_data={
                    "credit": credit,
                    "debit": debit,
                    "commission": commission,
                    "card_account": card_account,
                }
            )

        except Exception as e:
            logger.debug(f"Halyk: ошибка парсинга строки {row_idx} стр.{page_num}: {e}")
            return None

    def _fix_description(self, raw: str) -> str:
        """Исправить склеенные слова в описании Halyk PDF"""
        result = raw
        for bad, good in self.DESCRIPTION_FIXES.items():
            if bad in result:
                result = result.replace(bad, good)

        # Дополнительно: вставить пробел перед заглавными буквами в середине слова
        # Например: "ФинансовыйцентрАО" -> оставляем как есть (уже обработано выше)
        # "RegularCharge" -> "Regular Charge"
        result = re.sub(r'([a-z])([A-Z])', r'\1 \2', result)

        return result.strip()

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Парсинг даты в формате DD.MM.YYYY"""
        for fmt in ["%d.%m.%Y", "%d.%m.%y"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Парсинг суммы Halyk: '47 135,00' или '-662 100,00'"""
        if not amount_str:
            return None
        try:
            cleaned = amount_str.replace("₸", "").replace("$", "").replace("€", "").strip()
            cleaned = cleaned.replace("\xa0", "").replace(" ", "")
            cleaned = cleaned.replace(",", ".")
            if not cleaned or cleaned == "0.00" or cleaned == "0":
                return 0.0
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _determine_type(self, description: str, is_income: bool) -> TransactionType:
        """Определить тип транзакции по описанию"""
        desc_lower = description.lower()

        for tx_type, keywords in self.TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in desc_lower:
                    return tx_type

        # Fallback по направлению
        return TransactionType.INCOME if is_income else TransactionType.EXPENSE

    def _extract_counterparty(self, description: str) -> Optional[str]:
        """Извлечь контрагента из описания"""
        desc = description

        # "Поступление на счет АО Финансовый центр" -> "АО Финансовый центр"
        for prefix in ["Поступление на счет ", "Перевод на счет ", "Оплата услуг "]:
            if desc.startswith(prefix):
                return desc[len(prefix):].strip()

        # "Перевод на другую карту" -> карточный перевод, нет конкретного контрагента
        if "на другую карту" in desc:
            return "Карточный перевод"

        if "комиссия" in desc.lower():
            return "Halyk Bank"

        return desc

    def _determine_counterparty_type(self, description: str) -> CounterpartyType:
        """Определить тип контрагента"""
        desc = description.lower()

        if any(kw in desc for kw in ["ао ", "нао ", "тоо ", "ип "]):
            return CounterpartyType.MERCHANT
        if "банк" in desc or "комисси" in desc:
            return CounterpartyType.BANK
        if "банкомат" in desc or "наличн" in desc:
            return CounterpartyType.ATM
        if "пенси" in desc or "пособи" in desc:
            return CounterpartyType.GOVERNMENT
        if "перевод" in desc:
            return CounterpartyType.PERSON

        return CounterpartyType.UNKNOWN
