"""
Универсальный адаптивный парсер для неизвестных банков
Использует эвристики для определения структуры выписки
"""
import re
import pdfplumber
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

from ..base_parser import BaseParser, Transaction, TransactionType, AccountInfo

logger = logging.getLogger(__name__)


class GenericParser(BaseParser):
    """
    Умный адаптивный парсер для любых банковских выписок
    Автоматически определяет:
    - Формат даты
    - Структуру таблиц
    - Типы транзакций
    - Валюту
    """

    # Паттерны дат
    DATE_PATTERNS = [
        (r'\d{2}\.\d{2}\.\d{4}', '%d.%m.%Y'),
        (r'\d{2}\.\d{2}\.\d{2}', '%d.%m.%y'),
        (r'\d{4}-\d{2}-\d{2}', '%Y-%m-%d'),
        (r'\d{2}/\d{2}/\d{4}', '%d/%m/%Y'),
        (r'\d{2}/\d{2}/\d{2}', '%d/%m/%y'),
    ]

    # Ключевые слова для определения типа транзакции
    INCOME_KEYWORDS = [
        'пополнение', 'зачисление', 'поступление', 'входящий', 'возврат',
        'deposit', 'credit', 'incoming', 'salary', 'зарплата', 'пенсия',
        'cashback', 'кэшбэк', 'начисление'
    ]

    EXPENSE_KEYWORDS = [
        'покупка', 'списание', 'оплата', 'платёж', 'платеж', 'расход',
        'purchase', 'payment', 'debit', 'withdrawal', 'снятие', 'комиссия'
    ]

    TRANSFER_KEYWORDS = [
        'перевод', 'transfer', 'p2p', 'отправка', 'получение'
    ]

    # Валюты
    CURRENCY_SYMBOLS = {
        '₸': 'KZT', '₽': 'RUB', '$': 'USD', '€': 'EUR',
        '¥': 'CNY', '£': 'GBP', '₿': 'BTC', 'USDT': 'USDT'
    }

    def __init__(self, pdf_path: str):
        super().__init__(pdf_path)
        self.account.bank_name = "Неизвестный банк"
        self.detected_date_format = None
        self.detected_currency = "KZT"

    def _is_excel(self) -> bool:
        """Проверить, является ли файл Excel"""
        return self.pdf_path.lower().endswith(('.xlsx', '.xls'))

    def parse(self) -> bool:
        """Адаптивный парсинг с автоопределением структуры (PDF или Excel)"""
        if self._is_excel():
            return self._parse_excel()
        return self._parse_pdf()

    def _parse_pdf(self) -> bool:
        """Адаптивный парсинг PDF"""
        try:
            logger.info(f"Адаптивный парсинг PDF: {self.pdf_path}")

            with pdfplumber.open(self.pdf_path) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"PDF содержит {total_pages} страниц")

                # Анализ первой страницы для определения структуры
                first_page_text = pdf.pages[0].extract_text() or ""
                self._detect_structure(first_page_text, pdf.pages[0])

                # Парсинг всех страниц
                for page_num, page in enumerate(pdf.pages):
                    self._parse_page_adaptive(page, page_num)

            # Автоопределение информации о счете из транзакций
            self._infer_account_info()

            logger.info(f"Адаптивно спарсено {len(self.transactions)} транзакций")
            return len(self.transactions) > 0

        except Exception as e:
            logger.error(f"Ошибка адаптивного парсинга: {e}", exc_info=True)
            self.errors.append(f"Ошибка парсинга: {str(e)}")
            return False

    def _parse_excel(self) -> bool:
        """Адаптивный парсинг Excel файла"""
        try:
            import openpyxl
            logger.info(f"Адаптивный парсинг Excel: {self.pdf_path}")

            wb = openpyxl.load_workbook(self.pdf_path, read_only=True, data_only=True)
            sheet = wb.worksheets[0]

            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                return False

            # Ищем строку-заголовок таблицы
            header_idx = None
            for i, row in enumerate(rows):
                row_text = ' '.join(str(c or '').lower() for c in row)
                if any(w in row_text for w in ['дата', 'date']) and any(w in row_text for w in ['сумма', 'amount', 'операция', 'type']):
                    header_idx = i
                    break

            if header_idx is not None:
                column_mapping = self._detect_columns([str(c or '') for c in rows[header_idx]])
                data_start = header_idx + 1
            else:
                # Определяем по первой строке данных
                column_mapping = {}
                data_start = 0
                for i, row in enumerate(rows):
                    first_cell = str(row[0] or '').strip() if row and row[0] else ''
                    for pattern, _ in self.DATE_PATTERNS:
                        if re.match(pattern, first_cell):
                            data_start = i
                            column_mapping = self._detect_columns_by_data([str(c or '') for c in row])
                            break
                    if column_mapping:
                        break

            # Определение структуры из первых строк (для валюты и т.д.)
            preview_text = '\n'.join(' '.join(str(c or '') for c in row) for row in rows[:10])
            self._detect_structure_from_text(preview_text)

            # Парсинг строк
            for row in rows[data_start:]:
                if not row or not any(row):
                    continue
                row_list = [str(c or '').strip() for c in row]
                tx = self._parse_row_adaptive(row_list, column_mapping)
                if tx:
                    self.transactions.append(tx)

            wb.close()
            self._infer_account_info()

            logger.info(f"Адаптивно спарсено {len(self.transactions)} транзакций из Excel")
            return len(self.transactions) > 0

        except Exception as e:
            logger.error(f"Ошибка адаптивного парсинга Excel: {e}", exc_info=True)
            self.errors.append(f"Ошибка парсинга Excel: {str(e)}")
            return False

    def _detect_structure_from_text(self, text: str) -> None:
        """Определение валюты и формата даты из текста"""
        for symbol, currency in self.CURRENCY_SYMBOLS.items():
            if symbol in text:
                self.detected_currency = currency
                self.account.currency = currency
                break
        for pattern, date_format in self.DATE_PATTERNS:
            if re.search(pattern, text):
                self.detected_date_format = date_format
                break

    def _parse_account_info(self) -> None:
        """Будет вызвано из _detect_structure"""
        pass

    def _parse_transactions(self) -> None:
        """Будет вызвано из parse()"""
        pass

    def _detect_structure(self, text: str, page) -> None:
        """Автоопределение структуры выписки"""
        text_lower = text.lower()

        # Определение формата даты
        for pattern, date_format in self.DATE_PATTERNS:
            if re.search(pattern, text):
                self.detected_date_format = date_format
                logger.info(f"Определён формат даты: {date_format}")
                break

        # Определение валюты
        for symbol, currency in self.CURRENCY_SYMBOLS.items():
            if symbol in text:
                self.detected_currency = currency
                self.account.currency = currency
                logger.info(f"Определена валюта: {currency}")
                break

        # Попытка извлечь имя владельца
        # Ищем паттерны типа "ФИО: Иванов Иван Иванович"
        name_patterns = [
            r'(?:клиент|владелец|фио|ф\.и\.о|имя)[:\s]+([А-ЯЁа-яёӘәҒғҚқҢңӨөҰұҮүІіҺһəƏ\s]+)',
            r'(?:customer|name|holder)[:\s]+([A-Za-z\s]+)',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                self.account.owner = match.group(1).strip()
                break

        # Попытка извлечь номер счета/карты
        account_patterns = [
            r'(KZ\d{2}\d{3}[A-Z0-9]{13})',  # IBAN Казахстан
            r'(\d{20})',  # Номер счета 20 цифр
            r'\*{4}(\d{4})',  # Маскированная карта ****1234
            r'(\d{4}\s?\*{4}\s?\*{4}\s?\d{4})',  # 1234 **** **** 5678
        ]
        for pattern in account_patterns:
            match = re.search(pattern, text)
            if match:
                self.account.account_number = match.group(1)
                break

        # Извлечь период
        period_patterns = [
            r'(?:период|period)[:\s]+(\d{2}[./]\d{2}[./]\d{2,4})\s*[-–]\s*(\d{2}[./]\d{2}[./]\d{2,4})',
            r'с\s+(\d{2}[./]\d{2}[./]\d{2,4})\s+по\s+(\d{2}[./]\d{2}[./]\d{2,4})',
        ]
        for pattern in period_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                self.account.period_start = self._parse_date_adaptive(match.group(1))
                self.account.period_end = self._parse_date_adaptive(match.group(2))
                break

    def _parse_page_adaptive(self, page, page_num: int) -> None:
        """Адаптивный парсинг страницы"""
        # Сначала пробуем таблицы
        tables = page.extract_tables()
        for table in tables:
            if table and len(table) > 1:
                self._parse_table_adaptive(table)

        # Если таблиц мало, пробуем текстовый парсинг
        if len(self.transactions) < 5:
            text = page.extract_text() or ""
            self._parse_text_adaptive(text)

    def _parse_table_adaptive(self, table: List[List]) -> None:
        """Адаптивный парсинг таблицы"""
        if not table or len(table) < 2:
            return

        # Определяем какая колонка что содержит
        header_row = table[0]
        column_mapping = self._detect_columns(header_row)

        if not column_mapping.get('date') and not column_mapping.get('amount'):
            # Попробуем определить по первой строке данных
            column_mapping = self._detect_columns_by_data(table[1] if len(table) > 1 else None)

        if not column_mapping:
            return

        # Парсим строки
        for row in table[1:]:
            tx = self._parse_row_adaptive(row, column_mapping)
            if tx:
                self.transactions.append(tx)

    def _detect_columns(self, header_row: List) -> Dict[str, int]:
        """Определить соответствие колонок по заголовку"""
        mapping = {}
        if not header_row:
            return mapping

        for i, cell in enumerate(header_row):
            cell_lower = str(cell or '').lower()

            if any(w in cell_lower for w in ['дата', 'date', 'время']):
                mapping['date'] = i
            elif any(w in cell_lower for w in ['сумма', 'amount', 'sum']):
                mapping['amount'] = i
            elif any(w in cell_lower for w in ['описание', 'детали', 'description', 'details', 'назначение']):
                mapping['description'] = i
            elif any(w in cell_lower for w in ['тип', 'type', 'операция', 'категория']):
                mapping['type'] = i
            elif any(w in cell_lower for w in ['баланс', 'balance', 'остаток']):
                mapping['balance'] = i

        return mapping

    def _detect_columns_by_data(self, data_row: List) -> Dict[str, int]:
        """Определить колонки по содержимому первой строки данных"""
        mapping = {}
        if not data_row:
            return mapping

        for i, cell in enumerate(data_row):
            cell_str = str(cell or '').strip()

            # Ищем дату
            for pattern, _ in self.DATE_PATTERNS:
                if re.match(pattern, cell_str):
                    mapping['date'] = i
                    break

            # Ищем сумму
            if re.search(r'[+-]?\s*[\d\s]+[,.]?\d*\s*[₸₽$€¥£]?', cell_str):
                if 'amount' not in mapping:
                    mapping['amount'] = i

        return mapping

    def _parse_row_adaptive(self, row: List, column_mapping: Dict[str, int]) -> Optional[Transaction]:
        """Адаптивный парсинг строки"""
        try:
            # Извлечь дату
            date_idx = column_mapping.get('date', 0)
            date_str = str(row[date_idx] if date_idx < len(row) else '').strip()
            date = self._parse_date_adaptive(date_str)
            if not date:
                return None

            # Извлечь сумму
            amount_idx = column_mapping.get('amount', 1)
            amount_str = str(row[amount_idx] if amount_idx < len(row) else '').strip()
            amount = self._parse_amount_adaptive(amount_str)
            if amount == 0:
                return None

            # Извлечь описание
            desc_idx = column_mapping.get('description', -1)
            if desc_idx >= 0 and desc_idx < len(row):
                description = str(row[desc_idx] or '').strip()
            else:
                # Собрать всё кроме даты и суммы
                description = ' '.join(
                    str(cell or '').strip() for i, cell in enumerate(row)
                    if i not in [date_idx, amount_idx] and cell
                )

            # Определить тип транзакции
            tx_type = self._detect_transaction_type(description, amount)

            return Transaction(
                date=date,
                amount=amount,
                type=tx_type,
                description=description,
                currency=self.detected_currency,
                raw_data={"row": row}
            )

        except Exception as e:
            logger.debug(f"Ошибка парсинга строки: {e}")
            return None

    def _parse_text_adaptive(self, text: str) -> None:
        """Парсинг транзакций из текста (fallback)"""
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Ищем строки с датой и суммой
            date = None
            for pattern, _ in self.DATE_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    date = self._parse_date_adaptive(match.group())
                    break

            if not date:
                continue

            # Ищем сумму
            amount_match = re.search(r'([+-]?\s*[\d\s]+[,.]?\d*)\s*[₸₽$€¥£]?', line)
            if amount_match:
                amount = self._parse_amount_adaptive(amount_match.group())
                if amount != 0:
                    tx_type = self._detect_transaction_type(line, amount)
                    self.transactions.append(Transaction(
                        date=date,
                        amount=amount,
                        type=tx_type,
                        description=line,
                        currency=self.detected_currency
                    ))

    def _parse_date_adaptive(self, date_str: str) -> Optional[datetime]:
        """Адаптивный парсинг даты"""
        date_str = date_str.strip()
        if not date_str:
            return None

        # Нормализуем разделители
        date_str = date_str.replace('/', '.')

        for pattern, date_format in self.DATE_PATTERNS:
            match = re.match(pattern, date_str)
            if match:
                try:
                    return datetime.strptime(match.group(), date_format)
                except ValueError:
                    continue

        return None

    def _parse_amount_adaptive(self, amount_str: str) -> float:
        """Адаптивный парсинг суммы"""
        if not amount_str:
            return 0.0

        # Определяем знак
        is_negative = '-' in amount_str or 'списан' in amount_str.lower() or 'расход' in amount_str.lower()

        # Убираем всё кроме цифр и разделителей
        cleaned = re.sub(r'[^\d,.]', '', amount_str.replace('\xa0', '').replace(' ', ''))

        # Определяем десятичный разделитель
        if ',' in cleaned and '.' in cleaned:
            # Оба присутствуют - запятая как разделитель тысяч
            cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            # Только запятая - как десятичный разделитель
            cleaned = cleaned.replace(',', '.')

        try:
            amount = float(cleaned)
            return -abs(amount) if is_negative else abs(amount)
        except ValueError:
            return 0.0

    def _detect_transaction_type(self, text: str, amount: float) -> TransactionType:
        """Определить тип транзакции по тексту и сумме"""
        text_lower = text.lower()

        if any(kw in text_lower for kw in self.TRANSFER_KEYWORDS):
            return TransactionType.TRANSFER_IN if amount > 0 else TransactionType.TRANSFER_OUT

        if any(kw in text_lower for kw in self.INCOME_KEYWORDS):
            return TransactionType.INCOME

        if any(kw in text_lower for kw in self.EXPENSE_KEYWORDS):
            return TransactionType.EXPENSE

        # По знаку суммы
        return TransactionType.INCOME if amount > 0 else TransactionType.EXPENSE

    def _infer_account_info(self) -> None:
        """Вывести информацию о счете из спарсенных данных"""
        if self.transactions:
            # Период
            dates = [t.date for t in self.transactions if t.date]
            if dates:
                self.account.period_start = min(dates)
                self.account.period_end = max(dates)

            # Баланс (если есть)
            for t in self.transactions:
                if t.balance_after:
                    self.account.balance_end = t.balance_after
                    break
