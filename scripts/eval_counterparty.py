"""Оценка классификации контрагентов на размеченном наборе.

Зачем это отдельно от бенчмарка. `benchmark.py` меряет пропускную способность
и полноту извлечения: сколько строк восстановлено, сколько полей заполнено.
Он не отвечает на вопрос, *правильно* ли заполнено. Отличить магазин от банка,
а бренд от ИП с фамилией внутри — задача с эталоном, и меряется она иначе:
точностью и полнотой по каждому классу.

Набор (`backend/tests/data/counterparty_eval.json`) собран из настоящих
выписок, поэтому содержит то, чего синтетика не даёт: слипшийся текст из PDF,
казахскую schwa латиницей, одну операцию на трёх языках, каналы пополнения в
поле контрагента. Персональных данных в нём нет — ФИО внутри названий ИП
заменены на вымышленные с сохранением формы записи.

Без этой шкалы любое утверждение «модель лучше правил» остаётся заявлением.
Здесь оно становится числом, а разбивка по группам показывает не только
сколько ошибок, но и каких именно.

Запуск:
    python scripts/eval_counterparty.py            # правила, без сети
    python scripts/eval_counterparty.py --llm      # через AIManager из настроек
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

EVAL_PATH = REPO_ROOT / "backend" / "tests" / "data" / "counterparty_eval.json"

from app.services.enrichment.counterparty_classifier import (  # noqa: E402
    CounterpartyClassifier,
    classify_by_rule,
)


def load_cases(path: Path = EVAL_PATH) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)["cases"]


def classify_all(cases: Sequence[Dict[str, str]], use_llm: bool) -> List[str]:
    """Предсказания в том же порядке, что и кейсы."""
    names = [case["name"] for case in cases]

    if not use_llm:
        return [classify_by_rule(name).counterparty_type.value for name in names]

    from app.services.enrichment.pipeline import build_ai_manager

    ai_manager = build_ai_manager()
    if ai_manager is None:
        raise SystemExit(
            "Обогащение через модель выключено. Включите AI_ENRICHMENT_ENABLED "
            "и задайте CLAUDE_API_KEY в backend/.env, либо запустите без --llm."
        )

    # Размер батча под провайдера. Модель на 3B, получив 40 имён разом,
    # теряет часть записей или сбивается с нумерации — на первом прогоне так
    # пропал целый батч, треть покрытия. Облачной модели дробить незачем:
    # там каждый вызов стоит денег, а длинный список её не смущает.
    is_local = "ollama" in getattr(ai_manager, "__class__", type(ai_manager)).__module__.lower() or any(
        "ollama" in getattr(p, "provider_name", "").lower()
        for p in getattr(ai_manager, "providers", [])
    )
    batch_size = 12 if is_local else 40

    # Порог уверенности одинаков для любой модели, и это проверено заменой.
    # Локальная 3B ставит 0.1 там, где не знает ответа — на «YANDEX.GO» она
    # отвечает unknown с уверенностью 0.1, — и порог 0.4 такие ответы
    # отбрасывает, отдавая имя правилу, которое бренды знает на 13/13.
    # Снятие порога подняло покрытие модели с 43% до 65%, а точность
    # уронило с 89.0% до 76.8%: без фильтра модель перебивает правило там,
    # где сама сомневается.
    classifier = CounterpartyClassifier(
        ai_manager=ai_manager, batch_size=batch_size, min_confidence=0.4,
    )
    print(f"  размер батча: {batch_size}, порог уверенности: 0.4")
    mapping = asyncio.run(classifier.classify(names))
    print(f"  источники: {json.dumps(classifier.stats.as_dict(), ensure_ascii=False)}\n")
    return [
        mapping.get(name.strip(), classify_by_rule(name)).counterparty_type.value
        for name in names
    ]


def per_class_metrics(
    expected: Sequence[str], predicted: Sequence[str]
) -> Dict[str, Dict[str, float]]:
    """Точность, полнота и F1 по каждому классу.

    Одной доли верных ответов мало: набор несбалансирован, и классификатор,
    объявляющий всех подряд мерчантами, набрал бы приличную точность, потеряв
    при этом все госорганы и банки — то есть ровно те различия, ради которых
    модуль и существует.
    """
    labels = sorted(set(expected) | set(predicted))
    metrics: Dict[str, Dict[str, float]] = {}

    for label in labels:
        tp = sum(1 for e, p in zip(expected, predicted) if e == label and p == label)
        fp = sum(1 for e, p in zip(expected, predicted) if e != label and p == label)
        fn = sum(1 for e, p in zip(expected, predicted) if e == label and p != label)

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        metrics[label] = {
            "support": tp + fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return metrics


def group_accuracy(
    cases: Sequence[Dict[str, str]], predicted: Sequence[str]
) -> Dict[str, Tuple[int, int]]:
    """Доля верных по группам трудности: где именно ломается."""
    stats: Dict[str, List[int]] = defaultdict(lambda: [0, 0])
    for case, prediction in zip(cases, predicted):
        bucket = stats[case.get("group", "—")]
        bucket[1] += 1
        if prediction == case["expected"]:
            bucket[0] += 1
    return {group: (ok, total) for group, (ok, total) in stats.items()}


def print_report(
    cases: Sequence[Dict[str, str]], predicted: Sequence[str], show_errors: bool
) -> float:
    expected = [case["expected"] for case in cases]
    correct = sum(1 for e, p in zip(expected, predicted) if e == p)
    accuracy = 100.0 * correct / len(cases)

    print(f"=== Классификация контрагентов: {correct}/{len(cases)} ({accuracy:.1f}%) ===\n")

    metrics = per_class_metrics(expected, predicted)
    print(f"{'класс':<14}{'кейсов':>8}{'точность':>11}{'полнота':>10}{'F1':>8}")
    print("-" * 51)
    for label, values in metrics.items():
        print(
            f"{label:<14}{values['support']:>8}{values['precision']:>10.0%}"
            f"{values['recall']:>10.0%}{values['f1']:>8.2f}"
        )
    macro_f1 = sum(v["f1"] for v in metrics.values()) / len(metrics)
    print(f"\nмакро-F1: {macro_f1:.2f}\n")

    print(f"{'группа':<26}{'верно':>10}")
    print("-" * 36)
    for group, (ok, total) in sorted(
        group_accuracy(cases, predicted).items(), key=lambda kv: kv[1][0] / kv[1][1]
    ):
        print(f"{group:<26}{ok:>4}/{total:<4} {'✓' if ok == total else ''}")

    if show_errors:
        print("\n=== Ошибки ===")
        for case, prediction in zip(cases, predicted):
            if prediction != case["expected"]:
                print(
                    f"  {case['name'][:46]:<48} ждали {case['expected']:<11} "
                    f"получили {prediction}"
                )
    return accuracy


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", action="store_true", help="через AIManager вместо правил")
    parser.add_argument("--quiet", action="store_true", help="не печатать список ошибок")
    args = parser.parse_args(argv)

    cases = load_cases()
    print(f"Набор: {len(cases)} размеченных контрагентов из реальных выписок")
    print(f"Режим: {'LLM' if args.llm else 'правила (без сети)'}\n")

    predicted = classify_all(cases, use_llm=args.llm)
    print_report(cases, predicted, show_errors=not args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
