# Berka acquisition and training-data audit

| Check | Actual result | Verdict |
|---|---:|---|
| Transaction records fully inspected | 1,056,320 | Complete scan |
| Accounts / clients / dispositions | 4,500 / 5,369 / 5,369 | Foreign keys and primary keys valid |
| Observation dates | 1993-01-01 through 1998-12-31 | Six years |
| Positive posted debits | 651,227 | Exact hundredths aggregated |
| Train / validation / test windows | 103,116 / 14,891 / 14,959 | Nonempty |
| Eligible account-client components | 2,327 / 688 / 625 | Disjoint |
| History / forecast shape | N × 56 / N × 14 | Fixed lengths, float64 |
| Nonfinite values / negative tensor values | 0 / 0 | Pass |
| Duplicate raw rows / transaction IDs | 0 / 0 | Pass |
| Duplicate account-origin records / shared components | 0 / 0 | Pass |
| Daily target zero proportions | 80.0–93.4% depending on split and horizon | Sparse-regression warning |
| All-zero histories, train / validation / test | 5,003 / 439 / 208 | Retained and disclosed |
| Preparation and full numeric audit | Approximately 7 seconds locally | Complete |
| Targeted tests | 10 passed | Pass |

**Train for limited retrospective research.** The raw source and windows are available locally; this is now actual real multi-account data for an IBM-to-Berka transfer comparison. This audit does not establish contemporary US performance, a residual-spending target, or a verified currency for product integration. No model was trained as part of this acquisition task.

## Source, access and permitted scope

Retrieved September 19, 2026 from the Internet Archive's copy of the original PKDD-hosted [`data_berka.zip`](https://web.archive.org/web/20070214120527id_/http://lisp.vse.cz/pkdd99/DATA/data_berka.zip), linked by the [original research challenge](https://web.archive.org/web/20180506061559/http://lisp.vse.cz/pkdd99/Challenge/chall.htm). This is the original archive, not a Kaggle/GitHub mirror or CTU's subsequently modified database version. The archive is 18,074,591 bytes with SHA-256 `affa4477572e9d8f2de6beff8a525d37c056d5d8e4a9670dd8c7636208c002ce`. All eight member CRCs and member SHA-256 hashes are recorded in `forecasting/data/raw/berka/source.json`.

