# Forecast data audit

| Check | IBM TabFormer | MoneyData | Verdict |
|---|---:|---:|---|
| Raw rows audited | 24,386,900 | 6,567 | Full source scans |
| People in raw source | 2,000 simulated | 1 real | Limited research only |
| Qualifying positive outflow rows | 22,751,208 | 6,122 | Target semantics differ |
| Train / validation / test windows | 26,579 / 5,822 / 5,481 | 96 / 24 / 24 | Nonempty |
| Eligible people per split | 1,113 / 244 / 230 | 1 / 1 / 1 | IBM disjoint; MoneyData temporal case study |
| History / target tensor shape | N × 56 / N × 14 | N × 56 / N × 14 | Exact fixed length |
| Nonfinite / negative tensor values | 0 / 0 | 0 / 0 | Pass |
| Duplicate person + origin records across splits | 0 | 0 | Pass |
| Forecast start weekdays represented | All 7 in every split | All 7 in every split | Pass |
| All-zero histories, train / validation / test | 924 / 370 / 294 | 0 / 0 / 0 | IBM coverage caveat |
| Raw exact duplicate rows | 66 estimated by full-row 64-bit hashes | 0 exact | Retained |
| Preparation wall time | 85.41 seconds | 0.036 seconds | Local CPU |

The audit permits training for limited research. It does **not** permit a claim that either source establishes residual checking-account outflow accuracy or real-world generalization. Source targets are sums of recorded amounts: IBM records are simulated, MoneyData records are a real ledger from one person, and neither supplies verified discretionary/bill-excluded labels. The manual MoneyData category annotations and IBM fraud labels are not training inputs or filtering labels.

## Reproducible artifacts and contract

Run from the isolated worktree after acquisition and policy freeze:

```text
forecasting/.venv/bin/python -m forecasting.prepare --source ibm
forecasting/.venv/bin/python -m forecasting.prepare --source moneydata
forecasting/.venv/bin/python -m pytest forecasting/tests/test_prepare.py -q
```

`forecasting/evaluation.json` defines the experiment. The preparation program validates source size and SHA-256 against `forecasting/data/raw/{source}-source.json`, streams each source, leaves raw bytes untouched, and saves:

- `forecasting/data/processed/{source}_windows.npz`: `{split}_history` float64 `(N, 56)`, `{split}_y` float64 `(N, 14)`, `{split}_group` Unicode `(N,)`, `{split}_origin` int64 `(N,)`, and a scalar JSON `metadata` string. Splits are `train`, `validation`, and `test`. Amounts are major source monetary units; origins are first forecast dates expressed as days since 1970-01-01. Load with `allow_pickle=False`.
- `{source}_audit.json`: full per-day-head distributions, amount quantiles, shape/zero/duplicate checks, weekday counts, date boundaries, exclusions, and numeric eligibility counts.
- `{source}_manifest.json`: source/config/data/audit checksums, semantics, counts, and runtime. Data is locally retained and Git-ignored.

The policy SHA-256 used for both outputs is `b2750d890d8d81a1327d1820717ab194ebef9a4b96c5b29013da3fefdc519738`. The MoneyData currency was corrected from presumed GBP to `SOURCE_NATIVE` before any model training; the change occurred during IBM's raw scan and did not alter any IBM preparation setting. GBP is plausible from the UK account context, but not explicitly established by the downloaded source. No currency conversion was performed.

## IBM: synthetic card spending

The verified raw archive is `ibm-transactions.tgz`, SHA-256 `e9f589a0958f40d60f81b1a2e8428db86e00c05755caf44fb055827976c0efa2`. Its single CSV member is `card_transaction.v1.csv`. All 24,386,900 rows were inspected; this is not a sample. The observed date range is 1991-01-02 through 2020-02-28. CSV fields include `User`, `Card`, calendar date/time, `Amount`, merchant fields, `Errors?`, and `Is Fraud?`. Money is parsed to exact integer cents before daily aggregation and converted to float64 dollars only when windows are materialized.

All cards belonging to a `User` are pooled. The deterministic SHA-256 user split assigns 1,386 users to training, 317 to validation, and 297 to test before eligibility checks. Target years are respectively 2016, 2017, and 2018. An origin is January 1 plus a multiple of 15 days, with every 14-day target contained within its assigned year. A customer qualifies at an origin only if at least one successful positive charge was recorded on or before that origin's 56-day context start. This excludes 6,685 / 1,786 / 1,647 candidate windows. There is no requirement for a charge in the future or near the end of the window.

