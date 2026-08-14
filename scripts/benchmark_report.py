"""
Rendering for `scripts/benchmark.py` — turns the measurement dictionaries into the
console summary and the Markdown report. Kept separate so the benchmark file stays
about measuring, not formatting.
"""
from __future__ import annotations

import os
import platform
import sys
from datetime import datetime
from typing import Any, Dict, Optional

Section = Dict[str, Dict[str, Any]]
OLLAMA_URL = "http://localhost:11434/api/tags"


def _s(value: float) -> str:
    return f"{value:.2f}"


# ─────────────────────────── machine description ───────────────────────────


def _total_ram_gb() -> Optional[float]:
    try:
        import psutil  # type: ignore

        return psutil.virtual_memory().total / 1024 ** 3
    except Exception:
        pass

    if sys.platform == "win32":
        import ctypes

        kilobytes = ctypes.c_ulonglong(0)
        if ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(kilobytes)):
            return kilobytes.value / 1024 ** 2
        return None

    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024 ** 2
    except OSError:
        pass
    return None


def _ollama_reachable() -> bool:
    try:
        import httpx

        return httpx.get(OLLAMA_URL, timeout=2.0).status_code == 200
    except Exception:
        return False


def environment() -> Dict[str, Any]:
    """CPU/RAM/Python/OS plus whether a local Ollama answers — reported verbatim."""
    ram = _total_ram_gb()
    return {
        "cpu": platform.processor() or platform.machine(),
        "cores": os.cpu_count(),
        "ram_gb": f"{ram:.1f}" if ram else "unknown",
        "python": platform.python_version(),
        "os": f"{platform.system()} {platform.release()}",
        "ollama": _ollama_reachable(),
    }


