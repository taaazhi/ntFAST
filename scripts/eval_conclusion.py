"""Оценка заключений по делу на размеченном наборе.

Зачем это отдельно от `eval_counterparty.py`. Там задача с одним верным
ответом: контрагент — либо магазин, либо человек, и точность считается
сравнением с эталоном. Здесь верных ответов много: одно и то же дело можно
изложить разными словами, и требовать дословного совпадения бессмысленно.

Поэтому меряется не совпадение, а четыре свойства, каждое из которых
проверяемо без человека:

1. **Достоверность** — в тексте нет чисел, которых нет в фактах. Это ловит
   главную опасность: заключение, где сумма выглядит установленной, а взята
   из ниоткуда, вводит следствие в заблуждение убедительнее, чем отказ.
2. **Полнота** — сработавшие модули и ключевые числа названы. Заключение,
   умолчавшее о признаке, за который начислен балл, бесполезно: следователь
   не узнает, почему риск высокий.
3. **Сдержанность** — нет того, чего в фактах не было: чужой статьи, схемы,
   которую движок не находил, вывода о виновности.
4. **Состязательность** — если у признака есть контраргумент, он приведён.
   Документ, где изложена только версия обвинения, — не заключение.

Чего эта шкала не умеет. Совпадение проверяется по подстроке, а не по
смыслу: она поймает пропуск факта, но не отличит верное изложение от
правдоподобного пересказа. Для «модель А лучше модели Б» этого достаточно,
для «заключение готово к подписи» — нет, и так и должно быть: подписывает
следователь.

Запуск:
    python scripts/eval_conclusion.py                     # модель из настроек
    python scripts/eval_conclusion.py --model qwen2.5:7b  # сравнить другую
    python scripts/eval_conclusion.py --case pyramid      # одно дело
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

EVAL_PATH = REPO_ROOT / "backend" / "tests" / "data" / "conclusion_eval.json"

from app.services.agent.conclusion import build_conclusion, collect_facts  # noqa: E402

#: Обороты, которыми вводится довод против версии. Список намеренно широкий:
#: проверяется наличие состязательности, а не конкретная формулировка.
COUNTER_MARKERS = (
    "однако", "против", "может быть объяснен", "могут быть объяснен",
    "объясняется", "объяснение", "с другой стороны", "не исключено",
    "альтернатив", "в пользу", "вместе с тем", "при этом законн",
    "правомерн", "тем не менее", "но ", "хотя",
)

#: Разделители разрядов, которые модель расставляет по-своему. «1 440 000»,
#: «1440000» и «1,440,000» — одно и то же число, и сравнивать их надо после
#: приведения к общему виду.
_SEPARATORS = re.compile(r"[\s   ,]")


def load_cases(path: Path = EVAL_PATH) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)["cases"]


def _normalise(text: str) -> str:
    """Текст в нижнем регистре и без разделителей разрядов внутри чисел."""
    lowered = text.lower()
    # Разделители убираем только между цифрами: «ст. 218» не должно слипнуться
    # с соседним словом, а «1 440 000» обязано стать «1440000».
    return re.sub(r"(?<=\d)[\s   ,](?=\d)", "", lowered)


def _mentions(text: str, needle: str) -> bool:
    """Есть ли элемент в тексте — с поправкой на запись чисел."""
    lowered = text.lower()
    if needle.lower() in lowered:
        return True
    return _normalise(needle) in _normalise(text)


def evaluate_one(case: Dict[str, Any], provider: Any) -> Dict[str, Any]:
    """Одно дело: составить заключение и проверить его по разметке."""
    expect = case.get("expect") or {}
    started = time.perf_counter()
    conclusion = build_conclusion(case["analysis"], provider)
    elapsed = time.perf_counter() - started

    text = conclusion.text or ""
    result: Dict[str, Any] = {
        "id": case["id"],
        "seconds": round(elapsed, 1),
        "provider": conclusion.provider,
        "error": conclusion.error,
        "chars": len(text),
    }

    if not text:
        result.update({
            "produced": False, "no_invented": False, "clean_script": False,
            "coverage": 0.0, "missing": [], "no_forbidden": False,
            "counter_evidence": False, "citations_ok": False, "grounded": False,
            "passed": False,
        })
        return result

    # 1. Достоверность: числа из воздуха и чужая письменность.
    result["produced"] = True
    result["no_invented"] = not conclusion.invented_numbers
    result["invented"] = conclusion.invented_numbers[:5]
    result["clean_script"] = not conclusion.foreign_script

    # 2. Полнота: каждый обязательный элемент — список синонимов, засчитан
    #    при любом попадании.
    required: Sequence[Sequence[str]] = expect.get("must_include") or []
    missing = [
        variants[0] for variants in required
        if not any(_mentions(text, v) for v in variants)
    ]
    result["coverage"] = round((len(required) - len(missing)) / len(required), 3) if required else 1.0
    result["missing"] = missing

    # 3. Сдержанность: ничего сверх фактов.
    extra = [bad for bad in (expect.get("forbidden") or []) if _mentions(text, bad)]
    result["no_forbidden"] = not extra
    result["forbidden_found"] = extra

    # 4. Состязательность — только там, где в фактах есть контраргументы.
    if expect.get("needs_counter_evidence"):
        result["counter_evidence"] = any(m in text.lower() for m in COUNTER_MARKERS)
    else:
        result["counter_evidence"] = True

    # 5. Ссылки: непроверенная норма в заключении — брак независимо от того,
    #    просили её или нет.
    result["citations_ok"] = all(c.get("verified") for c in conclusion.citations)
    result["citations"] = [c.get("citation") for c in conclusion.citations]

    # 6. Заземление: процитировала ли модель только те нормы, текст которых ей
    #    дали в фактах, — или вспомнила статью «по памяти». Это строже, чем
    #    citations_ok: реальную статью можно назвать верно и при этом взять её
    #    не из поданного контекста. Пустой список цитат заземлён по определению.
    provided = {
        a.get("citation")
        for pattern in collect_facts(case["analysis"]).get("patterns", [])
        for a in pattern.get("articles", [])
        if a.get("citation")
    }
    cited = {c.get("citation") for c in conclusion.citations if c.get("citation")}
    ungrounded = sorted(cited - provided)
    result["grounded"] = not ungrounded
    result["ungrounded_citations"] = ungrounded

    result["passed"] = bool(
        result["no_invented"] and result["clean_script"] and result["no_forbidden"]
        and result["counter_evidence"] and result["citations_ok"]
        and result["coverage"] == 1.0
    )
    return result


def build_provider(model: Optional[str]) -> Any:
    """Провайдер из настроек либо Ollama с заданной моделью."""
    if model:
        from app.services.agent.ollama_provider import OllamaAgentProvider

        return OllamaAgentProvider(model=model)

    from app.services.agent import build_agent_provider

    provider = build_agent_provider()
    if provider is None:
        raise SystemExit(
            "Модель недоступна. Включите AI_ENRICHMENT_ENABLED=true и запустите "
            "Ollama (ollama pull qwen2.5:3b) либо задайте CLAUDE_API_KEY."
        )
    return provider


def report(rows: List[Dict[str, Any]], model_label: str) -> Dict[str, float]:
    total = len(rows)
    if not total:
        print("Набор пуст.")
        return {}

    def share(key: str) -> float:
        return sum(1 for r in rows if r.get(key)) / total

    print(f"\nЗаключения — {model_label}, дел: {total}\n")
    print(f"  {'дело':26} {'сек':>5}  {'полнота':>8}  что не так")
    print("  " + "-" * 74)
    for r in rows:
        problems = []
        if not r.get("produced"):
            problems.append(f"не составлено ({r.get('error')})")
        if r.get("missing"):
            problems.append("пропущено: " + ", ".join(r["missing"]))
        if r.get("invented"):
            problems.append("числа из воздуха: " + ", ".join(r["invented"]))
        if r.get("forbidden_found"):
            problems.append("лишнее: " + ", ".join(r["forbidden_found"]))
        if not r.get("counter_evidence"):
            problems.append("нет доводов против")
        if not r.get("citations_ok"):
            problems.append("непроверенная норма")
        if not r.get("clean_script"):
            problems.append("чужая письменность")
        mark = "OK" if r["passed"] else ""
        print(f"  {r['id']:26} {r['seconds']:5}  {r['coverage']:8.0%}  {mark}{'; '.join(problems)}")

    seconds = [r["seconds"] for r in rows]
    print("\n  Итого:")
    print(f"    заключение годно целиком   {share('passed'):.1%}")
    print(f"    без выдуманных чисел       {share('no_invented'):.1%}")
    print(f"    полнота (средняя)          {sum(r['coverage'] for r in rows) / total:.1%}")
    print(f"    ничего сверх фактов        {share('no_forbidden'):.1%}")
    print(f"    приведены доводы против    {share('counter_evidence'):.1%}")
    print(f"    все ссылки проверены       {share('citations_ok'):.1%}")
    print(f"    ссылки заземлены           {share('grounded'):.1%}")
    print(f"    время на дело              медиана {sorted(seconds)[len(seconds) // 2]:.0f} с, "
          f"всего {sum(seconds) / 60:.1f} мин")

    return {
        "passed": share("passed"),
        "no_invented": share("no_invented"),
        "no_forbidden": share("no_forbidden"),
        "counter_evidence": share("counter_evidence"),
        "citations_ok": share("citations_ok"),
        "grounded": share("grounded"),
        "coverage": sum(r["coverage"] for r in rows) / total,
    }


# Пороги проверяют регресс, а не абсолютное качество: числа заведомо ниже
# последних замеров, чтобы шум прогона не ронял гейт, но реальная просадка
# (например, модель начала выдумывать статьи закона) — ловилась.
def _gate(metrics: Dict[str, float], checks: List[tuple]) -> None:
    """checks: список (значение_порога, ключ_метрики, человекочитаемое имя).

    Порог None означает «не проверять». При непройденном пороге печатает
    причину и выходит с кодом 1 — так gated-прогон отличает регресс от нормы.
    """
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
    parser.add_argument("--case", help="прогнать одно дело по его id")
    parser.add_argument("--limit", type=int, help="ограничить число дел")
    parser.add_argument("--json", type=Path, help="куда сохранить подробный результат")
    parser.add_argument("--min-pass", type=float, metavar="ДОЛЯ",
                        help="0..1: гейт по «заключение годно целиком»; ниже — exit 1")
    parser.add_argument("--min-citations", type=float, metavar="ДОЛЯ",
                        help="0..1: гейт по «все ссылки проверены» — защита от выдуманных статей")
    parser.add_argument("--min-grounded", type=float, metavar="ДОЛЯ",
                        help="0..1: гейт по «ссылки заземлены» — цитата взята из поданного текста")
    args = parser.parse_args()

    cases = load_cases()
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            raise SystemExit(f"Дело '{args.case}' в наборе не найдено.")
    if args.limit:
        cases = cases[: args.limit]

    provider = build_provider(args.model)
    label = args.model or getattr(provider, "name", "модель из настроек")

    rows = []
    for index, case in enumerate(cases, 1):
        print(f"[{index}/{len(cases)}] {case['id']} …", flush=True)
        rows.append(evaluate_one(case, provider))

    metrics = report(rows, label)

    if args.json:
        args.json.write_text(
            json.dumps({"model": label, "cases": rows}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n  Подробности: {args.json}")

    # Гейт последним: JSON уже сохранён, поэтому даже при провале порога
    # подробности прогона остаются для разбора.
    _gate(metrics, [
        (args.min_pass, "passed", "заключение годно целиком"),
        (args.min_citations, "citations_ok", "все ссылки проверены"),
        (args.min_grounded, "grounded", "ссылки заземлены"),
    ])


if __name__ == "__main__":
    main()
