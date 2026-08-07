"""
ntFAST reproducible benchmark — end-to-end latency and extraction accuracy.

Every input file is generated from a seeded ground truth into a temporary directory,
so no real bank statement is ever read. Run `python scripts/benchmark.py --help`
for the options; rendering lives in `benchmark_report.py`.
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import re
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_report import environment, print_console, render  # noqa: E402
from app.services.bank_analyzer.analyzer import BankAnalyzer  # noqa: E402
from app.services.bank_analyzer.detector import BankDetector  # noqa: E402
from app.services.bank_analyzer.base_parser import (  # noqa: E402
    AccountInfo,
    CounterpartyType,
    Transaction,
    TransactionType,
)
from app.services.fraud.engine import FraudEngine  # noqa: E402

# The app logs every phase at INFO; keep the benchmark output readable.
logging.basicConfig(level=logging.ERROR)

HEADERS = ["Дата", "Описание", "Сумма", "Баланс"]


# ─────────────────────────── ground truth ───────────────────────────


@dataclass(frozen=True)
class Row:
    """One transaction as it is written into the file and expected back out."""

    date: datetime
    description: str
    amount: float

    @property
    def date_str(self) -> str:
        return self.date.strftime("%d.%m.%Y")

    @property
    def amount_str(self) -> str:
        return f"{self.amount:,.2f}".replace(",", " ")


# Merchant/counterparty pools. Deliberately free of the strings BankDetector
# keys on ("kaspi", "halyk", "p2p", "usdt", …) so the file is routed to
# GenericParser instead of a bank-specific one.
_SHOPS = ["Magnum Cash&Carry", "Small Market", "Aptechka 24", "Technodom", "Sulpak"]
_SERVICES = ["Yandex Go poezdka", "Оплата ЖКХ", "Интернет Beeline", "Мобильная связь"]
_PEOPLE = ["Ержан О.", "Маржан П.", "Асхат Т.", "Динара К.", "Нурлан Ж."]
_FIRMS = ["ТОО Астана Строй", "ТОО Глобал Инвест", "ИП Сериков", "ТОО Логистик Плюс"]


def build_ground_truth(count: int, seed: int = 42) -> List[Row]:
    """Deterministic synthetic statement with enough signal for the fraud engine."""
    rng = random.Random(seed)
    start = datetime(2025, 1, 5, 10, 0)
    rows: List[Row] = []
    day = 0

    while len(rows) < count:
        day += 1
        when = start + timedelta(days=day % 180)

        bucket = rng.random()
        if bucket < 0.08:  # salary
            rows.append(Row(when, f"Зарплата {rng.choice(_FIRMS)}", 520_000.0))
        elif bucket < 0.50:  # everyday spending
            rows.append(
                Row(when, rng.choice(_SHOPS), -round(rng.uniform(800, 12_000), 2))
            )
        elif bucket < 0.65:  # services
            rows.append(
                Row(when, rng.choice(_SERVICES), -round(rng.uniform(1_500, 35_000), 2))
            )
        elif bucket < 0.80:  # person-to-person movement
            direction = 1 if rng.random() < 0.5 else -1
            rows.append(
                Row(
                    when,
                    f"Перевод {rng.choice(_PEOPLE)}",
                    direction * round(rng.uniform(20_000, 400_000), 2),
                )
            )
        elif bucket < 0.88:  # round amounts
            rows.append(
                Row(when, f"Перевод {rng.choice(_FIRMS)}", -float(rng.choice([100_000, 200_000, 500_000])))
            )
        elif bucket < 0.94:  # amounts parked just under the 1M reporting threshold
            rows.append(Row(when, f"Перевод {rng.choice(_PEOPLE)}", -(950_000.0 + rng.randint(0, 40) * 1000)))
        else:  # night activity
            night = when.replace(hour=3)
            rows.append(Row(night, f"Ночной перевод {rng.choice(_PEOPLE)}", -round(rng.uniform(50_000, 800_000), 2)))

    return rows[:count]


def build_enriched(truth: Sequence[Row]) -> List[Transaction]:
    """
    The same statement as fully-populated Transaction objects — counterparty, merchant
    and flags included, the way the Kaspi/Halyk parsers produce them. GenericParser
    leaves those empty, and most detection modules go quiet without them.
    """
    enriched: List[Transaction] = []
    for row in truth:
        description = row.description
        counterparty = description.split(" ", 1)[-1] if " " in description else description
        is_salary = description.startswith("Зарплата")

        if is_salary:
            tx_type, cp_type = TransactionType.INCOME, CounterpartyType.MERCHANT
        elif description.startswith(("Перевод", "Ночной перевод")):
            tx_type = TransactionType.TRANSFER_IN if row.amount > 0 else TransactionType.TRANSFER_OUT
            cp_type = CounterpartyType.PERSON
        else:
            tx_type, cp_type = TransactionType.EXPENSE, CounterpartyType.MERCHANT
            counterparty = description

        enriched.append(
            Transaction(
                date=row.date,
                amount=row.amount,
                type=tx_type,
                description=description,
                counterparty=counterparty,
                counterparty_type=cp_type,
                merchant_name=counterparty if cp_type is CounterpartyType.MERCHANT else None,
                is_salary=is_salary,
            )
        )
    return enriched


# ─────────────────────────── file writers ───────────────────────────


def _register_cyrillic_font() -> str:
    """reportlab's built-in fonts are Latin-1 only; find a TTF that covers Cyrillic."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont("Bench", path))
            return "Bench"
    raise RuntimeError(
        "No Cyrillic-capable TTF found; install DejaVu Sans or run on a machine with Arial."
    )