def render(env: Dict[str, Any], latency: Section, accuracy: Section, engine: Section,
           count: int, completeness: Section | None = None) -> str:
    """Full Markdown report written to docs/benchmarks/latest.md."""
    runs = next(iter(latency.values()))["runs"]
    lines = [
        "# ntFAST benchmark — latest run",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  ·  "
        f"`python scripts/benchmark.py --runs {runs} --transactions {count}`",
        "",
        "## Machine",
        "",
        "| | |",
        "|---|---|",
        f"| CPU | {env['cpu']} ({env['cores']} logical cores) |",
        f"| RAM | {env['ram_gb']} GB |",
        f"| Python | {env['python']} |",
        f"| OS | {env['os']} |",
        f"| Ollama reachable | {'yes' if env['ollama'] else 'no'} |",
        "",
        "> The composite risk score is produced by rule-based and statistical modules only —"
        " `FraudEngine.full_analysis()` never calls the LLM. Ollama being up or down therefore"
        " does not move these timings. The LLM module (`nlp_analyzer.py`) is implemented but not"
        " wired into the scoring path.",
        "",
        f"## End-to-end latency — {count} transactions",
        "",
        "File → bank detection → parsing → categorisation → analytics → fraud engine → risk score."
        " One warm-up run is discarded.",
        "",
        "| Input | Runs | Median | Min | Max | Std dev |",
        "|---|---|---|---|---|---|",
    ]
    for label, data in latency.items():
        stats = data["end_to_end"]
        lines.append(
            f"| {label} | {data['runs']} | {_s(stats['median'])} s | {_s(stats['min'])} s | "
            f"{_s(stats['max'])} s | {_s(stats['stdev'])} s |"
        )

    lines += [
        "",
        "### Phase breakdown (median)",
        "",
        "| Input | Parsing | Fraud engine | Composite score |",
        "|---|---|---|---|",
    ]
    for label, data in latency.items():
        lines.append(
            f"| {label} | {_s(data['parse']['median'])} s | {_s(data['fraud']['median'])} s | "
            f"{data['composite']} ({data['level']}) |"
        )

    lines += [
        "",
        "## Fraud engine in isolation",
        "",
        "`GenericParser` recovers date, amount and description only — counterparty, merchant name"
        " and the salary/ATM/cash flags stay empty, and most detection modules need those to fire."
        " The *enriched* row below feeds the engine transactions with that metadata filled in, which"
        " is what the bank-specific parsers (Kaspi, Halyk) produce. The gap in composite score is the"
        " point: engine output depends on parser richness, not just on transaction count.",
        "",
        "| Input to the engine | Runs | Median | Composite score | Risk level | Red flags |",
        "|---|---|---|---|---|---|",
    ]
    for label, data in engine.items():
        lines.append(
            f"| {label} | {data['runs']} | {_s(data['stats']['median'])} s | {data['composite']} | "
            f"{data['level']} | {data['red_flags']} |"
        )

    lines += [
        "",
        "## Extraction accuracy",
        "",
        "A row is **recovered** when a parsed transaction has the same date and the same amount"
        " (±0.01). It is **fully correct** when the original description also survives somewhere"
        " in the parsed row — any text field, or their concatenation, since a layout with"
        " separate *operation* and *counterparty* columns splits `Перевод Ержан О.` across two"
        " cells. *Spurious* counts parsed rows that match nothing in the ground truth.",
        "",
        "The two *unseen* rows recover 100% of transactions but score 59% and 84% fully correct,"
        " and the reason is worth stating precisely: **the missing text is not on the page.**"
        " A salary shows up in those statements as operation `Пополнение` from counterparty"
        " `ТОО Астана Строй` — the word *Зарплата* appears nowhere in the file. In the Kazakh"
        " layout a further 61 rows say `Аударым`, which is `Перевод` in Kazakh. No parser"
        " recovers either: one needs inference, the other needs translation.",
        "",
        "| Layout | Expected | Returned | Recovered | Fully correct | Spurious |",
        "|---|---|---|---|---|---|",
    ]
    for label, data in accuracy.items():
        lines.append(
            f"| {label} | {data['expected']} | {data['returned']} | "
            f"{data['recovered']} ({data['row_accuracy']:.1f}%) | "
            f"{data['fully_correct']} ({data['full_accuracy']:.1f}%) | {data['spurious']} |"
        )

    if completeness:
        lines += [
            "",
            "## Field completeness",
            "",
            "Recovering the date and the amount is not the same as producing something the"
            " detection modules can use. Structuring, the counterparty graph, merchant risk and"
            " profile mismatch key off *what the counterparty is* — a merchant, a private"
            " person, a bank — and off flags such as *salary* or *ATM*. **Classified** below is"
            " the share of rows whose counterparty type is not `unknown`; it is the column that"
            " matters, and it is the one the generic path cannot fill.",
            "",
            "The *unseen* layouts are statements from a bank no parser was written for:"
            " different headers, different column order, one of them with no amount column at"
            " all — the value is split across debit and credit. Every field is present in the"
            " file, and after the multilingual header aliases the generic parser now recovers"
            " all of them.",
            "",
            "| Input | Rows | Counterparty | Merchant | Classified | Flags |",
            "|---|---|---|---|---|---|",
        ]
        for label, data in completeness.items():
            lines.append(
                f"| {label} | {data['rows']} | {data['counterparty_pct']:.0f}% | "
                f"{data['merchant_pct']:.0f}% | {data['classified_pct']:.0f}% | "
                f"{data['flagged_pct']:.0f}% |"
            )

    lines += [
        "",
        "### Where the deterministic parser stops",
        "",
        "PDFs without a ruled table used to score 0%: the amount regex matched the leading date, so"
        " `06.01.2025 … -26 341,94` was read as an amount of `6.01`, and the text fallback stopped"
        " after the first page. Both are fixed — the amount is now searched only after the date and"
        " only in money format, and the table-or-text decision is made per page. The row above"
        " measures the result.",
        "",
        "Two column-mapping bugs are also fixed. Headers were matched against Russian words only,"
        " so a Kazakh statement (`Күні`, `Сомасы`, `Қалдық`) fell through to the text fallback,"
        " which then read the *balance* column as the amount and turned the period line into a"
        " transaction. And the mapping was tested with `if not mapping.get('date')` — index `0`"
        " is falsy, so a layout with the date in the first column, which is nearly all of them,"
        " was treated as unmapped and overwritten by guesswork.",
        "",
        "What remains is not a parsing bug, and this is the point of the section. On the unseen"
        " layouts the generic parser now recovers **200/200 rows with 100% of counterparties** —"
        " every character is off the page. The composite score still comes out LOW (17.4) against"
        " HIGH (63.0) for the enriched input, because the string `Yandex Go poezdka` is extracted"
        " but not *understood*: `counterparty_type` stays `unknown` for every row, so merchant"
        " risk, the counterparty graph and profile mismatch have nothing to key off.",
        "",
        "That gap is not closable with better regexes, because the three things still missing are"
        " not text-extraction problems at all:",
        "",
        "1. **Classification.** `Yandex Go poezdka` is a merchant, `Ержан О.` is a private person."
        " Today this comes from hand-maintained merchant dictionaries inside the bank-specific"
        " parsers, which cover the banks someone wrote a parser for and no others.",
        "2. **Inference.** A monthly `Пополнение` from the same `ТОО` on the same day of the month"
        " is a salary. The statement never says so; `is_salary` has to be concluded.",
        "3. **Language.** `Аударым`, `Зат сатып алу`, `Толықтыру` mean transfer, purchase, top-up."
        " Kazakh is a state language of Kazakhstan and appears on real statements, so this is not"
        " an edge case. Today it is handled by an alias table that someone has to extend by hand"
        " for every bank and every wording.",
        "",
        "All three are exactly what a language model does without being told the layout in advance."
        " This is the measured case for the LLM extraction step, and the numbers to beat are"
        " **classified 0% → 100%** and **composite 17.4 → 63.0**, at a stated cost and latency"
        " per statement.",
        "",
        "## Method and limits",
        "",
        f"- Input is generated from a seeded ground truth ({count} transactions, `seed=42`) into a"
        " temporary directory; no real statement is ever read.",
        "- Accuracy is therefore parser fidelity on **known, self-generated layouts**, not accuracy"
        " on real bank statements. Numbers on genuine Kaspi/Halyk exports are not measured here.",
        "- Timings come from one machine (above) with no other load control; treat them as an order"
        " of magnitude, not a guarantee.",
        "- Reproduce with `python scripts/benchmark.py`.",
        "",
    ]
    return "\n".join(lines)


