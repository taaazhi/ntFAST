# ntFAST benchmark — latest run

Generated: 2026-08-18 13:38  ·  `python scripts/benchmark.py --runs 5 --transactions 500`

## Machine

| | |
|---|---|
| CPU | Intel64 Family 6 Model 158 Stepping 9, GenuineIntel (4 logical cores) |
| RAM | 7.9 GB |
| Python | 3.11.9 |
| OS | Windows 10 |
| Ollama reachable | yes |

> The composite risk score is produced by rule-based and statistical modules only — `FraudEngine.full_analysis()` never calls the LLM. Ollama being up or down therefore does not move these timings. The LLM module (`nlp_analyzer.py`) is implemented but not wired into the scoring path.

## End-to-end latency — 500 transactions

File → bank detection → parsing → categorisation → analytics → fraud engine → risk score. One warm-up run is discarded.

| Input | Runs | Median | Min | Max | Std dev |
|---|---|---|---|---|---|
| Excel (.xlsx) | 5 | 0.20 s | 0.19 s | 0.23 s | 0.02 s |
| PDF — ruled table | 5 | 3.28 s | 3.21 s | 3.43 s | 0.08 s |

### Phase breakdown (median)

| Input | Parsing | Fraud engine | Composite score |
|---|---|---|---|
| Excel (.xlsx) | 0.09 s | 0.03 s | 70.0 (high) |
| PDF — ruled table | 3.23 s | 0.03 s | 70.0 (high) |

## Fraud engine in isolation

`GenericParser` recovers date, amount and description only — counterparty, merchant name and the salary/ATM/cash flags stay empty, and most detection modules need those to fire. The *enriched* row below feeds the engine transactions with that metadata filled in, which is what the bank-specific parsers (Kaspi, Halyk) produce. The gap in composite score is the point: engine output depends on parser richness, not just on transaction count.

| Input to the engine | Runs | Median | Composite score | Risk level | Red flags |
|---|---|---|---|---|---|
| parsed (generic, sparse) | 5 | 0.03 s | 1.6 | low | 0 |
| enriched (bank-parser fields) | 5 | 0.05 s | 70.0 | high | 38 |
| unseen layout — kk | 5 | 0.05 s | 52.5 | medium | 38 |
| unseen layout — kk + обогащение | 5 | 0.05 s | 70.0 | high | 40 |
| unseen layout — ru | 5 | 0.06 s | 52.5 | medium | 37 |
| unseen layout — ru + обогащение | 5 | 0.05 s | 70.0 | high | 40 |

## Extraction accuracy

A row is **recovered** when a parsed transaction has the same date and the same amount (±0.01). It is **fully correct** when the original description also survives somewhere in the parsed row — any text field, or their concatenation, since a layout with separate *operation* and *counterparty* columns splits `Перевод Ержан О.` across two cells. *Spurious* counts parsed rows that match nothing in the ground truth.

The two *unseen* rows recover 100% of transactions but score 59% and 84% fully correct, and the reason is worth stating precisely: **the missing text is not on the page.** A salary shows up in those statements as operation `Пополнение` from counterparty `ТОО Астана Строй` — the word *Зарплата* appears nowhere in the file. In the Kazakh layout a further 61 rows say `Аударым`, which is `Перевод` in Kazakh. No parser recovers either: one needs inference, the other needs translation.

| Layout | Expected | Returned | Recovered | Fully correct | Spurious |
|---|---|---|---|---|---|
| Excel (.xlsx) | 500 | 500 | 500 (100.0%) | 500 (100.0%) | 0 |
| PDF — ruled table | 500 | 500 | 500 (100.0%) | 500 (100.0%) | 0 |
| PDF — multipage + headers | 500 | 500 | 500 (100.0%) | 500 (100.0%) | 0 |
| PDF — text, no table | 500 | 500 | 500 (100.0%) | 500 (100.0%) | 0 |
| Unseen bank — Kazakh | 500 | 500 | 500 (100.0%) | 284 (56.8%) | 0 |
| Незнакомый банк — нетиповые заголовки | 500 | 500 | 500 (100.0%) | 425 (85.0%) | 0 |
| Unseen bank — debit/credit columns | 500 | 500 | 500 (100.0%) | 425 (85.0%) | 0 |

## Field completeness

Recovering the date and the amount is not the same as producing something the detection modules can use. Structuring, the counterparty graph, merchant risk and profile mismatch key off *what the counterparty is* — a merchant, a private person, a bank — and off flags such as *salary* or *ATM*. **Classified** below is the share of rows whose counterparty type is not `unknown`; it is the column that matters, and it is the one the generic path cannot fill.

The *unseen* layouts are statements from a bank no parser was written for: different headers, different column order, one of them with no amount column at all — the value is split across debit and credit. Every field is present in the file, and after the multilingual header aliases the generic parser now recovers all of them.

