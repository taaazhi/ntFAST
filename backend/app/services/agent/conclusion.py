"""Заключение по выписке: связный вывод, а не набор чисел.

Зачем это ядро, а не украшение. Система считает одиннадцать модулей, строит
граф связей, находит схемы и подбирает нормы — и отдаёт следователю числа,
флаги и ссылки. Собрать из этого картину: что происходило по счёту, какие
признаки складываются вместе, что говорит против версии и чего не хватает
для вывода — до сих пор приходилось человеку, в голове, по каждому делу.

Правилами такой текст не пишется. Это единственное место в проекте, где
языковая модель делает работу, которую больше делать нечем, — и потому
здесь она стоит в основе пути «выписка → заключение», а не сбоку.

Три условия, без которых заключение вредно:

1. **Модель не считает.** Ей передаются уже посчитанные факты — суммы,
   количества, баллы, — и её задача связать их, а не вычислить. Каждое
   число в готовом тексте сверяется с фактами; чужое число делает
   заключение непроверенным.
2. **Модель не выдумывает норм.** Ссылки на статьи проверяются по корпусу
   после генерации, независимо от того, откуда модель их взяла.
3. **Отказ громкий.** Нет модели — нет заключения. Подделка отсутствующего
   вывода в документе для следствия хуже, чем его отсутствие.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты готовишь заключение по банковской выписке для следователя.

Тебе даны уже посчитанные факты. Твоя работа — связать их в текст, а не
пересчитывать: любое число бери из фактов дословно, своих не добавляй.

Структура заключения:
1. Что происходило по счёту — фактическая картина за период.
2. Какие признаки сработали и что они означают вместе.
3. Что говорит против этой версии — законные объяснения тех же признаков.
4. Применимые нормы — только те, что приведены в фактах.
5. Чего не хватает для вывода — какие данные следует запросить.

Требования:
- Речь идёт о счёте владельца. Операции по счёту совершает он, а метки вида
  [PERSON_1] обозначают его контрагентов — тех, кому он платил или от кого
  получал. Не приписывай действия по счёту контрагенту: перепутать субъекта
  и контрагента в заключении — грубая ошибка. Владельца называй «владелец
  счёта», не пытайся угадать, кто за меткой стоит.
- Не выноси обвинений и не предрешай квалификацию. Признак — основание для
  проверки, а не доказательство: «требует проверки», а не «подтверждает
  вину». Решение принимает следователь, заключение лишь готовит материал.
- Числа переписывай из фактов дословно, в том же виде. Не переводи в
  миллионы, не округляй, не считай проценты и разности — любое число,
  которого нет в фактах, делает заключение непригодным. Разность доходов и
  расходов уже посчитана и лежит в поле net_flow: бери её оттуда, не
  вычитай самостоятельно.
- Разделяй наблюдение и версию: сведения из фактов — наблюдение, их
  истолкование — версия, и она требует оговорки.
- Не называй статью, которой нет в фактах. Отсутствие нормы — не повод её
  придумать.
- Если признаков мало, так и скажи. Заключение «оснований не выявлено» —
  нормальный результат, а не неудача.
- Пиши по-русски, деловым языком, без канцелярита и без запугивания.
"""


#: Иероглифы и другие письменности, которых в заключении быть не может.
#: Qwen2.5 обучена в том числе на китайском, и на локальной модели он
#: изредка прорывается в текст: «нулевому流入流出 (net_flow)». Для документа,
#: который ложится в дело, это брак, а не мелочь.
_FOREIGN_SCRIPT = re.compile(
    r"[぀-ヿ㐀-䶿一-鿿가-힯]"
)


@dataclass
class Conclusion:
    """Заключение вместе со всем, что нужно для его проверки."""

    text: str = ""
    citations: List[Dict[str, Any]] = field(default_factory=list)
    #: Числа из текста, которых нет среди переданных фактов.
    invented_numbers: List[str] = field(default_factory=list)
    provider: Optional[str] = None
    error: Optional[str] = None
    #: Текст упёрся в потолок длины и оборван на полуслове. Отдельный признак,
    #: а не ошибка: написанное до обрыва может быть полезно, но выдавать его
    #: за готовое заключение нельзя.
    truncated: bool = False

    @property
    def foreign_script(self) -> List[str]:
        """Фрагменты на чужой письменности, если модель их вставила."""
        return sorted(set(_FOREIGN_SCRIPT.findall(self.text or "")))

    @property
    def is_trustworthy(self) -> bool:
        """Можно ли показывать заключение без оговорок."""
        return (
            bool(self.text)
            and not self.error
            and not self.truncated
            and not self.invented_numbers
            and not self.foreign_script
            and all(c.get("verified") for c in self.citations)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "citations": self.citations,
            "invented_numbers": self.invented_numbers,
            "provider": self.provider,
            "error": self.error,
            "truncated": self.truncated,
            "is_trustworthy": self.is_trustworthy,
        }


