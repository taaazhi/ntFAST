"""Засев read-only demo-стенда: один общий гостевой аккаунт и несколько
предзагруженных синтетических анализов.

Зачем скрипт, а не ручная загрузка: стенд поднимается на пустой базе
(Railway), и анализы нужно получить одним воспроизводимым прогоном — через
тот же путь, что и настоящая загрузка (BankAnalyzer.analyze →
save_analysis_to_db), чтобы форма данных совпадала с боевой до байта.

LLM на стенде нет (нет GPU/Ollama), поэтому заключение агента
предзаписывается: короткий честный вывод из фактов антифрод-движка, без
обращения к модели. Гость видит готовый отчёт со всеми вкладками, но менять
ничего не может — аккаунт в DEMO_READONLY_EMAILS (см. ensure_writable).

Файлы синтетические и закоммичены в репозиторий; реальных ПД в них нет.

Запуск локально или против Railway (Postgres):
    DATABASE_URL=<postgres url> python scripts/seed_demo.py
    python scripts/seed_demo.py --force   # пересоздать анализы демо-юзера
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User
from app.models.analysis import Analysis
from app.services.bank_analyzer.analyzer import BankAnalyzer
from app.services.analysis_persistence import save_analysis_to_db

DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@ntfast.kz")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "ntFASTdemo!2026")
DEMO_NAME = "Демо-стенд ntFAST"

# Синтетические выписки из репозитория: чистый профиль, мошеннический и CSV.
SAMPLES = [
    ROOT / "docs" / "subject_clean.xlsx",
    ROOT / "docs" / "subject_fraudster.xlsx",
    ROOT / "test_data" / "sample_bank_statement.csv",
]

_LEVEL_RU = {"low": "низкий", "medium": "средний", "high": "высокий", "critical": "критический"}


def _demo_conclusion(result: dict) -> str:
    """Честный вывод из фактов движка — без обращения к модели."""
    fraud = result.get("fraud_report") or {}
    summary = result.get("summary") or {}
    level = _LEVEL_RU.get(fraud.get("risk_level"), fraud.get("risk_level") or "—")
    score = fraud.get("composite_score")
    n = summary.get("total_transactions", 0)
    head = f"Демо-заключение. Проанализировано {n} транзакций, уровень риска — {level}"
    if isinstance(score, (int, float)):
        head += f" ({score:.1f}/100)"
    head += (". Это витринный стенд: заключение предзаписано из фактов антифрод-движка, "
             "языковая модель на демо не вызывается. На рабочей установке связный вывод "
             "пишет агент-следователь по тем же фактам — с проверкой чисел и ссылок на НПА РК.")
    return head


def get_or_create_demo_user(db) -> User:
    user = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if user:
        return user
    user = User(
        email=DEMO_EMAIL,
        password_hash=get_password_hash(DEMO_PASSWORD),
        full_name=DEMO_NAME,
        role="analyst",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"  создан demo-пользователь {DEMO_EMAIL}")
    return user


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="удалить прежние demo-анализы и пересоздать")
    args = parser.parse_args()

    missing = [str(p) for p in SAMPLES if not p.exists()]
    if missing:
        raise SystemExit("Нет синтетических файлов: " + ", ".join(missing))

    db = SessionLocal()
    try:
        user = get_or_create_demo_user(db)
        existing = db.query(Analysis).filter(Analysis.analyst_id == user.id).all()
        if existing and not args.force:
            print(f"  у demo уже {len(existing)} анализов — пропускаю (--force чтобы пересоздать)")
            return
        if existing and args.force:
            for a in existing:
                db.delete(a)
            db.commit()
            print(f"  удалено прежних анализов: {len(existing)}")

        for path in SAMPLES:
            print(f"  анализ {path.name} …", flush=True)
            result = BankAnalyzer(str(path)).analyze()
            aid = save_analysis_to_db(
                db, result, path.name, path.suffix.lstrip(".").lower(),
                path.stat().st_size, user_id=user.id,
            )
            if not aid:
                raise SystemExit(f"save_analysis_to_db вернул None для {path.name}")
            analysis = db.query(Analysis).filter(Analysis.id == aid).first()
            analysis.ai_narrative = _demo_conclusion(result)
            analysis.ai_provider = "demo (предзапись)"
            db.commit()
            fraud = result.get("fraud_report") or {}
            print(f"    id={aid}  риск={fraud.get('risk_level', '—')}  "
                  f"score={fraud.get('composite_score', '—')}  "
                  f"статус={analysis.status}")
        print("Готово. Demo-стенд засеян.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