def write_xlsx(rows: Sequence[Row], path: Path) -> None:
    import openpyxl

    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.title = "Выписка"
    sheet.append(["Выписка по счёту", "", "", ""])
    sheet.append(["Период", "05.01.2025 — 05.07.2025", "", ""])
    sheet.append([])
    sheet.append(HEADERS)

    balance = 1_000_000.0
    for row in rows:
        balance += row.amount
        sheet.append([row.date_str, row.description, row.amount, round(balance, 2)])

    wb.save(path)
    wb.close()


def _styled_table(rows: Sequence[Row], font: str):
    """Ruled table flowable — the ruling lines are what pdfplumber keys on."""
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    balance = 1_000_000.0
    data = [HEADERS]
    for row in rows:
        balance += row.amount
        data.append([row.date_str, row.description, row.amount_str, f"{balance:,.2f}".replace(",", " ")])

    table = Table(data, repeatRows=1, colWidths=[70, 200, 90, 90])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONT", (0, 0), (-1, -1), font, 7),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    return table


def write_pdf_table(rows: Sequence[Row], path: Path, font: str) -> None:
    """Clean, fully ruled table — the easy case."""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate

    doc = SimpleDocTemplate(str(path), pagesize=A4, topMargin=30, bottomMargin=30)
    doc.build([_styled_table(rows, font)])


def write_pdf_multipage(rows: Sequence[Row], path: Path, font: str) -> None:
    """Same data plus running headers and footers on every page."""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont(font, 8)
        canvas.drawString(40, A4[1] - 25, "Выписка по счёту KZ00 0000 0000 0000 0000")
        canvas.drawString(40, 20, f"Страница {doc.page} — сформировано автоматически")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, topMargin=45, bottomMargin=40)
    doc.build([_styled_table(rows, font)], onFirstPage=decorate, onLaterPages=decorate)