def collect_facts(
    analysis_result: Dict[str, Any], anonymizer: Any = None
) -> Dict[str, Any]:
    """Выжимка из отчёта — то, на чём модель строит рассуждение.

    Передаётся именно выжимка, а не весь отчёт: тысяча транзакций в контекст
    не помещается, а модель, получившая сырые строки, начнёт считать сама.
    """
    summary = analysis_result.get("summary") or {}
    fraud = analysis_result.get("fraud_report") or {}
    account = analysis_result.get("account") or {}
    enrichment = analysis_result.get("enrichment") or {}
    graph = fraud.get("graph") or {}
    profile = fraud.get("account_profile") or {}

    def mask(value: Optional[str]) -> str:
        if not value:
            return ""
        return anonymizer.counterparty(value) if anonymizer else str(value)

    def money(value: Any) -> str:
        """Сумма готовой строкой: «5 540 137 ₸».

        Сырое число модель охотно переводит в миллионы и ошибается —
        «5 540 137,44» превращалось в «55,4013744 млн». Готовая строка не
        оставляет ей поводов считать.
        """
        try:
            return f"{round(float(value)):,} ₸".replace(",", " ")
        except (TypeError, ValueError):
            return "—"

    return {
        # Явно: чей это счёт. Без такой строки модель принимала метку
        # контрагента за владельца и писала «[PERSON_1] совершил покупки»,
        # хотя покупки совершал владелец, а [PERSON_1] — тот, кому он платил.
        #
        # Слово «обезличен» здесь стояло раньше, и модель прочитала его как
        # пробел в данных: заключение открывалось фразой «в период отсутствия
        # данных о владельце счёта». Имя скрыто намеренно — это надо сказать
        # так, чтобы не выглядело нехваткой сведений.
        "account_holder": (
            "субъект проверки; имя не передаётся по закону о персональных "
            "данных, называй его «владелец счёта»"
        ),
        "period": account.get("period") or {},
        "transactions": summary.get("total_transactions"),
        "total_income": money(summary.get("total_income")),
        "total_expense": money(summary.get("total_expense")),
        "net_flow": money(summary.get("net_flow")),
        "risk_score": fraud.get("composite_score"),
        "risk_level": fraud.get("risk_level"),
        "account_type": profile.get("account_type"),
        "counterparties": graph.get("node_count"),
        "connections": graph.get("edge_count"),
        "income_sources": [
            {"counterparty": mask(s.get("counterparty")), "reason": s.get("reason")}
            for s in (enrichment.get("salary_sources") or [])
        ],
        "flags": [
            {
                "module": f.get("module"),
                "reason": f.get("reason"),
                "counter_evidence": f.get("counter_evidence"),
                "contribution": f.get("score_contribution"),
            }
            for f in (fraud.get("explained_flags") or [])
        ],
        "patterns": [
            {
                "name": p.get("display_name") or p.get("pattern_name"),
                "reason": p.get("reason"),
                "counter_evidence": p.get("counter_evidence"),
                "confidence": p.get("confidence"),
                "articles": [
                    {"citation": a.get("citation"), "title": a.get("title")}
                    for a in (p.get("legal_articles") or [])
                    # Непроверенную норму модели не показываем вовсе: иначе
                    # она процитирует её в заключении как установленную.
                    if a.get("verified")
                ],
            }
            for p in (fraud.get("flagged_patterns") or [])
        ],
    }


#: Числа в тексте: «4 500 000», «84,000», «12», «63.0», «1 320».
#:
#: Две ветви. Первая — число с разделителями разрядов: группы ровно по три
#: цифры через пробел или запятую. Вторая — обычное число. Разделение нужно,
#: чтобы «12, 15» осталось двумя числами, а «1,440,000» стало одним.
_NUMBER = re.compile(
    r"\d{1,3}(?:[\s  ,]\d{3})+(?:[.,]\d+)?"
    r"|\d+(?:[.,]\d+)?"
)

