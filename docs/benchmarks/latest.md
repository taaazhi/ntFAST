# ntFAST benchmark — latest run

Generated: 2026-08-15 03:27  ·  `python scripts/benchmark.py --runs 3 --transactions 200`

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
| Excel (.xlsx) | 3 | 0.06 s | 0.06 s | 0.06 s | 0.00 s |
| PDF — ruled table | 3 | 1.58 s | 1.57 s | 1.60 s | 0.01 s |

### Phase breakdown (median)

| Input | Parsing | Fraud engine | Composite score |
|---|---|---|---|
| Excel (.xlsx) | 0.04 s | 0.01 s | 0.0 (low) |
| PDF — ruled table | 1.52 s | 0.01 s | 0.0 (low) |

## Fraud engine in isolation

`GenericParser` recovers date, amount and description only — counterparty, merchant name and the salary/ATM/cash flags stay empty, and most detection modules need those to fire. The *enriched* row below feeds the engine transactions with that metadata filled in, which is what the bank-specific parsers (Kaspi, Halyk) produce. The gap in composite score is the point: engine output depends on parser richness, not just on transaction count.

| Input to the engine | Runs | Median | Composite score | Risk level | Red flags |
|---|---|---|---|---|---|
| parsed (generic, sparse) | 3 | 0.01 s | 0.0 | low | 0 |
| enriched (bank-parser fields) | 3 | 0.01 s | 63.0 | high | 3 |
| unseen layout — kk | 3 | 0.01 s | 17.4 | low | 2 |
| unseen layout — ru | 3 | 0.01 s | 14.9 | low | 2 |

## Extraction accuracy

A row is **recovered** when a parsed transaction has the same date and the same amount (±0.01). It is **fully correct** when the original description also survives somewhere in the parsed row — any text field, or their concatenation, since a layout with separate *operation* and *counterparty* columns splits `Перевод Ержан О.` across two cells. *Spurious* counts parsed rows that match nothing in the ground truth.

The two *unseen* rows recover 100% of transactions but score 59% and 84% fully correct, and the reason is worth stating precisely: **the missing text is not on the page.** A salary shows up in those statements as operation `Пополнение` from counterparty `ТОО Астана Строй` — the word *Зарплата* appears nowhere in the file. In the Kazakh layout a further 61 rows say `Аударым`, which is `Перевод` in Kazakh. No parser recovers either: one needs inference, the other needs translation.

| Layout | Expected | Returned | Recovered | Fully correct | Spurious |
|---|---|---|---|---|---|
| Excel (.xlsx) | 200 | 200 | 200 (100.0%) | 200 (100.0%) | 0 |
| PDF — ruled table | 200 | 200 | 200 (100.0%) | 200 (100.0%) | 0 |
| PDF — multipage + headers | 200 | 200 | 200 (100.0%) | 200 (100.0%) | 0 |
| PDF — text, no table | 200 | 200 | 200 (100.0%) | 200 (100.0%) | 0 |
| Unseen bank — Kazakh | 200 | 200 | 200 (100.0%) | 118 (59.0%) | 0 |
| Unseen bank — debit/credit columns | 200 | 200 | 200 (100.0%) | 168 (84.0%) | 0 |

## Field completeness

Recovering the date and the amount is not the same as producing something the detection modules can use. Structuring, the counterparty graph, merchant risk and profile mismatch key off *what the counterparty is* — a merchant, a private person, a bank — and off flags such as *salary* or *ATM*. **Classified** below is the share of rows whose counterparty type is not `unknown`; it is the column that matters, and it is the one the generic path cannot fill.

The *unseen* layouts are statements from a bank no parser was written for: different headers, different column order, one of them with no amount column at all — the value is split across debit and credit. Every field is present in the file, and after the multilingual header aliases the generic parser now recovers all of them.

| Input | Rows | Counterparty | Merchant | Classified | Flags |
|---|---|---|---|---|---|
| bank parser (Kaspi layout) | 200 | 100% | 70% | 100% | 10% |
| Unseen bank — Kazakh | 200 | 100% | 0% | 0% | 0% |
| Unseen bank — debit/credit columns | 200 | 100% | 0% | 0% | 0% |

### Where the deterministic parser stops

PDFs without a ruled table used to score 0%: the amount regex matched the leading date, so `06.01.2025 … -26 341,94` was read as an amount of `6.01`, and the text fallback stopped after the first page. Both are fixed — the amount is now searched only after the date and only in money format, and the table-or-text decision is made per page. The row above measures the result.

Two column-mapping bugs are also fixed. Headers were matched against Russian words only, so a Kazakh statement (`Күні`, `Сомасы`, `Қалдық`) fell through to the text fallback, which then read the *balance* column as the amount and turned the period line into a transaction. And the mapping was tested with `if not mapping.get('date')` — index `0` is falsy, so a layout with the date in the first column, which is nearly all of them, was treated as unmapped and overwritten by guesswork.

What remains is not a parsing bug, and this is the point of the section. On the unseen layouts the generic parser now recovers **200/200 rows with 100% of counterparties** — every character is off the page. The composite score still comes out LOW (17.4) against HIGH (63.0) for the enriched input, because the string `Yandex Go poezdka` is extracted but not *understood*: `counterparty_type` stays `unknown` for every row, so merchant risk, the counterparty graph and profile mismatch have nothing to key off.

That gap is not closable with better regexes, because the three things still missing are not text-extraction problems at all:

1. **Classification.** `Yandex Go poezdka` is a merchant, `Ержан О.` is a private person. Today this comes from hand-maintained merchant dictionaries inside the bank-specific parsers, which cover the banks someone wrote a parser for and no others.
2. **Inference.** A monthly `Пополнение` from the same `ТОО` on the same day of the month is a salary. The statement never says so; `is_salary` has to be concluded.
3. **Language.** `Аударым`, `Зат сатып алу`, `Толықтыру` mean transfer, purchase, top-up. Kazakh is a state language of Kazakhstan and appears on real statements, so this is not an edge case. Today it is handled by an alias table that someone has to extend by hand for every bank and every wording.

All three are exactly what a language model does without being told the layout in advance. This is the measured case for the LLM extraction step, and the numbers to beat are **classified 0% → 100%** and **composite 17.4 → 63.0**, at a stated cost and latency per statement.

## Method and limits

- Input is generated from a seeded ground truth (200 transactions, `seed=42`) into a temporary directory; no real statement is ever read.
- Accuracy is therefore parser fidelity on **known, self-generated layouts**, not accuracy on real bank statements. Numbers on genuine Kaspi/Halyk exports are not measured here.
- Timings come from one machine (above) with no other load control; treat them as an order of magnitude, not a guarantee.
- Reproduce with `python scripts/benchmark.py`.
