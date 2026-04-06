"""
PatternDetector — детектор конкретных схем мошенничества.

Обнаруживает 6 named-паттернов с доказательной базой и контраргументами.
Каждый паттерн содержит: уверенность (0-1), улики, причину, контраргумент,
ссылку на НПА Республики Казахстан.
"""
from collections import defaultdict
from datetime import timedelta
from typing import List

from .models import AccountProfile, AccountType, FlaggedPattern


# Казахстанский регуляторный порог отчётности (AML)
KZ_AML_THRESHOLD = 1_000_000  # тенге


class PatternDetector:
    """
    Анализирует транзакции на конкретные мошеннические схемы.

    Использование:
        detector = PatternDetector()
        patterns = detector.detect_all(transactions, profile)
    """

    def detect_all(
        self,
        transactions: list,
        profile: AccountProfile
    ) -> List[FlaggedPattern]:
        """Запустить все детекторы и вернуть список найденных паттернов."""
        if not transactions:
            return []

        patterns: List[FlaggedPattern] = []
        patterns.extend(self._detect_layering(transactions, profile))
        patterns.extend(self._detect_structuring(transactions, profile))
        patterns.extend(self._detect_carding(transactions, profile))
        patterns.extend(self._detect_pyramid_scheme(transactions, profile))
        patterns.extend(self._detect_human_trafficking(transactions, profile))
        patterns.extend(self._detect_tax_evasion(transactions, profile))

        # Сортируем по убыванию confidence
        return sorted(patterns, key=lambda p: p.confidence, reverse=True)

    # ──────────────────────────────────────────────────────────────────
    # 1. Отмывание денег — этап расслоения (Layering)
    # ──────────────────────────────────────────────────────────────────

    def _detect_layering(
        self,
        transactions: list,
        profile: AccountProfile
    ) -> List[FlaggedPattern]:
        """
        Признак: крупное поступление → быстрое перераспределение 3+ получателям за 72ч.
        Покрывает >= 70% суммы поступления.
        """
        patterns = []
        income_txs = sorted(
            [t for t in transactions if self._amount(t) >= 500_000],
            key=lambda t: self._date(t) or self._min_date(transactions)
        )

        for inc in income_txs:
            inc_date = self._date(inc)
            if inc_date is None:
                continue
            window_end = inc_date + timedelta(hours=72)

            out_window = [
                t for t in transactions
                if self._amount(t) < 0
                and inc_date <= (self._date(t) or inc_date) <= window_end
            ]
            if len(out_window) < 3:
                continue

            unique_dests = set(
                self._counterparty(t) for t in out_window if self._counterparty(t)
            )
            if len(unique_dests) < 3:
                continue

            total_out = sum(abs(self._amount(t)) for t in out_window)
            coverage = total_out / self._amount(inc)

            if coverage < 0.70:
                continue

            # Снижаем уверенность для владельцев бизнеса и фрилансеров
            # v4.3: повышен порог получение→траты — обычный человек тоже тратит после зарплаты
            base_confidence = min(0.90, 0.50 + coverage * 0.40)
            if profile.account_type == AccountType.BUSINESS_OWNER:
                base_confidence -= 0.35
            elif profile.account_type == AccountType.FREELANCER:
                base_confidence -= 0.30
            elif profile.account_type == AccountType.SALARY_EMPLOYEE:
                base_confidence -= 0.20

            # Требуем минимум 5 уникальных получателей (3 — нормально: аренда, ЖКХ, перевод)
            if len(unique_dests) < 5:
                base_confidence -= 0.15

            if base_confidence < 0.15:
                continue

            patterns.append(FlaggedPattern(
                pattern_name="money_laundering_layering",
                display_name="Подозрение на отмывание денег — этап расслоения",
                confidence=round(base_confidence, 2),
                risk_contribution=round(base_confidence * 85, 1),
                evidence=[{
                    "income_date": str(inc_date.date()),
                    "income_amount_kzt": round(self._amount(inc), 2),
                    "income_source": self._counterparty(inc) or "Неизвестно",
                    "outflows_count": len(out_window),
                    "unique_destinations": len(unique_dests),
                    "total_redistributed_kzt": round(total_out, 2),
                    "redistribution_pct": round(coverage * 100, 1),
                    "window_hours": 72,
                }],
                reason=(
                    f"Поступление {self._amount(inc):,.0f} ₸ перераспределено "
                    f"на {len(unique_dests)} получателей в течение 72 часов "
                    f"({coverage * 100:.0f}% суммы). "
                    f"Всего исходящих транзакций: {len(out_window)}."
                ),
                counter_evidence=(
                    "Может быть законным: выплата зарплат сотрудникам, "
                    "расчёты с подрядчиками, возврат займов нескольким кредиторам, "
                    "групповая покупка или инвестиция."
                    if profile.account_type in (
                        AccountType.BUSINESS_OWNER, AccountType.FREELANCER
                    ) else
                    "Может быть законным: групповой сбор средств (свадьба, лечение), "
                    "возврат долгов нескольким людям."
                ),
                regulatory_reference="ЗРК О ПОД/ФТ ст. 4, п. 1; FATF Recommendation 1"
            ))

        return patterns

    # ──────────────────────────────────────────────────────────────────
    # 2. Структурирование (Structuring / Smurfing)
    # ──────────────────────────────────────────────────────────────────

    def _detect_structuring(
        self,
        transactions: list,
        profile: AccountProfile
    ) -> List[FlaggedPattern]:
        """
        Признак: намеренное деление сумм так, чтобы оставаться ниже порога 1M KZT.
        Учитываем доход: для высокодоходных аккаунтов порог выше.
        """
        patterns = []

        # Для высокодоходных — поднимаем порог чтобы не флагировать ипотеку
        effective_threshold = max(
            KZ_AML_THRESHOLD,
            profile.avg_monthly_income * 0.8
        )
        # SALARY_EMPLOYEE: всегда строгий регуляторный порог
        if profile.account_type == AccountType.SALARY_EMPLOYEE:
            effective_threshold = KZ_AML_THRESHOLD

        low = effective_threshold * 0.90
        high = effective_threshold

        just_under = [
            t for t in transactions
            if self._amount(t) < 0 and low <= abs(self._amount(t)) < high
        ]

        if len(just_under) < 2:
            return patterns

        confidence = min(0.85, len(just_under) * 0.15)
        patterns.append(FlaggedPattern(
            pattern_name="structuring",
            display_name="Структурирование — дробление сумм ниже порога отчётности",
            confidence=round(confidence, 2),
            risk_contribution=round(confidence * 70, 1),
            evidence=[{
                "date": str(self._date(t).date()) if self._date(t) else "?",
                "amount_kzt": round(abs(self._amount(t)), 2),
                "pct_of_threshold": round(abs(self._amount(t)) / effective_threshold * 100, 1),
                "counterparty": self._counterparty(t) or "Неизвестно",
            } for t in just_under[:10]],
            reason=(
                f"{len(just_under)} транзакций в диапазоне "
                f"{low:,.0f}–{high:,.0f} ₸ "
                f"(90–100% от порога отчётности {effective_threshold:,.0f} ₸)."
            ),
            counter_evidence=(
                "Суммы могут случайно приближаться к порогу: "
                "ипотечный платёж, оплата крупной покупки, аренда."
            ),
            regulatory_reference="ЗРК О ПОД/ФТ ст. 11; FATF Recommendation 10"
        ))
        return patterns

    # ──────────────────────────────────────────────────────────────────
    # 3. Кардинг (Carding)
    # ──────────────────────────────────────────────────────────────────

    def _detect_carding(
        self,
        transactions: list,
        profile: AccountProfile
    ) -> List[FlaggedPattern]:
        """
        Признак: 5+ мелких покупок (<10K KZT) в иностранной валюте за 2 часа.
        Типично для кардеров, тестирующих похищенные карты.
        """
        patterns = []

        small_foreign = sorted([
            t for t in transactions
            if (self._amount(t) < 0
                and abs(self._amount(t)) < 10_000
                and self._foreign_currency(t))
        ], key=lambda t: self._date(t) or self._min_date(transactions))

        if len(small_foreign) < 5:
            return patterns

        # Кластеризация по временным окнам (2 часа)
        bursts = []
        current = [small_foreign[0]]

        for i in range(1, len(small_foreign)):
            prev_date = self._date(small_foreign[i - 1])
            curr_date = self._date(small_foreign[i])
            if (prev_date and curr_date and
                    (curr_date - prev_date) <= timedelta(hours=2)):
                current.append(small_foreign[i])
            else:
                if len(current) >= 5:
                    bursts.append(current)
                current = [small_foreign[i]]

        if len(current) >= 5:
            bursts.append(current)

        for burst in bursts:
            unique_merchants = set(self._counterparty(t) for t in burst)
            confidence = min(0.85, 0.40 + len(burst) * 0.04)
            burst_date = self._date(burst[0])

            patterns.append(FlaggedPattern(
                pattern_name="carding",
                display_name="Признаки кардинга — тестирование карт",
                confidence=round(confidence, 2),
                risk_contribution=round(confidence * 75, 1),
                evidence=[{
                    "burst_start": str(burst_date.date()) if burst_date else "?",
                    "transactions_count": len(burst),
                    "unique_merchants": len(unique_merchants),
                    "total_amount_kzt": round(sum(abs(self._amount(t)) for t in burst), 2),
                    "avg_amount_kzt": round(
                        sum(abs(self._amount(t)) for t in burst) / len(burst), 2
                    ),
                    "currencies": list(set(
                        self._foreign_currency(t) for t in burst
                        if self._foreign_currency(t)
                    )),
                }],
                reason=(
                    f"{len(burst)} мелких покупок в иностранной валюте "
                    f"у {len(unique_merchants)} мерчантов за 2 часа."
                ),
                counter_evidence=(
                    "Может быть законным: туристические мелкие покупки, "
                    "тестирование нескольких сервисов, подписки в разных сервисах."
                ),
                regulatory_reference="УК РК ст. 205 (мошенничество); FATF R.15"
            ))

        return patterns

    # ──────────────────────────────────────────────────────────────────
    # 4. Финансовая пирамида
    # ──────────────────────────────────────────────────────────────────

    def _detect_pyramid_scheme(
        self,
        transactions: list,
        profile: AccountProfile
    ) -> List[FlaggedPattern]:
        """
        Признак: много мелких поступлений от разных физлиц → один крупный перевод наружу.
        """
        patterns = []

        person_inflows = [
            t for t in transactions
            if (self._amount(t) > 0
                and self._amount(t) < 200_000
                and self._is_person(t))
        ]

        unique_payers = set(self._counterparty(t) for t in person_inflows)
        if len(unique_payers) < 5:
            return patterns

        total_in = sum(self._amount(t) for t in person_inflows)

        large_outflows = [
            t for t in transactions
            if (self._amount(t) < 0
                and abs(self._amount(t)) > total_in * 0.50
                and self._is_person(t))
        ]

        if not large_outflows:
            return patterns

        confidence = min(0.75, 0.35 + len(unique_payers) * 0.04)

        patterns.append(FlaggedPattern(
            pattern_name="pyramid_scheme",
            display_name="Признаки участия в финансовой пирамиде",
            confidence=round(confidence, 2),
            risk_contribution=round(confidence * 65, 1),
            evidence=[{
                "unique_small_payers": len(unique_payers),
                "total_small_inflows_kzt": round(total_in, 2),
                "large_outflow_amount_kzt": round(abs(self._amount(large_outflows[0])), 2),
                "large_outflow_recipient": self._counterparty(large_outflows[0]) or "?",
            }],
            reason=(
                f"Поступления от {len(unique_payers)} физических лиц "
                f"общей суммой {total_in:,.0f} ₸, "
                f"затем крупный перевод "
                f"{abs(self._amount(large_outflows[0])):,.0f} ₸ одному получателю."
            ),
            counter_evidence=(
                "Может быть законным: краудфандинг, групповой сбор на подарок/лечение, "
                "возврат займа организатору поездки."
            ),
            regulatory_reference="УК РК ст. 216 (незаконная организация финансовой пирамиды)"
        ))
        return patterns

    # ──────────────────────────────────────────────────────────────────
    # 5. Выплаты связанные с торговлей людьми
    # ──────────────────────────────────────────────────────────────────

    def _detect_human_trafficking(
        self,
        transactions: list,
        profile: AccountProfile
    ) -> List[FlaggedPattern]:
        """
        Признак: регулярные небольшие выплаты 10K–100K ₸ >= 5 разным физлицам.
        НЕ применяется к BUSINESS_OWNER (может быть зарплата).
        """
        # Для работодателей — это может быть выплата зарплат
        if profile.account_type == AccountType.BUSINESS_OWNER:
            return []

        patterns = []

        person_transfers = [
            t for t in transactions
            if (self._amount(t) < 0
                and 10_000 <= abs(self._amount(t)) <= 100_000
                and self._is_person(t))
        ]

        if len(person_transfers) < 10:
            return patterns

        unique_persons = set(self._counterparty(t) for t in person_transfers)
        if len(unique_persons) < 5:
            return patterns

        total_amount = sum(abs(self._amount(t)) for t in person_transfers)
        confidence = min(0.70, 0.25 + len(unique_persons) * 0.04)

        patterns.append(FlaggedPattern(
            pattern_name="human_trafficking_payments",
            display_name="Систематические выплаты многим физическим лицам",
            confidence=round(confidence, 2),
            risk_contribution=round(confidence * 60, 1),
            evidence=[{
                "unique_recipients": len(unique_persons),
                "total_transfers": len(person_transfers),
                "total_amount_kzt": round(total_amount, 2),
                "avg_per_transfer_kzt": round(total_amount / len(person_transfers), 2),
                "sample_recipients": list(unique_persons)[:5],
            }],
            reason=(
                f"Регулярные выплаты {len(unique_persons)} разным физическим лицам, "
                f"итого {len(person_transfers)} переводов на {total_amount:,.0f} ₸."
            ),
            counter_evidence=(
                "Может быть законным: выплата фрилансерам, погашение нескольких "
                "личных займов, субаренда жилья."
            ),
            regulatory_reference="УК РК ст. 135 (торговля людьми); ЗРК О ПОД/ФТ ст. 4"
        ))
        return patterns

    # ──────────────────────────────────────────────────────────────────
    # 6. Уклонение от налогов (наличные)
    # ──────────────────────────────────────────────────────────────────

    def _detect_tax_evasion(
        self,
        transactions: list,
        profile: AccountProfile
    ) -> List[FlaggedPattern]:
        """
        Признак: крупные наличные поступления (ATM/кэш) без прослеживаемого источника.
        Наличные > 50% от электронного дохода → подозрительно.
        """
        patterns = []

        cash_deposits = [
            t for t in transactions
            if (self._amount(t) > 0
                and (getattr(t, 'is_atm', False)
                     or getattr(t, 'is_cash_operation', False)
                     or 'БАНКОМАТ' in self._counterparty(t).upper()
                     or 'ATM' in self._counterparty(t).upper()
                     or 'НАЛИЧН' in (getattr(t, 'description', '') or '').upper()))
        ]

        total_cash_in = sum(self._amount(t) for t in cash_deposits)

        if total_cash_in < 500_000:
            return patterns

        known_electronic_income = sum(
            self._amount(t) for t in transactions
            if (self._amount(t) > 0
                and not getattr(t, 'is_atm', False)
                and not getattr(t, 'is_cash_operation', False))
        )

        unexplained_ratio = total_cash_in / (known_electronic_income + 1)

        if unexplained_ratio < 0.50:
            return patterns

        confidence = min(0.80, 0.25 + unexplained_ratio * 0.25)

        patterns.append(FlaggedPattern(
            pattern_name="tax_evasion_cash",
            display_name="Возможное уклонение от налогов — налично-кассовые операции",
            confidence=round(confidence, 2),
            risk_contribution=round(confidence * 60, 1),
            evidence=[{
                "total_cash_deposits_kzt": round(total_cash_in, 2),
                "known_electronic_income_kzt": round(known_electronic_income, 2),
                "unexplained_ratio": round(unexplained_ratio, 2),
                "cash_deposit_count": len(cash_deposits),
            }],
            reason=(
                f"Наличные поступления {total_cash_in:,.0f} ₸ составляют "
                f"{unexplained_ratio * 100:.0f}% от прослеживаемого "
                f"электронного дохода {known_electronic_income:,.0f} ₸."
            ),
            counter_evidence=(
                "Может быть законным: продажа личного имущества (авто, недвижимость), "
                "займ от родственников, ранее накопленные наличные сбережения."
            ),
            regulatory_reference=(
                "НК РК ст. 320 (доходы физических лиц); "
                "ЗРК О ПОД/ФТ ст. 11 (обязательный финансовый мониторинг)"
            )
        ))
        return patterns

    # ── Вспомогательные методы ──────────────────────────────────────

    def _amount(self, t) -> float:
        return float(getattr(t, 'amount', 0) or 0)

    def _date(self, t):
        for attr in ('transaction_date', 'date', 'created_at'):
            val = getattr(t, attr, None)
            if val is not None:
                return val
        return None

    def _min_date(self, transactions: list):
        dates = [self._date(t) for t in transactions if self._date(t)]
        return min(dates) if dates else None

    def _counterparty(self, t) -> str:
        for attr in ('counterparty_name', 'counterparty', 'merchant_name'):
            val = getattr(t, attr, None)
            if val:
                return str(val).strip()
        return ""

    def _foreign_currency(self, t) -> str:
        """Вернуть иностранную валюту транзакции, если есть."""
        orig_currency = getattr(t, 'original_currency', None)
        if orig_currency and orig_currency not in ('KZT', 'KZT '):
            return str(orig_currency)
        # Альтернатива: если currency != KZT
        currency = getattr(t, 'currency', 'KZT')
        if currency and currency not in ('KZT', '₸'):
            return str(currency)
        return ""

    def _is_person(self, t) -> bool:
        """
        Определить, является ли контрагент физическим лицом.
        Эвристика: нет ключевых слов юрлица, короткое имя с инициалами.
        """
        cp = self._counterparty(t).upper()
        if not cp:
            return False
        # Юрлица
        for kw in ("ТОО", "АО ", "ИП ", "ООО", "ГКП", "BANK", "БАНК",
                   "KASPI", "HALYK", "МАГНУМ", "MAGNUM", "MARKET"):
            if kw in cp:
                return False
        # Имя с инициалами (например "Ержан А." или "NURLAN B")
        counterparty_type = getattr(t, 'counterparty_type', None)
        if counterparty_type is not None:
            return str(counterparty_type).lower() in ('person', 'individual', 'физлицо')
        # Эвристика по длине
        return len(cp.split()) <= 4
