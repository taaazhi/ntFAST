"""Собрать коммитабельную фикстуру-корпус для eval поиска по НПА.

Настоящий корпус (`data/legal/*.jsonl`) в репозиторий не кладётся — мегабайты
кодексов, поправки по нескольку раз в год. Но замерять качество поиска нужно
воспроизводимо и в CI. Отсюда фикстура: горстка НАСТОЯЩИХ статей (профильные
для антифрода + дистракторы), вырезанных из реального корпуса и закоммиченных.

Дистракторы обязательны: без них любой поиск «попадает», потому что искать не
из чего. Здесь их выбирают детерминированно (каждая N-я статья с фиксированным
шагом), чтобы фикстура не менялась от прогона к прогону.

Запуск (только там, где построен реальный корпус):
    python scripts/build_retrieval_fixture.py
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "data" / "legal"
OUT = ROOT / "backend" / "tests" / "data" / "legal_corpus_fixture.jsonl"

# Профильные статьи — целевые ответы eval. (код, номер).
RELEVANT = [
    ("УК РК", "189"), ("УК РК", "190"), ("УК РК", "214"), ("УК РК", "215"),
    ("УК РК", "217"), ("УК РК", "217-1"), ("УК РК", "218"), ("УК РК", "218-1"),
    ("УК РК", "231"), ("УК РК", "232"), ("УК РК", "232-1"), ("УК РК", "258"),
    ("ЗРК О ПОД/ФТ", "11-1"), ("ЗРК О ПОД/ФТ", "12"), ("ЗРК О ПОД/ФТ", "20"),
]

DISTRACTOR_STEP = 37  # каждая 37-я неотобранная статья — стабильный «шум»
DISTRACTOR_CAP = 40


def load_all() -> list[dict]:
    articles = []
    for f in sorted(glob.glob(str(CORPUS_DIR / "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if line:
                articles.append(json.loads(line))
    return articles


def main() -> None:
    if not CORPUS_DIR.exists():
        raise SystemExit(f"Нет {CORPUS_DIR}: сначала построй корпус (fetch_legal_corpus.py).")

    all_articles = load_all()
    by_key = {(a["code"], a["number"]): a for a in all_articles}

    picked, missing = [], []
    for key in RELEVANT:
        if key in by_key:
            picked.append(by_key[key])
        else:
            missing.append(key)
    if missing:
        raise SystemExit(f"В корпусе нет статей: {missing}")

    relevant_keys = set(RELEVANT)
    pool = [a for a in all_articles if (a["code"], a["number"]) not in relevant_keys]
    distractors = pool[::DISTRACTOR_STEP][:DISTRACTOR_CAP]

    fixture = picked + distractors
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as out:
        for a in fixture:
            # только поля, нужные корпусу; fetched_at выкидываем — шум в diff
            row = {k: a.get(k, "") for k in
                   ("code", "number", "title", "text", "url", "title_kk", "url_kk")}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Записано {len(fixture)} статей ({len(picked)} целевых + "
          f"{len(distractors)} дистракторов) → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
