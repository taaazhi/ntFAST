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
        #: Разметка колонок от модели, по заголовку таблицы. Одна на файл.
        self._llm_layout_cache: Dict[str, Dict[str, int]] = {}

    def _is_excel(self) -> bool:
        """Проверить, является ли файл Excel"""
        return self.pdf_path.lower().endswith(('.xlsx', '.xls'))

    def _is_csv(self) -> bool:
        return self.pdf_path.lower().endswith(('.csv', '.tsv'))

    def parse(self) -> bool:
        """Адаптивный парсинг с автоопределением структуры (PDF, Excel, CSV)"""
        if self._is_csv():
            return self._parse_csv()
        if self._is_excel():
            return self._parse_excel()
        return self._parse_pdf()

    def _parse_csv(self) -> bool:
        """Парсинг CSV/TSV с автоопределением разделителя и кодировки.

        CSV-выгрузки обычно самые структурированные из всех форматов: явные
        заголовки колонок и отдельные поля под реквизиты контрагента. Поэтому
        здесь, в отличие от PDF, можно забрать ИИН/БИН, счёт и банк.
        """
        import csv as csv_module

        try:
            logger.info(f"Адаптивный парсинг CSV: {self.pdf_path}")
            rows = self._read_csv_rows(csv_module)
            if not rows:
                self.errors.append("CSV файл пустой")
                return False

            header = [str(c or '').strip() for c in rows[0]]
            column_mapping = self._detect_columns(header)
            extra_mapping = self._detect_csv_extra_columns(header)

            if 'date' not in column_mapping or 'amount' not in column_mapping:
                self.errors.append(
                    f"Не найдены обязательные колонки (дата/сумма) в заголовке: {header}"
                )
                return False

            self._detect_structure_from_text("\n".join(" ".join(r) for r in rows[:5]))

            for row in rows[1:]:
                if not row or not any(str(c or '').strip() for c in row):
                    continue
                tx = self._parse_row_adaptive([str(c or '').strip() for c in row], column_mapping)
                if tx:
                    self._attach_csv_extras(tx, row, extra_mapping)
                    self.transactions.append(tx)

            self._infer_account_info()
            logger.info(f"Адаптивно спарсено {len(self.transactions)} транзакций из CSV")
            if not self.transactions:
                self.errors.append("Ни одной транзакции не извлечено из CSV")
                return False
            return True

        except Exception as e:
            logger.error(f"Ошибка парсинга CSV: {e}", exc_info=True)
            self.errors.append(f"Ошибка парсинга CSV: {str(e)}")
            return False

    def _read_csv_rows(self, csv_module) -> List[List[str]]:
        """Прочитать CSV, подобрав кодировку и разделитель.

        utf-8-sig снимает BOM, который Excel добавляет при экспорте; cp1251 —
        типичная кодировка выгрузок из русскоязычных банковских систем.
        """
        for encoding in ('utf-8-sig', 'cp1251'):
            try:
                with open(self.pdf_path, encoding=encoding, newline='') as fh:
                    sample = fh.read(4096)
                    fh.seek(0)
                    try:
                        dialect = csv_module.Sniffer().sniff(sample, delimiters=',;\t|')
                    except csv_module.Error:
                        dialect = csv_module.excel
                    return [row for row in csv_module.reader(fh, dialect)]
            except UnicodeDecodeError:
                continue
        raise ValueError("Не удалось определить кодировку CSV (пробовали utf-8 и cp1251)")

    # Дополнительные колонки, которых нет в PDF-выписках
    CSV_EXTRA_COLUMNS = {
        'counterparty': ('контрагент', 'counterparty', 'получатель', 'плательщик', 'payee', 'payer'),
        'counterparty_iin_bin': ('иин', 'бин', 'iin', 'bin', 'iin_bin', 'иин_бин'),
        'counterparty_account': ('счет', 'счёт', 'account', 'iban'),
        'counterparty_bank': ('банк', 'bank'),
        'payment_purpose': ('назначение', 'purpose', 'основание'),
    }

    def _detect_csv_extra_columns(self, header: List[str]) -> Dict[str, int]:
        mapping: Dict[str, int] = {}
        for idx, cell in enumerate(header):
            low = str(cell or '').strip().lower()
            if not low:
                continue
            for field, aliases in self.CSV_EXTRA_COLUMNS.items():
                if field not in mapping and any(a == low or a in low for a in aliases):
                    mapping[field] = idx
        return mapping

    @staticmethod
    def _attach_csv_extras(tx: Transaction, row: List, mapping: Dict[str, int]) -> None:
        for field, idx in mapping.items():
            if idx >= len(row):
                continue
            value = str(row[idx] or '').strip()
            if value:
                setattr(tx, field, value)
        # Описание в CSV часто пустое, а смысл несёт назначение платежа
        if not tx.description and tx.payment_purpose:
            tx.description = tx.payment_purpose

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
        """Адаптивный парсинг страницы: сначала таблицы, иначе текст.

        Решение принимается ПО КАЖДОЙ странице отдельно. Раньше условием было
        `len(self.transactions) < 5` — общий счётчик по всему документу, из-за
        чего текстовый разбор выключался навсегда, как только набиралось пять
        транзакций. На PDF без таблиц это означало разбор первой страницы и
        молчаливую потерю всех остальных.
        """
        before = len(self.transactions)

        for table in page.extract_tables() or []:
            if table and len(table) > 1:
                self._parse_table_adaptive(table)

        if len(self.transactions) == before:
            self._parse_text_adaptive(page.extract_text() or "")

    def _detect_columns_via_llm(self, table: List[List]) -> Optional[Dict[str, int]]:
        """Разметка колонок от языковой модели, если она доступна.

        Один вызов на файл: разметка одна на таблицу, поэтому стоимость не
        зависит от числа транзакций. Данные модель не читает — она смотрит
        заголовок и четыре строки, а извлекает значения по-прежнему код.

        Результат проверяется на самих данных: колонка, объявленная датой,
        обязана содержать даты. Не прошедшая проверку разметка отбрасывается.
        """
        try:
            from app.services.enrichment.pipeline import build_ai_manager
            from ..llm_layout import detect_layout
        except Exception:
            return None

        header = [str(c or "") for c in table[0]]

        # Разметка одна на файл. Выписка разбита на страницы, заголовок на
        # каждой повторяется, и без кэша модель опрашивалась бы заново для
        # каждой — вчетверо дольше и вчетверо больше шансов, что на одной
        # из страниц она ответит иначе. Ровно это и произошло на замере:
        # 148 строк из 200, потому что одну страницу разметило по-другому.
        cache_key = " | ".join(header)
        cached = self._llm_layout_cache.get(cache_key)
        if cached is not None:
            return cached or None

        ai_manager = build_ai_manager()
        if ai_manager is None:
            return None

        rows = [[str(c or "") for c in row] for row in table[1:6]]
        layout = detect_layout(header, rows, ai_manager)
        # Пустой результат тоже запоминаем: повторять неудачу на каждой
        # странице — только тратить время.
        self._llm_layout_cache[cache_key] = layout or {}
        return layout

    def _parse_table_adaptive(self, table: List[List]) -> None:
        """Адаптивный парсинг таблицы"""
        if not table or len(table) < 2:
            return

        # Определяем какая колонка что содержит
        header_row = table[0]
        column_mapping = self._detect_columns(header_row)

        # `is None`, а не truthiness: индекс колонки 0 — валидный, но ложный.
        # Дата почти всегда стоит первой, поэтому прежняя проверка считала её
        # ненайденной и перетирала разметку заголовков угадыванием по данным.
        has_date = column_mapping.get('date') is not None
        has_amount = (
            column_mapping.get('amount') is not None
            or 'amount_split' in column_mapping
        )
        if not has_date or not has_amount:
            # Словарь заголовков не справился — спрашиваем модель. Это тот
            # случай, ради которого она здесь: выписка банка, для которого
            # никто не писал ни парсера, ни алиасов. Без неё такой файл давал
            # 0 верных строк из 200 и 201 лишнюю, причём суммой становился
            # остаток по счёту — молча, с видом успешного разбора.
            llm_mapping = self._detect_columns_via_llm(table)
            if llm_mapping:
                column_mapping = llm_mapping
            else:
                # Модели нет или её разметка не подтвердилась данными —
                # прежний путь: догадка по первой строке.
                guessed = self._detect_columns_by_data(table[1] if len(table) > 1 else None)
                # Найденное по заголовкам точнее догадок: оно и побеждает.
                column_mapping = {**guessed, **column_mapping}

        if not column_mapping:
            return

        # Парсим строки
        for row in table[1:]:
            tx = self._parse_row_adaptive(row, column_mapping)
            if tx:
                self.transactions.append(tx)

    # Заголовки колонок на трёх языках. Порядок проверки важен: «остаток»
    # ищется раньше «суммы», иначе казахское «Шот қалдығы» (остаток по счёту)
    # перехватывается как сумма и в транзакции попадает баланс.
    COLUMN_ALIASES = (
        ("balance", ('баланс', 'остаток', 'қалдық', 'қалдығы', 'balance')),
        ("date", ('дата', 'күні', 'date', 'время', 'уақыт')),
        ("credit", ('приход', 'кіріс', 'credit', 'зачисление')),
        ("debit", ('расход', 'шығыс', 'debit', 'списание')),
        ("amount", ('сумма', 'сомасы', 'amount', 'sum')),
        ("counterparty", ('контрагент', 'қарсы агент', 'counterparty',
                          'получатель', 'плательщик', 'payee', 'payer')),
        ("description", ('описание', 'детали', 'сипаттама', 'description',
                         'details', 'назначение', 'толығырақ')),
        ("type", ('вид операции', 'операция түрі', 'тип', 'type',
                  'операция', 'категория')),
    )

    def _detect_columns(self, header_row: List) -> Dict[str, int]:
        """Определить соответствие колонок по заголовку (ru/kk/en).

        Раньше сравнение шло только с русскими и английскими словами, и
        выписка любого банка на казахском проваливалась в текстовый fallback,
        который склеивал колонки и брал сумму откуда придётся.
        """
        mapping: Dict[str, int] = {}
        if not header_row:
            return mapping

        for i, cell in enumerate(header_row):
            cell_lower = str(cell or '').lower()
            if not cell_lower.strip():
                continue
            for field, aliases in self.COLUMN_ALIASES:
                if field in mapping:
                    continue
                if any(w in cell_lower for w in aliases):
                    mapping[field] = i
                    break

        # Раскладка «Приход | Расход» вместо одной колонки суммы. Знак задаётся
        # тем, в какой из колонок стоит число, поэтому отдельной «суммы» нет.
        if 'amount' not in mapping and 'credit' in mapping and 'debit' in mapping:
            mapping['amount_split'] = 1

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

            def cell(idx: Optional[int]) -> str:
                if idx is None or idx < 0 or idx >= len(row):
                    return ''
                return str(row[idx] or '').strip()

            # Извлечь сумму. Раскладка «Приход | Расход» задаёт знак тем,
            # в какой колонке стоит число, — отдельной колонки суммы там нет.
            used = {date_idx}
            if 'amount_split' in column_mapping:
                credit_idx = column_mapping.get('credit')
                debit_idx = column_mapping.get('debit')
                credit = self._parse_amount_adaptive(cell(credit_idx))
                debit = self._parse_amount_adaptive(cell(debit_idx))
                amount = credit if credit else -abs(debit)
                used.update({i for i in (credit_idx, debit_idx) if i is not None})
            else:
                amount_idx = column_mapping.get('amount', 1)
                amount = self._parse_amount_adaptive(cell(amount_idx))
                used.add(amount_idx)

            if amount == 0:
                return None

            # Контрагент: в размеченной таблице он в своей колонке. Именно на
            # него опираются граф, merchant risk и structuring — без него
            # строка для детекторов почти бесполезна.
            counterparty_idx = column_mapping.get('counterparty')
            counterparty = cell(counterparty_idx) or None
            if counterparty_idx is not None:
                used.add(counterparty_idx)
            if counterparty in {'—', '-', ''}:
                counterparty = None

            operation = cell(column_mapping.get('type')) or ''

            # Извлечь описание
            desc_idx = column_mapping.get('description')
            if desc_idx is not None and 0 <= desc_idx < len(row):
                description = cell(desc_idx)
            else:
                # Собрать всё, кроме уже разобранных колонок и остатка
                balance_idx = column_mapping.get('balance')
                skip = used | ({balance_idx} if balance_idx is not None else set())
                description = ' '.join(
                    str(c or '').strip() for i, c in enumerate(row)
                    if i not in skip and c
                )
            if not description:
                description = ' '.join(x for x in (operation, counterparty or '') if x)

            # Определить тип транзакции
            tx_type = self._detect_transaction_type(
                ' '.join(x for x in (operation, description) if x), amount
            )

            return Transaction(
                date=date,
                amount=amount,
                type=tx_type,
                description=description,
                counterparty=counterparty,
                currency=self.detected_currency,
                raw_data={"row": row}
            )

        except Exception as e:
            logger.debug(f"Ошибка парсинга строки: {e}")
            return None

    # Денежная сумма: обязательно два знака после разделителя копеек.
    # Целые числа не берём — под них подпадают номера документов, счётчики
    # страниц и куски дат.
    MONEY_PATTERN = re.compile(r'[+-]?\d[\d   ]*[.,]\d{2}(?!\d)')

    def _parse_text_adaptive(self, text: str) -> None:
        """Парсинг транзакций из текста (fallback, когда таблиц в PDF нет).

        Сумму ищем СТРОГО ПОСЛЕ даты и только в денежном формате. Прежняя
        версия сканировала строку целиком регулярным выражением, которое
        допускало числа без копеек, и первым совпадением оказывалась сама
        дата: строка «06.01.2025 Yandex Go poezdka -26 341,94» давала сумму
        6.01 вместо -26 341,94. Транзакции при этом создавались — с верной
        датой и выдуманной суммой. Выписка с оборотом в миллионы выглядела
        как выписка на пару сотен тенге, и антифрод честно ставил LOW.
        """
        for raw_line in text.split('\n'):
            line = raw_line.strip()
            if not line:
                continue

            date = None
            date_end = 0
            for pattern, _ in self.DATE_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    date = self._parse_date_adaptive(match.group())
                    date_end = match.end()
                    break

            if not date:
                continue

            # Хвост строки после даты — там, где стоит сумма и описание
            tail = line[date_end:]
            amounts = self.MONEY_PATTERN.findall(tail)
            if not amounts:
                # Строка с датой, но без распознаваемой суммы. Молча
                # пропускаем — это шапка, футер или строка периода.
                continue

            # Из нескольких чисел берём последнее: в выписках порядок
            # «сумма … остаток» встречается реже, чем «описание … сумма».
            amount = self._parse_amount_adaptive(amounts[-1])
            if amount == 0:
                continue

            tx_type = self._detect_transaction_type(line, amount)
            self.transactions.append(Transaction(
                date=date,
                amount=amount,
                type=tx_type,
                description=tail.strip() or line,
                currency=self.detected_currency,
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
