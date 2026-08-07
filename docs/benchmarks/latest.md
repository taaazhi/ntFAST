# ntFAST benchmark — latest run

Generated: 2026-08-07 14:34  ·  `python scripts/benchmark.py --runs 5 --transactions 500`

## Machine

| | |
|---|---|
| CPU | Intel64 Family 6 Model 158 Stepping 9, GenuineIntel (4 logical cores) |
| RAM | 7.9 GB |
| Python | 3.11.9 |
| OS | Windows 10 |
| Ollama reachable | no |

> The composite risk score is produced by rule-based and statistical modules only — `FraudEngine.full_analysis()` never calls the LLM. Ollama being up or down therefore does not move these timings. The LLM module (`nlp_analyzer.py`) is implemented but not wired into the scoring path.

## End-to-end latency — 500 transactions

File → bank detection → parsing → categorisation → analytics → fraud engine → risk score. One warm-up run is discarded.

| Input | Runs | Median | Min | Max | Std dev |
|---|---|---|---|---|---|
| Excel (.xlsx) | 5 | 0.11 s | 0.11 s | 0.16 s | 0.02 s |
| PDF — ruled table | 5 | 3.03 s | 2.98 s | 3.18 s | 0.07 s |

### Phase breakdown (median)

| Input | Parsing | Fraud engine | Composite score |
|---|---|---|---|
| Excel (.xlsx) | 0.06 s | 0.03 s | 1.6 (low) |
| PDF — ruled table | 2.98 s | 0.03 s | 1.6 (low) |

## Fraud engine in isolation

`GenericParser` recovers date, amount and description only — counterparty, merchant name and the salary/ATM/cash flags stay empty, and most detection modules need those to fire. The *enriched* row below feeds the engine transactions with that metadata filled in, which is what the bank-specific parsers (Kaspi, Halyk) produce. The gap in composite score is the point: engine output depends on parser richness, not just on transaction count.

| Input to the engine | Runs | Median | Composite score | Risk level | Red flags |
|---|---|---|---|---|---|
| parsed (generic, sparse) | 5 | 0.03 s | 1.6 | low | 0 |
| enriched (bank-parser fields) | 5 | 0.03 s | 70.0 | high | 38 |

## Extraction accuracy

A row is **recovered** when a parsed transaction has the same date and the same amount (±0.01). It is **fully correct** when that transaction's description also contains the original description. *Spurious* counts parsed rows that match nothing in the ground truth.

| Layout | Expected | Returned | Recovered | Fully correct | Spurious |
|---|---|---|---|---|---|
| Excel (.xlsx) | 500 | 500 | 500 (100.0%) | 500 (100.0%) | 0 |
| PDF — ruled table | 500 | 500 | 500 (100.0%) | 500 (100.0%) | 0 |
| PDF — multipage + headers | 500 | 500 | 500 (100.0%) | 500 (100.0%) | 0 |
| PDF — text, no table | 500 | 70 | 0 (0.0%) | 0 (0.0%) | 70 |

### Known limitation — PDFs without a ruled table

When a PDF carries no extractable table, `GenericParser` falls back to line-by-line text parsing (`parsers/generic.py:362`), and that path currently mis-reads the row: its amount regex matches the leading date, so `06.01.2025 … -26 341.94` is read as an amount of `6.01`. The fallback also runs only while fewer than 5 transactions have been collected, so it stops after the first page. Statements exported as flat text are therefore not supported today — the row above measures that rather than hiding it.

## Method and limits

- Input is generated from a seeded ground truth (500 transactions, `seed=42`) into a temporary directory; no real statement is ever read.
- Accuracy is therefore parser fidelity on **known, self-generated layouts**, not accuracy on real bank statements. Numbers on genuine Kaspi/Halyk exports are not measured here.
- Timings come from one machine (above) with no other load control; treat them as an order of magnitude, not a guarantee.
- Reproduce with `python scripts/benchmark.py`.
