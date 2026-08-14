"""Классификация контрагентов: мерчант, физлицо, банк, госорган.

Зачем это отдельный слой. Парсер извлекает строку «Yandex Go poezdka» —
и на этом его возможности заканчиваются. Детекторам (`merchant_risk`,
граф контрагентов, `profile_mismatch`) нужно не написание, а сущность:
магазин это или перевод человеку. Бенчмарк на незнакомых форматах
показывает разрыв прямо: 200/200 строк извлечено, 100% контрагентов
получено, `counterparty_type` не определён ни у одной — и композитный
балл 17.4 LOW против 63.0 HIGH на тех же деньгах и датах.

Регулярка эту задачу не решает: «Magnum» магазин, а «Ержан О.» человек не
потому, что они по-разному написаны, а потому, что мы знаем, что такое
Magnum. Сейчас это знание живёт в рукописных словарях внутри парсеров
Kaspi и Halyk и покрывает ровно те банки, для которых кто-то их написал.

Порядок принятия решения — от бесплатного к дорогому:

1. **Анонимизатор.** Имя, заменённое на «[ФИО-1]», уже опознано как
   физлицо детерминированным правилом. Спрашивать модель незачем, и
   отправлять наружу нечего.
2. **Кэш.** «Magnum» повторяется в выписках разных людей. Названия
   организаций персональными данными не являются, поэтому кэшируются.
3. **LLM.** Остаток — батчами, по уникальным именам. В выписке Kaspi на
   1320 транзакций уникальных контрагентов 329: дедупликация экономит
   вчетверо ещё до кэша.
4. **Правило.** Модель недоступна или ответила мусором — падаем на
   `is_organization` и помечаем источник, чтобы это было видно в отчёте,
   а не выглядело как результат работы модели.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.services.bank_analyzer.base_parser import CounterpartyType
from app.utils.helpers import is_organization

logger = logging.getLogger(__name__)

#: Плейсхолдеры анонимизатора: «[ФИО-1]», «[CUSTOMER]», «[ИИН-2]».
PLACEHOLDER_PATTERN = re.compile(r'^\[[A-ZА-ЯЁ_]+(?:-\d+)?\]$')

#: Кириллица с казахскими буквами, включая латинскую schwa Ə (U+018F),
#: которой в выписках печатают казахскую Ә.
_CYR = r'А-ЯЁӘҒҚҢӨҰҮІҺа-яёәғқңөұүіһƏə'

#: «Ержан О.» и «Ержан О.М.» — форма записи контрагента-физлица в выписках.
PERSON_INITIAL_PATTERN = re.compile(rf'^[{_CYR}][{_CYR}]+\s+[{_CYR}]\.(?:\s*[{_CYR}]\.)?$')

#: «Ержан Омаров», «Омаров Ержан Болатович» — два-три слова с заглавной.
FULL_NAME_PATTERN = re.compile(
    rf'^[{_CYR}][{_CYR}]+(?:\s+[{_CYR}][{_CYR}]+){{1,2}}$'
)


def _looks_like_full_name(value: str) -> bool:
    """Похоже ли на ФИО целиком.

    Проверка намеренно узкая. Ошибиться в другую сторону — записать
    организацию в физлица — хуже: организация выпадет из графа
    контрагентов, где как раз и видны схемы вывода средств.
    """
    return bool(FULL_NAME_PATTERN.match(value.strip()))

#: Организационно-правовые формы РК. Нужны и как признак организации,
#: и как отдельное поле `merchant_type` в отчёте.
LEGAL_FORMS = {
    "ТОО": "ТОО", "АО": "АО", "ИП": "ИП", "ЖШС": "ТОО", "АҚ": "АО",
    "ЖК": "ИП", "ПК": "ПК", "КХ": "КХ", "ОФ": "ОФ", "РГП": "РГП",
    "ГУ": "ГУ", "КГП": "КГП", "LLP": "ТОО", "LLC": "ТОО",
}

_TYPE_BY_NAME = {t.value: t for t in CounterpartyType}

#: Схема tool_use. Модель обязана вернуть запись на каждое переданное имя;
#: сверка по `index` ловит пропуски и перестановки.
CLASSIFICATION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "counterparties": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "Номер контрагента из входного списка",
                    },
                    "kind": {
                        "type": "string",
                        "enum": [t.value for t in CounterpartyType],
                        "description": (
                            "merchant — торговая точка, сервис, интернет-магазин; "
                            "person — физическое лицо; bank — банк или платёжная "
                            "система; government — госорган, налоговая, суд, "
                            "пенсионный фонд; unknown — определить невозможно"
                        ),
                    },
                    "merchant_name": {
                        "type": "string",
                        "description": (
                            "Узнаваемое название без технического мусора: из "
                            "'Yandex Go poezdka 12.05' — 'Yandex Go'. Пустая "
                            "строка, если это не мерчант."
                        ),
                    },
                    "merchant_type": {
                        "type": "string",
                        "description": "Форма: ТОО, АО, ИП. Пустая строка, если неизвестна.",
                    },
                    "category": {
                        "type": "string",
                        "description": (
                            "Одно слово: транспорт, продукты, связь, развлечения, "
                            "здоровье, одежда, финансы, госуслуги, прочее"
                        ),
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Уверенность 0..1",
                    },
                },
                "required": ["index", "kind", "confidence"],
            },
        }
    },
    "required": ["counterparties"],
}

SYSTEM_PROMPT = (
    "Ты классифицируешь контрагентов из банковских выписок Казахстана. "
    "Названия встречаются на русском, казахском и английском, часто с "
    "техническим мусором: кодами городов, номерами терминалов, датами.\n\n"
    "Правила:\n"
    "- ТОО, АО, ЖШС, АҚ, ИП, ЖК — организации, а не физические лица.\n"
    "- Плейсхолдеры вида [ФИО-1] — это обезличенные физические лица.\n"
    "- Kaspi, Halyk, Jusan, Forte, Freedom, Binance — банки и платёжные системы.\n"
    "- Комитет госдоходов, ЦОН, ГЦВП, суды — government.\n"
    "- Не выдумывай: если название ни о чём не говорит, ставь unknown с "
    "низкой уверенностью. Ошибочная уверенная классификация вреднее пропуска, "
    "потому что на этих данных строится оценка риска в уголовном деле."
)


@dataclass(frozen=True)
class Classification:
    """Результат по одному контрагенту.

    `source` не косметика: он отделяет вывод модели от догадки правила,
    и попадает в отчёт, чтобы следователь видел, чем обосновано.
    """

    counterparty_type: CounterpartyType = CounterpartyType.UNKNOWN
    merchant_name: Optional[str] = None
    merchant_type: Optional[str] = None
    category: Optional[str] = None
    confidence: float = 0.0
    source: str = "rule"


@dataclass
class ClassificationStats:
    """Сколько имён каким путём получено — печатается в бенчмарке."""

    total: int = 0
    from_anonymizer: int = 0
    from_cache: int = 0
    from_llm: int = 0
    from_rule: int = 0
    llm_batches: int = 0
    llm_failures: int = 0
    provider: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "from_anonymizer": self.from_anonymizer,
            "from_cache": self.from_cache,
            "from_llm": self.from_llm,
            "from_rule": self.from_rule,
            "llm_batches": self.llm_batches,
            "llm_failures": self.llm_failures,
            "provider": self.provider,
            "llm_coverage_pct": (
                100.0 * self.from_llm / self.total if self.total else 0.0
            ),
        }


def extract_legal_form(name: str) -> Optional[str]:
    """Форма организации из названия: «ТОО "Астана Строй"» → «ТОО»."""
    for token in re.split(r'[\s"«»,.]+', name):
        canonical = LEGAL_FORMS.get(token.upper())
        if canonical:
            return canonical
    return None


def classify_by_rule(name: str) -> Classification:
    """Детерминированный запасной вариант — он же поведение до этого слоя.

    Специально скромен: `is_organization` отличает организацию от всего
    остального и не знает, что «Yandex Go poezdka» — сервис такси. Отсюда
    и разрыв, который закрывает модель.
    """
    cleaned = (name or "").strip()
    if not cleaned:
        return Classification()

    if PLACEHOLDER_PATTERN.match(cleaned):
        return Classification(
            counterparty_type=CounterpartyType.PERSON,
            confidence=1.0,
            source="anonymizer",
        )

    form = extract_legal_form(cleaned)
    if form or is_organization(cleaned):
        return Classification(
            counterparty_type=CounterpartyType.MERCHANT,
            merchant_name=cleaned,
            merchant_type=form,
            confidence=0.5,
            source="rule",
        )

    # «Ержан О.» — не организация, значит физлицо. Возвращать здесь UNKNOWN
    # опасно: детектор зарплаты пропускает контрагентов с неопределённым
    # типом, и человек, регулярно переводивший деньги, попадал в
    # работодатели — то есть подменял профиль счёта в материалах дела.
    if PERSON_INITIAL_PATTERN.match(cleaned) or _looks_like_full_name(cleaned):
        return Classification(
            counterparty_type=CounterpartyType.PERSON,
            confidence=0.5,
            source="rule",
        )
    return Classification(source="rule")


class CounterpartyClassifier:
    """Классифицирует уникальные имена контрагентов.

    `ai_manager` — любой объект с `generate_structured(prompt, schema,
    system_prompt) -> (dict, provider_name)`; в тестах туда передаётся
    двойник, поэтому ключ API для запуска не нужен.

    Когда `ai_manager` не передан, класс работает целиком на правилах.
    Это осознанный режим: система обязана оставаться работоспособной без
    облака, лишь с худшим качеством, а не падать.
    """

    def __init__(
        self,
        ai_manager: Any = None,
        cache: Optional[Dict[str, Classification]] = None,
        batch_size: int = 40,
        min_confidence: float = 0.4,
    ) -> None:
        self._ai = ai_manager
        self._cache = cache if cache is not None else {}
        self._batch_size = max(1, batch_size)
        self._min_confidence = min_confidence
        self.stats = ClassificationStats()

    # ── публичный API ────────────────────────────────────────────

    async def classify(self, names: Iterable[Optional[str]]) -> Dict[str, Classification]:
        """Имя → классификация. Порядок: анонимизатор, кэш, LLM, правило."""
        unique = self._unique(names)
        self.stats = ClassificationStats(total=len(unique))
        if not unique:
            return {}

        resolved: Dict[str, Classification] = {}
        need_llm: List[str] = []

        for name in unique:
            placeholder_or_cached = self._resolve_cheaply(name)
            if placeholder_or_cached is not None:
                resolved[name] = placeholder_or_cached
            else:
                need_llm.append(name)

        if need_llm and self._ai is not None:
            resolved.update(await self._classify_via_llm(need_llm))

        # Всё, чего модель не покрыла — правилом. Ветка обязана быть рабочей:
        # именно она отвечает за поведение при недоступном провайдере.
        for name in unique:
            if name not in resolved:
                resolved[name] = classify_by_rule(name)
                self.stats.from_rule += 1

        return resolved

    def apply(self, transactions: Sequence[Any], mapping: Dict[str, Classification]) -> int:
        """Перенести классификации в транзакции. Возвращает число изменённых.

        Уже заполненное парсером не трогаем: банк-специфичный парсер знает
        свою выписку лучше, чем модель — общий текст.
        """
        changed = 0
        for tx in transactions:
            key = self._key(getattr(tx, "counterparty", None) or getattr(tx, "description", None))
            result = mapping.get(key)
            if result is None:
                continue

            touched = False
            if getattr(tx, "counterparty_type", None) is CounterpartyType.UNKNOWN:
                tx.counterparty_type = result.counterparty_type
                touched = True
            if result.merchant_name and not getattr(tx, "merchant_name", None):
                tx.merchant_name = result.merchant_name
                touched = True
            if result.merchant_type and not getattr(tx, "merchant_type", None):
                tx.merchant_type = result.merchant_type
                touched = True
            if result.category and not getattr(tx, "category", None):
                tx.category = result.category
                touched = True
            changed += touched
        return changed

    # ── внутреннее ───────────────────────────────────────────────

    @staticmethod
    def _key(value: Optional[str]) -> str:
        return (value or "").strip()

    def _unique(self, names: Iterable[Optional[str]]) -> List[str]:
        """Порядок сохраняем: батчи и логи должны быть воспроизводимы."""
        seen: Dict[str, None] = {}
        for name in names:
            key = self._key(name)
            if key:
                seen.setdefault(key, None)
        return list(seen)

    def _resolve_cheaply(self, name: str) -> Optional[Classification]:
        """Плейсхолдер или кэш — без сетевого вызова."""
        if PLACEHOLDER_PATTERN.match(name):
            self.stats.from_anonymizer += 1
            return Classification(
                counterparty_type=CounterpartyType.PERSON,
                confidence=1.0,
                source="anonymizer",
            )
        cached = self._cache.get(name)
        if cached is not None:
            self.stats.from_cache += 1
            return cached
        return None

    async def _classify_via_llm(self, names: Sequence[str]) -> Dict[str, Classification]:
        resolved: Dict[str, Classification] = {}
        for start in range(0, len(names), self._batch_size):
            batch = list(names[start:start + self._batch_size])
            self.stats.llm_batches += 1
            try:
                payload, provider = await self._ai.generate_structured(
                    self._build_prompt(batch), CLASSIFICATION_SCHEMA, SYSTEM_PROMPT
                )
            except Exception as exc:
                # Падение провайдера не должно ронять анализ: остаток уйдёт
                # в правило, и это будет видно в статистике.
                logger.warning("Не удалось классифицировать батч контрагентов: %s", exc)
                self.stats.llm_failures += 1
                continue

            self.stats.provider = self.stats.provider or provider
            batch_result = self._parse_response(payload, batch)
            if not batch_result:
                self.stats.llm_failures += 1
                continue

            for name, result in batch_result.items():
                resolved[name] = result
                self.stats.from_llm += 1
                # Организации кэшируем, физлиц — никогда: имя человека
                # персональные данные, и в общем кэше ему не место.
                if result.counterparty_type is not CounterpartyType.PERSON:
                    self._cache[name] = result
        return resolved

    @staticmethod
    def _build_prompt(batch: Sequence[str]) -> str:
        listing = "\n".join(f"{i}. {name}" for i, name in enumerate(batch))
        return (
            "Классифицируй контрагентов из банковской выписки.\n"
            "Верни ровно одну запись на каждый номер из списка.\n\n"
            f"{listing}"
        )

    def _parse_response(
        self, payload: Any, batch: Sequence[str]
    ) -> Dict[str, Classification]:
        """Разобрать ответ модели, отбрасывая всё, чему нельзя доверять.

        Модель может вернуть строку вместо объекта, промахнуться индексом,
        придумать тип или ответить с низкой уверенностью. Каждый такой
        случай — молчаливый пропуск: имя уйдёт в правило. Тихо подставлять
        сомнительную классификацию нельзя, на ней строится оценка риска.
        """
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                return {}
        if not isinstance(payload, dict):
            return {}

        items = payload.get("counterparties")
        if not isinstance(items, list):
            return {}

        result: Dict[str, Classification] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            if not isinstance(index, int) or not 0 <= index < len(batch):
                continue

            kind = _TYPE_BY_NAME.get(str(item.get("kind", "")).strip().lower())
            if kind is None:
                continue

            try:
                confidence = float(item.get("confidence", 0.0))
            except (TypeError, ValueError):
                continue
            if confidence < self._min_confidence:
                continue

            name = batch[index]
            merchant_name = str(item.get("merchant_name") or "").strip() or None
            merchant_type = str(item.get("merchant_type") or "").strip() or None
            result[name] = Classification(
                counterparty_type=kind,
                merchant_name=merchant_name if kind is CounterpartyType.MERCHANT else None,
                merchant_type=LEGAL_FORMS.get((merchant_type or "").upper(), merchant_type),
                category=str(item.get("category") or "").strip() or None,
                confidence=min(confidence, 1.0),
                source="llm",
            )
        return result