The positive-successful-charge target excludes 388,431 error rows and 1,264,896 nonpositive rows. Those sets overlap on 17,635 rows; the unique excluded count is 1,635,692. Nonpositive rows comprise 1,244,683 refunds/negative amounts and 20,213 zeros. The 27,376 positive successful charges marked fraudulent remain in the target; fraud annotations are never model features or eligibility criteria. Exact row duplicates are retained because the raw file lacks a unique transaction identifier that would prove repeated rows are duplicate events. The reported count of 66 comes from all-column 64-bit hashes over the entire source and has a theoretical hash-collision caveat.

Observation completeness is assumed from each customer's first qualifying transaction through the global dataset end. Missing dates become zero daily charges. That assumption may include closed accounts or missing records. Zero histories are therefore retained, not silently interpreted as errors or removed using future activity. Examples of the affected records are:

- Training: `104@2016-07-29`, `104@2016-08-13`, `104@2016-08-28`.
- Validation: `1112@2017-01-01`, `1112@2017-01-16`, `1112@2017-01-31`.
- Test: `1080@2018-08-14`, `1080@2018-08-29`, `1080@2018-09-13`.

Each split contains exactly one repeated history content pattern: the all-zero vector. The within-split duplicate-history excess counts are 923 / 369 / 293. Every split pair shares that one numeric vector but has zero shared customers and zero shared customer/origin records. This is disclosed numeric sameness, not evidence that the same customer record crossed a holdout boundary. Target dates are strictly ordered across splits.

Mean 14-day target totals are $2,021.18 / $1,835.04 / $1,786.62. Zero 14-day targets occur in 954 / 373 / 300 windows. The per-head zero-label rates range from 11.90–12.30%, 13.47–14.81%, and 13.45–14.67%, respectively. Full day-1 through day-14 counts and quantiles are recorded in the audit JSON. No head approaches an 80% zero-label majority.

These are synthetic **card purchase amounts**, not checking-account debits on payment settlement dates. They cannot be inserted into a checking-account cashflow solver without a separately validated card-payment accounting model. This package's adapter intentionally rejects `card_spending`.

## MoneyData: one person's posted outflow

The author-linked sheet snapshot is `moneydata-author-sheet.csv`, SHA-256 `8e9fba7059145342afa7f765165068e699fd75fe1468a9b299e59e58aa2b3c72`. All 6,567 rows were audited. The observed range is 2015-07-27 through 2022-07-25. There are 6,122 positive debit rows and 445 positive credit rows, no negative debit/credit values, no rows with both debit and credit, and no exact duplicate rows or transaction numbers.

Dates are explicitly parsed as day/month/year from the author sheet. Acquisition found 2,621 day/month swaps in the related Mendeley XLSX when comparing the same transaction numbers; every non-date field matched. The unmodified author CSV is therefore the modeling source. Both source artifacts are retained, and the discrepancy is documented in acquisition records rather than repaired silently.

The target is gross positive `Debit Amount`, with credits excluded rather than netted. It includes bills, transfers, cash withdrawals, and purchases. It is not residual/discretionary spending. Training targets are 2016–2019, validation targets 2020, and test targets 2021. Every split intentionally contains the same person; the chronological holdout can test later posted spending for this case only. There are no repeated history contents or repeated person/origin keys across splits.

All entries post on weekdays: Monday 2,162; Tuesday 1,307; Wednesday 1,039; Thursday 952; Friday 1,107; Saturday/Sunday 0. The source archives weekend activity on Monday. Zero weekend targets therefore measure the posting convention, not absence of weekend spending. Forecast origins still span all seven weekdays so the model is evaluated at arbitrary weekly starting positions.

Validation contains a large outlier: transaction `2713`, dated `06/03/2020`, is an 84,000-native-unit transfer. The maximum validation 14-day total is 101,869.59, versus a median of 2,886.18. This row remains under the precommitted gross-outflow policy. Mean 14-day totals are 2,018.93 / 7,188.19 / 2,674.30 native units, and no window has an entirely zero 14-day target. The validation shift can strongly influence model selection and is a reason to report robust uncertainty and source limitations, not a reason to change the holdout after seeing results.

## Tests and decision

Seven targeted tests passed. They verify exact-cent parsing and malformed amounts; error/refund/fraud/duplicate semantics across raw chunks; pooled card accounts; day-first posted debit semantics; causal first-transaction eligibility; retention of accounts with no future activity; all-weekday origins; group/chronological separation; negative-tensor rejection; policy freeze enforcement; and raw checksum mismatch rejection.

**Train for limited research.** There are zero blocking numeric defects under the stated target definitions. The unresolved scientific limitations are, in order: no representative real multi-customer source yet, unverified individual observation completeness, no validated bill exclusion, card-spending versus checking-cashflow mismatch for IBM, and unknown currency plus one-person/weekday-posting limitations for MoneyData. Neither fallback can independently justify production model promotion.