The original call invited knowledge-discovery research, and [CTU currently explicitly provides public database export](https://relational.fel.cvut.cz/dataset/Financial) to support relational machine learning. This supports the local research use here. The reviewed original guide, call and CTU pages do not provide a modern standardized dataset license. Redistribution and commercial-use terms remain unresolved; raw and derived records remain local and Git-ignored. Do not attach an unrelated mirror's license or package records for public redistribution. Attribution: Petr Berka and Marta Sochorova, PKDD'99 Financial Data Set; CTU repository context: Jan Motl and Oliver Schulte.

## Monetary and transaction semantics

The raw fields are `trans_id`, `account_id`, `date`, `type`, `operation`, `amount`, `balance`, `k_symbol`, `bank`, and partner `account`. The [original dictionary](https://web.archive.org/web/20180506035658/http://lisp.vse.cz/pkdd99/Challenge/berka.htm) establishes YYMMDD dates and describes transaction directions and operations. Parsing explicitly prefixes the dates with `19`; ambiguous automatic century conversion is not used.

There are 634,571 `VYDAJ` rows, 16,666 `VYBER` rows and 405,083 `PRIJEM` rows. Both withdrawal types count as debits. Although the dictionary omits `VYBER` as a direction value, every such row has the documented cash-withdrawal operation `VYBER`. Among adjacent observed dates that each contain exactly one transaction, all 9,597 unambiguous `VYBER` balance transitions match a negative amount exactly. This corroborates the explicit inclusion policy. Other directions reconcile within 0.1 source units in all 397,344 unambiguous comparisons; the small discrepancies mean balances should not be treated as an exact-cent ledger proof. No intraday ordering is assumed.

Ten zero-value debit rows are excluded; no negative amount occurs. Credit entries do not offset debit entries. Targets are **gross positive posted outflow**, including cash withdrawals, transfers, scheduled obligations and fees. Neither permanent orders nor loan outcomes are model inputs. Balance is an audit diagnostic only, never a predictor, filter or label.

The historical Czech-bank setting suggests crowns, but neither the inspected primary dictionary nor archive explicitly states a currency code. Metadata therefore says `SOURCE_NATIVE`, with no conversion or USD relabeling. Amount strings are converted to exact integer hundredths before aggregation and to float64 source-native major units when windows are materialized. Combining this forecast with separately scheduled bills would double count obligations without a separate residual-extraction step.

## Frozen split and observation assumptions

`forecasting/data/processed/berka-v2/policy.json` was frozen after inspecting raw schema, dates and transaction types, before any model fit or scores. Its SHA-256 is `cf7c65f6e04c4004b54ab1c5074983b72a657c36f08c1acae99f59bbdbd9a400`.

The split unit is a connected component in the account-client disposition graph. This prevents accounts linked by the same person from crossing holdouts. The actual archive has 4,500 components: 869 accounts have multiple clients, but no client links multiple accounts. Tests include synthetic cross-account links so this fact is not assumed in the implementation. Full-digest SHA-256 of the version and stable component ID assigns 3,155 / 720 / 625 components to the 70/15/15 train/validation/test partitions before eligibility checks.

Training target years are 1993–1996, validation 1997, and final test 1998. Forecast origins are January 1 plus multiples of 15 days, retaining only 14-day targets wholly inside their assigned year. Each history contains the previous 56 days and stops the day before the target. All seven forecast-start weekdays appear in every split. The final test is reserved for evaluation after validation selection. Audit summaries inspect data quality, not model performance.

Eligibility starts at the later of account creation and its first recorded transaction; it never requires subsequent activity. Absent dates from there through the global archive end become observed zeros. This is an unverified completeness assumption: closure and missing feeds are not independently established. No future last-activity filter silently removes inactive accounts. Training excludes 12,620 candidate origins outside global coverage and 187,144 with insufficient prior observation; validation excludes 2,389 insufficient-history origins and test excludes 41.

If IBM 2016–2017 data pretrains a model evaluated on Berka in the 1990s, label the experiment **retrospective domain transfer**. It cannot represent a model that existed at the historical forecast date.

## Distribution and duplicate-content warnings

There are 25,898 / 3,590 / 3,366 all-zero 14-day target windows. Daily targets are even sparser: every daily head is at least approximately 80% zero. Report 14-day-total error and underprediction, plus serious zero/mean/weekday/linear baselines. High daily zero-class accuracy would be uninformative. Mean 14-day totals are 7,762.65 / 8,066.44 / 8,487.62 native units; maxima are 198,000 / 141,914.60 / 216,400. No outliers were removed using those results.

The train/validation, train/test and validation/test partitions share 256 / 142 / 32 distinct numeric history patterns. Within-split duplicate-history excess counts are 7,394 / 490 / 298. These include sparse and all-zero histories from different accounts; they are not repeated account-origin records. Keep this content overlap visible rather than treating every numeric pattern as independent evidence. Cluster uncertainty by the disposition component. Up to 20 all-zero-history account-origin examples per split are retained in the audit JSON.

Required model fields have no missing values. Optional descriptive fields have missing values: operation 183,114; transaction symbol 535,314; partner bank 782,812; partner account 760,931. These fields are not needed for this target or model inputs. Raw transactions cover all weekdays, so the Monday-only posting artifact in MoneyData does not apply here.

## Artifacts and validation

- Raw: `forecasting/data/raw/berka/data_berka.zip` and `source.json`.
- Frozen policy and prepared data: `forecasting/data/processed/berka-v2/policy.json`, `berka_windows.npz`, `berka_audit.json`, `berka_manifest.json`.
- Window-file SHA-256: `12d5dc488ddb0dac23d8c4e9354b6a2684d465f68d5611b83933fbec50034383`.
- Reader: load NPZ with `allow_pickle=False`. Each split has `history`, `y`, `group`, `account`, and `origin`; `group` is the bootstrap component, while **account plus origin** is the record key. Origins are integer days since 1970-01-01. Scalar `metadata` is JSON.
- Reproduce: `forecasting/.venv/bin/python -m forecasting.berka acquire`; `freeze` only on a new output directory; then `prepare`. The original archive checksum, fixed dimensions, frozen policy and unchanged policy bytes are enforced.
- Verification: `forecasting/.venv/bin/python -m pytest forecasting/tests/test_berka.py -q` passes 10 tests covering connected-component separation, exact cents and direction handling, date parsing, causal eligibility, all-weekday origins, invalid source rejection and checksum/freeze checks.

There are zero numeric training blockers. Material limitations are sparse targets, unknown per-account observation completeness, old-domain representativeness, gross rather than residual outflow, unresolved currency and redistribution terms. They limit interpretation and product integration; they do not turn this audited local research dataset into synthetic data.
