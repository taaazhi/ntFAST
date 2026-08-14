# ntFAST benchmark — latest run

Generated: 2026-08-15 03:05  ·  `python scripts/benchmark.py --runs 2 --transactions 200`

## Machine

| | |
|---|---|
| CPU | Intel64 Family 6 Model 158 Stepping 9, GenuineIntel (4 logical cores) |
| RAM | 7.9 GB |
| Python | 3.11.9 |
| OS | Windows 10 |
| Ollama reachable | no |

> The composite risk score is produced by rule-based and statistical modules only — `FraudEngine.full_analysis()` never calls the LLM. Ollama being up or down therefore does not move these timings. The LLM module (`nlp_analyzer.py`) is implemented but not wired into the scoring path.

## End-to-end latency — 200 transactions

File → bank detection → parsing → categorisation → analytics → fraud engine → risk score. One warm-up run is discarded.

| Input | Runs | Median | Min | Max | Std dev |
|---|---|---|---|---|---|
| Excel (.xlsx) | 2 | 0.06 s | 0.06 s | 0.07 s | 0.00 s |
| PDF — ruled table | 2 | 1.66 s | 1.65 s | 1.67 s | 0.02 s |

### Phase breakdown (median)

| Input | Parsing | Fraud engine | Composite score |
|---|---|---|---|
| Excel (.xlsx) | 0.04 s | 0.01 s | 0.0 (low) |
| PDF — ruled table | 1.64 s | 0.01 s | 0.0 (low) |

## Fraud engine in isolation

`GenericParser` recovers date, amount and description only — counterparty, merchant name and the salary/ATM/cash flags stay empty, and most detection modules need those to fire. The *enriched* row below feeds the engine transactions with that metadata filled in, which is what the bank-specific parsers (Kaspi, Halyk) produce. The gap in composite score is the point: engine output depends on parser richness, not just on transaction count.

| Input to the engine | Runs | Median | Composite score | Risk level | Red flags |
|---|---|---|---|---|---|
| parsed (generic, sparse) | 2 | 0.01 s | 0.0 | low | 0 |
| enriched (bank-parser fields) | 2 | 0.01 s | 63.0 | high | 3 |

## Extraction accuracy

A row is **recovered** when a parsed transaction has the same date and the same amount (±0.01). It is **fully correct** when that transaction's description also contains the original description. *Spurious* counts parsed rows that match nothing in the ground truth.

| Layout | Expected | Returned | Recovered | Fully correct | Spurious |
|---|---|---|---|---|---|
| Excel (.xlsx) | 200 | 200 | 200 (100.0%) | 200 (100.0%) | 0 |
| PDF — ruled table | 200 | 200 | 200 (100.0%) | 200 (100.0%) | 0 |
| PDF — multipage + headers | 200 | 200 | 200 (100.0%) | 200 (100.0%) | 0 |
| PDF — text, no table | 200 | 200 | 200 (100.0%) | 200 (100.0%) | 0 |

### Where the deterministic parser stops

PDFs without a ruled table used to score 0%: the amount regex matched the leading date, so `06.01.2025 … -26 341,94` was read as an amount of `6.01`, and the text fallback stopped after the first page. Both are fixed — the amount is now searched only after the date and only in money format, and the table-or-text decision is made per page. The row above measures the result.

What remains is not a bug but the shape of the approach: every layout above is one this repository generates itself, and every bank-specific parser encodes a layout someone read by hand. A statement from a bank with no parser, or an existing bank changing its export, falls back to the generic path and recovers only what a generic layout exposes — date, amount and description, without the counterparty and merchant metadata the detection modules depend on. The gap between the two engine rows above is exactly that cost. Closing it by hand means writing another parser per bank per format.

## Method and limits

- Input is generated from a seeded ground truth (200 transactions, `seed=42`) into a temporary directory; no real statement is ever read.
- Accuracy is therefore parser fidelity on **known, self-generated layouts**, not accuracy on real bank statements. Numbers on genuine Kaspi/Halyk exports are not measured here.
- Timings come from one machine (above) with no other load control; treat them as an order of magnitude, not a guarantee.
- Reproduce with `python scripts/benchmark.py`.
