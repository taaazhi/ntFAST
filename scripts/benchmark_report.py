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


def render(env: Dict[str, Any], latency: Section, accuracy: Section, engine: Section, count: int) -> str:
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
        " (±0.01). It is **fully correct** when that transaction's description also contains the"
        " original description. *Spurious* counts parsed rows that match nothing in the ground truth.",
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
        "What remains is not a bug but the shape of the approach: every layout above is one this"
        " repository generates itself, and every bank-specific parser encodes a layout someone read"
        " by hand. A statement from a bank with no parser, or an existing bank changing its export,"
        " falls back to the generic path and recovers only what a generic layout exposes —"
        " date, amount and description, without the counterparty and merchant metadata the"
        " detection modules depend on. The gap between the two engine rows above is exactly that"
        " cost. Closing it by hand means writing another parser per bank per format.",
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


def print_console(env: Dict[str, Any], latency: Section, accuracy: Section, engine: Section) -> None:
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
            f"  {label:<22} median {data['stats']['median']:.2f}s · composite {data['composite']} "
            f"({data['level']}) · {data['red_flags']} red flags"
        )

    print("\n=== Extraction accuracy ===")
    for label, data in accuracy.items():
        print(
            f"  {label:<22} recovered {data['recovered']}/{data['expected']} "
            f"({data['row_accuracy']:.1f}%) · fully correct {data['full_accuracy']:.1f}% "
            f"· spurious {data['spurious']}"
        )
    print()
