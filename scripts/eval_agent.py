"""Оценка следственного агента на размеченном наборе вопросов.

Чем это отличается от `eval_conclusion.py`. Там модель излагает готовые
факты, и проверять надо текст. Здесь она сама решает, где взять данные, —
и главная проверяемая способность не «красиво ответил», а **выбрал нужный
инструмент**. Агент, ответивший из головы, ошибётся даже когда угадает
число: в следующий раз данные будут другими, а привычка отвечать без
запроса останется.

Отсюда три метрики, и все три проверяются без человека:

1. **Инструмент** — вызван ли тот, которым этот вопрос решается.
2. **Ответ** — есть ли в нём верное значение. Эталон посчитан заранее:
   набор операций подобран так, что каждый ответ выводится арифметикой.
3. **Отказ** — на вопрос, данных для которого нет, ожидается признание
   нехватки. Способность сказать «не знаю» для следственной системы важнее
   красноречия: выдуманный ответ здесь дороже молчания.

Отказ распознаётся по оборотам речи — это огрубление, и оно уже один раз
ошиблось: verbatim верные «операций не было» и «предоставьте дополнительную
информацию» первая версия списка не распознала и записала в провалы. Список
пришлось расширять, и такой правке всегда нужна причина в самом ответе, а не
в желании поднять число.

Чего эта шкала не умеет: она не читает рассуждение. Агент, вызвавший
верный инструмент и переписавший число, неотличим от агента, который понял
вопрос. Для сравнения моделей и для поиска регрессий этого достаточно.

Запуск:
    python scripts/eval_agent.py
    python scripts/eval_agent.py --model qwen2.5:7b-instruct
    python scripts/eval_agent.py --case cash_operations
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

EVAL_PATH = REPO_ROOT / "backend" / "tests" / "data" / "agent_eval.json"

from app.services.agent import InvestigatorAgent  # noqa: E402
from app.services.agent.context_factory import from_db_transactions  # noqa: E402

#: Обороты, которыми признают нехватку данных. Список широкий намеренно:
#: проверяется сам факт отказа, а не формулировка.
REFUSAL_MARKERS = (
    "не найдено", "не обнаружен", "отсутству", "нет данных", "не содержится",
    "не могу", "нет операций", "не выявлено", "не указан", "нет сведений",
    "не располага", "неизвестн", "0 операц", "ни одной",
    # Добавлены после первого прогона: агент отказывал верно — «операций не
    # было», «предоставьте дополнительную информацию», — а шкала считала это
    # провалом. Измеритель ошибался, не модель.
    "не было", "предоставьте", "необходимо знать", "требуется дополнительн",
    "уточните", "нет информации",
)


class _Row:
    """Строка транзакции в том виде, в каком её отдаёт база."""

    def __init__(self, raw: Dict[str, Any]) -> None:
        self.transaction_date = datetime.strptime(raw["date"], "%Y-%m-%d")
        self.amount = float(raw["amount"])
        self.counterparty_name = raw["counterparty"]
        self.description = raw["counterparty"]
        self.counterparty_type = raw.get("type", "unknown")
        self.merchant_name = ""
        self.is_salary = bool(raw.get("is_salary"))
        self.is_cash_operation = bool(raw.get("is_cash"))


def load_set(path: Path = EVAL_PATH) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _normalise(text: str) -> str:
    """Убрать разделители разрядов, чтобы «2 520 000» и «2520000» совпали."""
    return re.sub(r"(?<=\d)[\s   ,](?=\d)", "", text.lower())


def _mentions(text: str, needle: str) -> bool:
    return needle.lower() in text.lower() or _normalise(needle) in _normalise(text)


def evaluate_one(case: Dict[str, Any], rows: List[_Row], provider: Any) -> Dict[str, Any]:
    context = from_db_transactions(rows, owner_name="Владелец Счётов")

    started = time.perf_counter()
    answer = InvestigatorAgent(provider).ask(case["question"], context)
    elapsed = time.perf_counter() - started

    text = answer.text or ""
    used = [call.get("tool") for call in answer.tool_calls]

    wanted = case.get("tools") or []
    # Достаточно одного из перечисленных: у части вопросов есть два законных
    # пути к ответу, и настаивать на конкретном значило бы штрафовать за
    # правильное решение.
    tool_ok = (not wanted) or any(tool in wanted for tool in used)

    missing = [
        variants[0] for variants in (case.get("must_include") or [])
        if not any(_mentions(text, v) for v in variants)
    ]
    extra = [bad for bad in (case.get("forbidden") or []) if _mentions(text, bad)]

    refusal_ok = True
    if case.get("expect_refusal"):
        refusal_ok = any(marker in text.lower() for marker in REFUSAL_MARKERS)

    return {
        "id": case["id"],
        "seconds": round(elapsed, 1),
        "tools_used": used,
        "tool_ok": tool_ok,
        "missing": missing,
        "answer_ok": not missing,
        "forbidden_found": extra,
        "refusal_ok": refusal_ok,
        "stopped_early": answer.stopped_early,
        "citations_ok": all(c.get("verified") for c in answer.citations),
        "passed": bool(tool_ok and not missing and not extra and refusal_ok
                       and all(c.get("verified") for c in answer.citations)),
        "text": text[:400],
    }


def build_provider(model: Optional[str]) -> Any:
    if model:
        from app.services.agent.ollama_provider import OllamaAgentProvider

        return OllamaAgentProvider(model=model)

    from app.services.agent import build_agent_provider

    provider = build_agent_provider()
    if provider is None:
        raise SystemExit(
            "Модель недоступна. Включите AI_ENRICHMENT_ENABLED=true и запустите "
            "Ollama либо задайте CLAUDE_API_KEY."
        )
    return provider


def report(rows: List[Dict[str, Any]], label: str) -> Dict[str, float]:
    total = len(rows)
    if not total:
        print("Набор пуст.")
        return {}

    def share(key: str) -> float:
        return sum(1 for r in rows if r.get(key)) / total

    print(f"\nАгент — {label}, вопросов: {total}\n")
    print(f"  {'вопрос':22} {'сек':>5}  инструменты / что не так")
    print("  " + "-" * 76)
    for r in rows:
        problems = []
        if not r["tool_ok"]:
            problems.append("не тот инструмент")
        if r["missing"]:
            problems.append("нет в ответе: " + ", ".join(r["missing"]))
        if r["forbidden_found"]:
            problems.append("выдумано: " + ", ".join(r["forbidden_found"]))
        if not r["refusal_ok"]:
            problems.append("не признал нехватку данных")
        if not r["citations_ok"]:
            problems.append("непроверенная норма")
        if r["stopped_early"]:
            problems.append("шаги кончились")
        mark = "OK  " if r["passed"] else ""
        tools = ", ".join(r["tools_used"]) or "—"
        print(f"  {r['id']:22} {r['seconds']:5}  {mark}{tools}"
              + (f" | {'; '.join(problems)}" if problems else ""))

    seconds = sorted(r["seconds"] for r in rows)
    print("\n  Итого:")
    print(f"    ответ верен целиком        {share('passed'):.1%}")
    print(f"    выбран нужный инструмент   {share('tool_ok'):.1%}")
    print(f"    верное значение в ответе   {share('answer_ok'):.1%}")
    print(f"    признал нехватку данных    {share('refusal_ok'):.1%}")
    print(f"    время на вопрос            медиана {seconds[len(seconds) // 2]:.0f} с, "
          f"всего {sum(seconds) / 60:.1f} мин")

    return {
        "passed": share("passed"),
        "tool_ok": share("tool_ok"),
        "answer_ok": share("answer_ok"),
        "refusal_ok": share("refusal_ok"),
    }


# Пороги ловят регресс, а не абсолют: значения ниже последних замеров, чтобы
# шум прогона не ронял гейт, но реальная просадка (модель стала врать в числах
# или брать не тот инструмент) — падала с ненулевым кодом.
def _gate(metrics: Dict[str, float], checks: List[tuple]) -> None:
    failures = []
    for threshold, key, human in checks:
        if threshold is None:
            continue
        value = metrics.get(key, 0.0)
        if value < threshold:
            failures.append(f"{human}: {value:.1%} < порога {threshold:.0%}")
    if failures:
        print("\n  ПОРОГ НЕ ПРОЙДЕН:")
        for line in failures:
            print(f"    - {line}")
        raise SystemExit(1)
    if any(t is not None for t, _, _ in checks):
        print("\n  Пороги пройдены.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="модель Ollama (по умолчанию — из настроек)")
    parser.add_argument("--case", help="один вопрос по его id")
    parser.add_argument("--json", type=Path, help="куда сохранить подробности")
    parser.add_argument("--min-pass", type=float, metavar="ДОЛЯ",
                        help="0..1: гейт по «ответ верен целиком»; ниже — exit 1")
    parser.add_argument("--min-answer", type=float, metavar="ДОЛЯ",
                        help="0..1: гейт по «верное значение в ответе» — защита от вранья в числах")
    args = parser.parse_args()

    data = load_set()
    rows = [_Row(raw) for raw in data["transactions"]]
    questions = data["questions"]
    if args.case:
        questions = [q for q in questions if q["id"] == args.case]
        if not questions:
            raise SystemExit(f"Вопрос '{args.case}' в наборе не найден.")

    provider = build_provider(args.model)
    label = args.model or getattr(provider, "name", "модель из настроек")

    results = []
    for index, case in enumerate(questions, 1):
        print(f"[{index}/{len(questions)}] {case['id']} …", flush=True)
        results.append(evaluate_one(case, rows, provider))

    metrics = report(results, label)

    if args.json:
        args.json.write_text(
            json.dumps({"model": label, "cases": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n  Подробности: {args.json}")

    # Гейт последним, чтобы JSON сохранился даже при провале порога.
    _gate(metrics, [
        (args.min_pass, "passed", "ответ верен целиком"),
        (args.min_answer, "answer_ok", "верное значение в ответе"),
    ])


if __name__ == "__main__":
    main()
