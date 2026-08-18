"""Eval поиска по НПА: находит ли лексический поиск нужную статью.

Зачем отдельно от eval заключения. Заключение проверяет, что модель не
выдумала норму. Но есть вопрос раньше: а находит ли система правильную статью
по запросу «своими словами», как его формулирует следователь или агент? Если
поиск не находит — модели нечего процитировать, и весь RAG бессмыслен. Здесь
это измеряется числом, а не на глаз.

Модель НЕ нужна: поиск детерминированный (лексический). Поэтому eval быстрый,
воспроизводимый и годится для CI — в отличие от eval'ов, которым нужна живая
языковая модель.

По умолчанию гоняется против коммитабельной фикстуры
(backend/tests/data/legal_corpus_fixture.jsonl, 15 целевых статей + дистракторы).
Против настоящего корпуса — `--corpus-dir data/legal`.

    python scripts/eval_retrieval.py
    python scripts/eval_retrieval.py --corpus-dir data/legal --k 5
    python scripts/eval_retrieval.py --min-hit 0.8 --min-mrr 0.7   # гейт: ниже — exit 1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.legal import corpus  # noqa: E402

DATA = ROOT / "backend" / "tests" / "data" / "retrieval_eval.json"
FIXTURE_DIR = ROOT / "backend" / "tests" / "data"


def load_queries() -> List[Dict]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    return data["queries"]


def evaluate_one(q: Dict, k: int, corpus_dir: str) -> Dict:
    expected = set(q["expected"])
    hits = corpus.search(q["query"], limit=k, corpus_dir=corpus_dir)
    ranked = [art.citation for art, _ in hits]
    found = [c for c in ranked if c in expected]

    # ранг первой релевантной (для MRR); 0 — не нашлось в top-k
    rr = 0.0
    for i, c in enumerate(ranked, 1):
        if c in expected:
            rr = 1.0 / i
            break

    relevant_in_topk = len(set(ranked) & expected)
    return {
        "id": q["id"],
        "lang": q.get("lang", "ru"),
        "hit": bool(found),
        "reciprocal_rank": rr,
        "precision_at_k": relevant_in_topk / k if k else 0.0,
        "recall_at_k": relevant_in_topk / len(expected) if expected else 0.0,
        "expected": sorted(expected),
        "got": ranked,
    }


def report(rows: List[Dict], k: int, label: str) -> Dict[str, float]:
    total = len(rows)
    if not total:
        print("Набор пуст.")
        return {}

    print(f"\nПоиск по НПА — {label}, запросов: {total}, k={k}\n")
    print(f"  {'запрос':22} {'hit':>4} {'1/rank':>7}  ожидалось -> нашлось")
    print("  " + "-" * 76)
    for r in rows:
        mark = "OK " if r["hit"] else "—  "
        got_head = ", ".join(r["got"][:3]) or "ничего"
        print(f"  {r['id']:22} {mark:>4} {r['reciprocal_rank']:7.2f}  "
              f"{', '.join(r['expected'])} -> {got_head}")

    metrics = {
        "hit_at_k": sum(r["hit"] for r in rows) / total,
        "mrr": sum(r["reciprocal_rank"] for r in rows) / total,
        "precision_at_k": sum(r["precision_at_k"] for r in rows) / total,
        "recall_at_k": sum(r["recall_at_k"] for r in rows) / total,
    }
    print("\n  Итого:")
    print(f"    hit@{k} (нашлась в top-{k})   {metrics['hit_at_k']:.1%}")
    print(f"    MRR (1/ранг первой)         {metrics['mrr']:.3f}")
    print(f"    precision@{k}               {metrics['precision_at_k']:.1%}")
    print(f"    recall@{k}                  {metrics['recall_at_k']:.1%}")

    # Разбивка по языку запроса: проект работает в Казахстане, и важно видеть
    # отдельно, что поиск находит норму и по русскому, и по казахскому запросу.
    langs = sorted({r["lang"] for r in rows})
    if len(langs) > 1:
        print("\n  По языку запроса:")
        for lang in langs:
            group = [r for r in rows if r["lang"] == lang]
            hit = sum(r["hit"] for r in group) / len(group)
            mrr = sum(r["reciprocal_rank"] for r in group) / len(group)
            print(f"    {lang}: hit@{k} {hit:.1%}, MRR {mrr:.3f}  ({len(group)} запр.)")
    return metrics


def _gate(metrics: Dict[str, float], min_hit, min_mrr) -> None:
    failures = []
    if min_hit is not None and metrics.get("hit_at_k", 0) < min_hit:
        failures.append(f"hit@k {metrics['hit_at_k']:.1%} < порога {min_hit:.0%}")
    if min_mrr is not None and metrics.get("mrr", 0) < min_mrr:
        failures.append(f"MRR {metrics['mrr']:.3f} < порога {min_mrr:.2f}")
    if failures:
        print("\n  ПОРОГ НЕ ПРОЙДЕН:")
        for line in failures:
            print(f"    - {line}")
        raise SystemExit(1)
    if min_hit is not None or min_mrr is not None:
        print("\n  Пороги пройдены.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", default=str(FIXTURE_DIR),
                        help="каталог с *.jsonl (по умолчанию — фикстура)")
    parser.add_argument("--k", type=int, default=5, help="глубина top-k")
    parser.add_argument("--json", type=Path, help="куда сохранить подробности")
    parser.add_argument("--min-hit", type=float, metavar="ДОЛЯ",
                        help="0..1: гейт по hit@k; ниже — exit 1")
    parser.add_argument("--min-mrr", type=float, metavar="ЗНАЧЕНИЕ",
                        help="0..1: гейт по MRR; ниже — exit 1")
    args = parser.parse_args()

    corpus.clear_cache()
    rows = [evaluate_one(q, args.k, args.corpus_dir) for q in load_queries()]
    label = "фикстура" if args.corpus_dir == str(FIXTURE_DIR) else args.corpus_dir
    metrics = report(rows, args.k, label)

    if args.json:
        args.json.write_text(json.dumps({"corpus": label, "k": args.k,
                             "metrics": metrics, "queries": rows},
                             ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  Подробности: {args.json}")

    _gate(metrics, args.min_hit, args.min_mrr)


if __name__ == "__main__":
    main()