#: Даты в любом принятом написании. Вырезаются до поиска чисел: период
#: «2025-08-14» модель законно перепишет как «14.08.2025», и без этого
#: «14.08» выглядело бы выдуманным числом, хотя это та же дата.
_DATE = re.compile(
    r"\b\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}\b"
    r"|\b\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}\b"
)


def _numbers_in(value: Any) -> set:
    """Все числа внутри структуры, приведённые к сопоставимому виду."""
    found = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for item in node.values():
                walk(item)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
        elif isinstance(node, (int, float)):
            found.add(_normalise_number(str(node)))
        elif isinstance(node, str):
            for match in _NUMBER.findall(node):
                found.add(_normalise_number(match))

    walk(value)
    return {n for n in found if n}


def _normalise_number(raw: str) -> str:
    """«4 500 000,00», «4,500,000» и «4500000.0» — одно и то же число.

    Запятая двусмысленна: в русском тексте это десятичный разделитель, а
    модель, обученная в основном на английском, ставит её между разрядами.
    Различаем по длине хвоста — ровно три цифры после запятой означают
    разряды. Без этого «84,000 ₸» превращалось в 84 и объявлялось выдумкой,
    хотя в фактах стояло ровно 84 000: проверка обвиняла верное заключение,
    а это хуже, чем не проверять вовсе.
    """
    cleaned = re.sub(r"[\s  ]", "", raw)
    cleaned = re.sub(r",(?=\d{3}(?:\D|$))", "", cleaned)
    cleaned = cleaned.replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return ""
    # Целые сравниваем как целые: 63.0 и 63 — одно число.
    return str(int(value)) if value == int(value) else f"{value:.2f}"


def find_invented_numbers(text: str, facts: Dict[str, Any]) -> List[str]:
    """Числа из заключения, которых нет среди фактов.

    Главная защита от правдоподобной выдумки. Модель, получив «12 переводов
    на 4 500 000 ₸», охотно напишет «около 4,5 млн» или «свыше 5 миллионов» —
    второе уже неправда, и в материалах дела это недопустимо.

    Мелкие числа (до 3) пропускаются: это нумерация пунктов и порядковые
    слова, а не факты.
    """
    known = _numbers_in(facts)
    invented = []
    # Даты убираем до разбора: их модель законно переписывает в другом
    # формате, и это не выдумка, а то же самое значение.
    without_dates = _DATE.sub(" ", text or "")
    for match in _NUMBER.findall(without_dates):
        number = _normalise_number(match)
        if not number or number in known:
            continue
        try:
            if abs(float(number)) <= 3:
                continue
        except ValueError:
            continue
        invented.append(match.strip())
    return invented


def build_conclusion(
    analysis_result: Dict[str, Any],
    provider: Any,
    anonymizer: Any = None,
    corpus_dir: Optional[str] = None,
) -> Conclusion:
    """Собрать заключение по готовому анализу.

    `provider` — объект с `run(system, messages, tools)`. Инструменты не
    передаются: здесь модель не запрашивает данные, а излагает уже собранные.
    """
    if provider is None:
        return Conclusion(error="языковая модель недоступна — заключение не составлено")

    facts = collect_facts(analysis_result, anonymizer=anonymizer)
    import json

    message = (
        "Составь заключение по этим фактам.\n\n"
        + json.dumps(facts, ensure_ascii=False, indent=2)
    )

    try:
        response = provider.run(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
            tools=None,
        )
    except Exception as exc:
        logger.warning("Заключение не составлено: %s", exc)
        return Conclusion(error=f"модель недоступна: {exc}")

    blocks = response.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    if not text:
        return Conclusion(
            provider=response.get("provider"),
            error="модель вернула пустой ответ",
        )

    conclusion = Conclusion(
        text=text,
        provider=response.get("provider"),
        truncated=response.get("stop_reason") == "length",
    )
    conclusion.invented_numbers = find_invented_numbers(text, facts)

    if conclusion.truncated:
        logger.warning("Заключение оборвано на потолке длины: %s символов", len(text))

    try:
        from app.services.legal import parse_reference

        conclusion.citations = parse_reference(text, corpus_dir=corpus_dir)
    except Exception as exc:
        logger.warning("Ссылки в заключении не сверены: %s", exc)

    if conclusion.invented_numbers:
        logger.warning(
            "В заключении числа, которых нет в фактах: %s",
            ", ".join(conclusion.invented_numbers[:5]),
        )
    return conclusion
