# V2 numeric data admission

Prepared and frozen before model fitting on September 19, 2026. All counts below are computed from the downloaded records and resulting tensors. Labels are later observed outflows, not human preference labels. IBM records are simulated; Berka records come from the historical real-bank challenge. Neither establishes modern US student performance.

| Check | IBM | Berka | Verdict |
|---|---:|---:|---|
| train windows | 53,340 | 103,116 | Available |
| train groups | 1,117 | 2,327 | Disjoint between splits |
| train all-zero histories | 1,967 (3.69%) | 5,003 (4.85%) | Retained; completeness assumption disclosed |
| train daily target zero fraction range | 12.1%–12.5% | 82.5%–92.4% | Sparse target; use monetary errors, not zero-day accuracy |
| validation windows | 5,915 | 14,891 | Available |
| validation groups | 249 | 688 | Disjoint between splits |
| validation all-zero histories | 383 (6.48%) | 439 (2.95%) | Retained; completeness assumption disclosed |
| validation daily target zero fraction range | 13.5%–14.5% | 81.8%–93.1% | Sparse target; use monetary errors, not zero-day accuracy |
| test windows | 5,520 | 14,959 | Available |
| test groups | 230 | 625 | Disjoint between splits |
| test all-zero histories | 334 (6.05%) | 208 (1.39%) | Retained; completeness assumption disclosed |
| test daily target zero fraction range | 14.0%–15.3% | 80.0%–93.4% | Sparse target; use monetary errors, not zero-day accuracy |
| Nonfinite or negative tensor entries | 0 | 0 | Pass |
| Duplicate account/person + origin records | 0 | 0 | Pass |
| Cross-split customer/component overlap | 0 | 0 | Pass |
| History / target length | 56 / 14 | 56 / 14 | Pass for every record |
| Target periods strictly ordered | Yes | Yes | Pass |

## Train verdict

**Train for limited retrospective research.** There are zero numeric blocking findings. Berka account-client components are separated before SSL or supervised fitting. IBM preserves the original `forecast-v1` person split while reserving 2019 as a new future-period test of the already-known held-out cohort. Train/validation/test membership is recorded in the retained split manifests and their committed hashes.

## Interpretation and known limits

- Berka daily labels are roughly 80–93% zero. A model can look accurate at predicting zeros while missing financially important bursts. Primary selection uses 14-day amount error; underprediction and simple baselines are reported alongside it.
- Identical numeric histories exist across unrelated accounts (including all-zero and routine-charge patterns). These are not duplicated account-origin records; content overlap and identity overlap are separately audited.
- Absent transaction days are assumed observed zeros after prior account observation. Feed completeness and account closure are not independently established. No future last-activity filter is used.
- Berka direction `VYBER` is not listed alongside `VYDAJ` in the old direction dictionary, but its operation means cash withdrawal; all 9,597 unambiguous balance transitions inspected agree exactly with a debit. Both are counted.
- IBM is synthetic card spending; Berka is gross posted outflow including transfers, bills and cash withdrawals. Neither has validated known-bill exclusion. No forecast is silently appended to a separately scheduled bill ledger.
- Berka currency remains `SOURCE_NATIVE` because the inspected original materials do not explicitly establish a currency code. Within-source scaled research is permitted; dollar labeling and currency-dependent product integration are blocked.
- IBM 2016–17 pretraining transferred into Berka 1990s is retrospective cross-domain research, not an as-of historical backtest.
- MoneyData is excluded from all v2 fitting, normalization, selection and this comparison.
- Raw Berka and per-account derived data stay local. The original research-release basis is documented; a modern redistribution license is not asserted.

Machine-readable audit, source-policy and manifest copies are stored beside this document. The private datasets remain under `forecasting/data/processed/{ibm,berka}-v2/`.