def write_pdf_text(rows: Sequence[Row], path: Path, font: str) -> None:
    """No table at all — plain lines, which forces the text fallback path."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdfcanvas

    canvas = pdfcanvas.Canvas(str(path), pagesize=A4)
    canvas.setFont(font, 8)
    y = A4[1] - 40
    for row in rows:
        canvas.drawString(40, y, f"{row.date_str}   {row.description}   {row.amount_str}")
        y -= 11
        if y < 40:
            canvas.showPage()
            canvas.setFont(font, 8)
            y = A4[1] - 40
    canvas.save()


# ─────────────────────────── measurement ───────────────────────────


def parse_only(path: Path) -> List[Transaction]:
    """Detection + parsing, mirroring BankAnalyzer.analyze() steps 1-3."""
    detection = BankDetector(str(path)).detect()
    parser_class = BankAnalyzer.PARSER_MAPPING.get(detection.bank_type)
    if parser_class is None:
        from app.services.bank_analyzer.parsers.generic import GenericParser

        parser_class = GenericParser
    parser = parser_class(str(path))
    parser.parse()
    return parser.get_transactions()


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().casefold()


def measure_accuracy(truth: Sequence[Row], parsed: Sequence[Transaction]) -> Dict[str, Any]:
    """
    A ground-truth row counts as *recovered* when some parsed transaction carries the
    same date and the same amount (±0.01). It counts as *fully correct* when that
    transaction's description also contains the original description — the text
    fallback prepends the date and amount to the line, so containment, not equality,
    is the fair test.
    """
    remaining: Dict[Tuple[str, float], List[Transaction]] = {}
    for tx in parsed:
        if tx.date is None:
            continue
        remaining.setdefault((tx.date.strftime("%d.%m.%Y"), round(tx.amount, 2)), []).append(tx)

    recovered = 0
    fully_correct = 0
    consumed = 0
    for row in truth:
        bucket = remaining.get((row.date_str, round(row.amount, 2)))
        if not bucket:
            continue

        # Several ground-truth rows can share a date and an amount. Prefer the candidate
        # whose description matches, otherwise the count would penalise the parser for a
        # collision the generator created.
        wanted = _norm(row.description)
        index = next((i for i, tx in enumerate(bucket) if wanted in _norm(tx.description)), None)
        tx = bucket.pop(index) if index is not None else bucket.pop()

        consumed += 1
        recovered += 1
        if wanted in _norm(tx.description):
            fully_correct += 1

    total = len(truth) or 1
    return {
        "expected": len(truth),
        "returned": len(parsed),
        "recovered": recovered,
        "fully_correct": fully_correct,
        "spurious": max(0, len(parsed) - consumed),
        "row_accuracy": 100.0 * recovered / total,
        "full_accuracy": 100.0 * fully_correct / total,
    }


def _stats(samples: Sequence[float]) -> Dict[str, float]:
    return {
        "median": statistics.median(samples),
        "min": min(samples),
        "max": max(samples),
        "stdev": statistics.stdev(samples) if len(samples) > 1 else 0.0,
    }


def measure_latency(path: Path, runs: int) -> Dict[str, Any]:
    """One warm-up run (discarded) then `runs` measured end-to-end runs."""
    BankAnalyzer(str(path)).analyze()

    totals: List[float] = []
    parses: List[float] = []
    frauds: List[float] = []
    composite = 0.0
    level = "n/a"

    for _ in range(runs):
        started = time.perf_counter()
        result = BankAnalyzer(str(path)).analyze()
        totals.append(time.perf_counter() - started)

        fraud = (result or {}).get("fraud_report") or {}
        composite = fraud.get("composite_score", composite)
        level = fraud.get("risk_level", level)

        started = time.perf_counter()
        transactions = parse_only(path)
        parses.append(time.perf_counter() - started)

        started = time.perf_counter()
        FraudEngine().full_analysis(transactions, AccountInfo(bank_name="Demo Bank", currency="KZT"))
        frauds.append(time.perf_counter() - started)

    return {
        "runs": runs,
        "end_to_end": _stats(totals),
        "parse": _stats(parses),
        "fraud": _stats(frauds),
        "composite": composite,
        "level": level,
    }


def measure_fraud(transactions: Sequence[Transaction], runs: int) -> Dict[str, Any]:
    """Fraud engine only, on transactions handed to it directly."""
    account = AccountInfo(bank_name="Demo Bank", currency="KZT")
    FraudEngine().full_analysis(list(transactions), account)

    samples: List[float] = []
    report = None
    for _ in range(runs):
        started = time.perf_counter()
        report = FraudEngine().full_analysis(list(transactions), account)
        samples.append(time.perf_counter() - started)

    return {
        "runs": runs,
        "stats": _stats(samples),
        "composite": getattr(report, "composite_score", 0.0),
        "level": getattr(report, "risk_level", "n/a"),
        "red_flags": len(getattr(report, "red_flags", []) or []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ntFAST latency and extraction-accuracy benchmark")
    parser.add_argument("--runs", type=int, default=5, help="measured runs per input (default: 5)")
    parser.add_argument("--transactions", type=int, default=500, help="statement size (default: 500)")
    parser.add_argument("--seed", type=int, default=42, help="ground-truth seed (default: 42)")
    parser.add_argument("--out", default="docs/benchmarks/latest.md", help="report path")
    args = parser.parse_args()

    truth = build_ground_truth(args.transactions, args.seed)
    font = _register_cyrillic_font()

    # ignore_cleanup_errors: openpyxl's read-only workbook in BankDetector keeps the
    # .xlsx handle open, which blocks directory removal on Windows.
    with tempfile.TemporaryDirectory(prefix="ntfast-bench-", ignore_cleanup_errors=True) as workdir:
        work = Path(workdir)
        xlsx = work / "statement.xlsx"
        pdf_table = work / "statement_table.pdf"
        pdf_pages = work / "statement_multipage.pdf"
        pdf_text = work / "statement_text.pdf"

        print(f"Generating {len(truth)} synthetic transactions in 4 layouts…")
        write_xlsx(truth, xlsx)
        write_pdf_table(truth, pdf_table, font)
        write_pdf_multipage(truth, pdf_pages, font)
        write_pdf_text(truth, pdf_text, font)

        print("Measuring extraction accuracy…")
        accuracy = {
            "Excel (.xlsx)": measure_accuracy(truth, parse_only(xlsx)),
            "PDF — ruled table": measure_accuracy(truth, parse_only(pdf_table)),
            "PDF — multipage + headers": measure_accuracy(truth, parse_only(pdf_pages)),
            "PDF — text, no table": measure_accuracy(truth, parse_only(pdf_text)),
        }

        print(f"Measuring latency ({args.runs} runs + warm-up per input)…")
        latency = {
            "Excel (.xlsx)": measure_latency(xlsx, args.runs),
            "PDF — ruled table": measure_latency(pdf_table, args.runs),
        }

        print("Measuring the fraud engine in isolation…")
        engine = {
            "parsed (generic, sparse)": measure_fraud(parse_only(xlsx), args.runs),
            "enriched (bank-parser fields)": measure_fraud(build_enriched(truth), args.runs),
        }

        env = environment()

    print_console(env, latency, accuracy, engine)

    out_path = REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(env, latency, accuracy, engine, args.transactions), encoding="utf-8")
    print(f"Report written to {out_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