| Input | Rows | Counterparty | Merchant | Classified | Flags |
|---|---|---|---|---|---|
| bank parser (Kaspi layout) | 500 | 100% | 67% | 100% | 10% |
| Unseen bank — Kazakh | 500 | 100% | 0% | 0% | 0% |
| Unseen bank — Kazakh + обогащение | 500 | 100% | 66% | 97% | 6% |
| Незнакомый банк — нетиповые заголовки | 500 | 100% | 0% | 0% | 0% |
| Незнакомый банк — нетиповые заголовки + обогащение | 500 | 100% | 66% | 97% | 6% |
| Unseen bank — debit/credit columns | 500 | 100% | 0% | 0% | 0% |
| Unseen bank — debit/credit columns + обогащение | 500 | 100% | 66% | 97% | 6% |

### Where the deterministic parser stops

PDFs without a ruled table used to score 0%: the amount regex matched the leading date, so `06.01.2025 … -26 341,94` was read as an amount of `6.01`, and the text fallback stopped after the first page. Both are fixed — the amount is now searched only after the date and only in money format, and the table-or-text decision is made per page. The row above measures the result.

Two column-mapping bugs are also fixed. Headers were matched against Russian words only, so a Kazakh statement (`Күні`, `Сомасы`, `Қалдық`) fell through to the text fallback, which then read the *balance* column as the amount and turned the period line into a transaction. And the mapping was tested with `if not mapping.get('date')` — index `0` is falsy, so a layout with the date in the first column, which is nearly all of them, was treated as unmapped and overwritten by guesswork.

### What actually drives the score

The engine rows above were first read as *the parser is too poor for the detectors*. An ablation says otherwise. Starting from the parsed unseen layout and copying in one field at a time from the enriched ground truth:

| Field copied in | Composite |
|---|---|
| nothing (as parsed) | 17.4 low |
| counterparty type + merchant name | 17.4 low |
| operation type | 17.8 low |
| **`is_salary`** | **63.0 high** |

One boolean accounts for the entire gap. Counterparty classification — the thing this section previously blamed — moves nothing at all. The reason is indirect: `AccountProfiler` types an account with no salary as UNKNOWN and one with salary as SALARY_EMPLOYEE, and the detectors carry different contextual weights per profile. A stream of P2P transfers is unremarkable on an account of unknown purpose and anomalous on a payroll card. That is how an investigator reads it too: the question is whether the flows match the declared source of income.

So the gap is closed by an enrichment step, not by a model. `is_salary` was previously set by searching for the word *зарплата* (`account_profiler.SALARY_KEYWORDS`, `halyk.py`), and real statements rarely contain it — a salary arrives as `Пополнение` from a `ТОО` and nothing more. `enrichment/salary_detector.py` infers it from behaviour instead: the same organisation, comparable amounts, roughly the same day of the month, several months running. Wording and language stop mattering. The *+ обогащение* rows above are that step, and they reach 63.0 HIGH with no model involved.

### Where a model would actually earn its place

Having measured it, the honest list is shorter and more specific than *the parser is weak*. Each item below is a hand-maintained list that has to grow per bank, per wording and per language:

1. **Channel descriptions that pose as counterparties.** Kaspi writes `С карты другого банка` in the counterparty field. Behaviourally it is indistinguishable from a salary — regular, comparable, same day — and it was classified as an employer until a stop-list was added. The list is in `salary_detector.GENERIC_SOURCES` and covers only the banks whose statements someone has held.
2. **The same document in three languages disagreeing.** Kaspi exports in Russian, Kazakh and English. `is_pension_benefit` fired 13 times on the Russian file and **zero** times on the other two, because the keyword lists were Russian-only — so the same pensioner's account read as a salaried employee depending on which file was uploaded. Fixed by extending the lists; the next bank will need it again.
3. **One counterparty, three spellings.** The same employer appears as `АО Финансовый центр`, `Қаражаттыңшотқатүсуі АОФинансовый центр` and `ReceipttotheaccountАО Финансовый центр` — PDF extraction welds words together differently per language. They become three separate nodes in the counterparty graph, which is where laundering schemes are supposed to become visible.

None of these is a layout problem, and none is solved by another regex. They are the measured case for the LLM step — and the baseline it has to beat is now the enriched rule-based run at 63.0, not the 17.4 it would have been flattering to quote.

## Method and limits

- Input is generated from a seeded ground truth (500 transactions, `seed=42`) into a temporary directory; no real statement is ever read.
- Accuracy is therefore parser fidelity on **known, self-generated layouts**, not accuracy on real bank statements. Numbers on genuine Kaspi/Halyk exports are not measured here.
- Timings come from one machine (above) with no other load control; treat them as an order of magnitude, not a guarantee.
- Reproduce with `python scripts/benchmark.py`.