def print_console(env: Dict[str, Any], latency: Section, accuracy: Section, engine: Section,
                  completeness: Section | None = None) -> None:
    print("\n=== Machine ===")
    print(f"  CPU {env['cpu']} · {env['cores']} cores · {env['ram_gb']} GB RAM")
    print(f"  Python {env['python']} · {env['os']} · Ollama {'up' if env['ollama'] else 'down'}")

    print("\n=== End-to-end latency ===")
    for label, data in latency.items():
        stats = data["end_to_end"]
        print(
            f"  {label:<22} median {stats['median']:.2f}s  "
            f"(min {stats['min']:.2f} / max {stats['max']:.2f} / sd {stats['stdev']:.2f}) "
            f"over {data['runs']} runs"
        )
        print(
            f"  {'':<22} parse {data['parse']['median']:.2f}s · fraud {data['fraud']['median']:.2f}s "
            f"· composite {data['composite']} ({data['level']})"
        )

    print("\n=== Fraud engine in isolation ===")
    for label, data in engine.items():
        print(
            f"  {label:<30} median {data['stats']['median']:.2f}s · composite {data['composite']} "
            f"({data['level']}) · {data['red_flags']} red flags"
        )

    if completeness:
        print("\n=== Field completeness (what the detectors actually get) ===")
        print(f"  {'':<30} {'rows':>6} {'cparty':>8} {'merch':>7} {'class':>7} {'flags':>7}")
        for label, data in completeness.items():
            print(
                f"  {label:<30} {data['rows']:>6} {data['counterparty_pct']:>7.0f}% "
                f"{data['merchant_pct']:>6.0f}% {data['classified_pct']:>6.0f}% "
                f"{data['flagged_pct']:>6.0f}%"
            )

    print("\n=== Extraction accuracy ===")
    for label, data in accuracy.items():
        print(
            f"  {label:<22} recovered {data['recovered']}/{data['expected']} "
            f"({data['row_accuracy']:.1f}%) · fully correct {data['full_accuracy']:.1f}% "
            f"· spurious {data['spurious']}"
        )
    print()
