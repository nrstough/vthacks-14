# Public-source forecasting v1: results and model card

Run September 19, 2026. **Neither neural candidate earned promotion.** The saved default is the weekday average for IBM and ridge with alpha 100 for MoneyData. Both defaults and neural checkpoints remain experimental because neither dataset establishes representative real multi-customer checking-account performance.

## Final results

Model settings, epoch and seed were selected by validation 14-day total MAE before final-test evaluation. The table compares the selected neural model with the validation-selected baseline, not a baseline chosen after seeing the test.

| Source / selected model | Daily MAE | 7-day total MAE | 14-day total MAE | 14-day bias, predicted−actual | Mean 14-day underprediction |
|---|---:|---:|---:|---:|---:|
| IBM weekday average | 91.22 | 285.49 | **434.19** | −1.03 | **217.61** |
| IBM MLP, seed 47 | **86.46** | 286.73 | 438.19 | −40.42 | 239.30 |
| MoneyData ridge, alpha 100 | 275.98 | **990.54** | **989.74** | +509.50 | **240.12** |
| MoneyData MLP, seed 11 | **246.50** | 1,266.31 | 1,055.41 | −161.66 | 608.54 |

IBM amounts are synthetic USD card charges. MoneyData amounts are source-native units with unverified currency; values across sources must not be combined or compared as the same money. Daily errors and errors in summed totals answer different questions: lower daily MAE did not translate to a better 14-day total estimate here.

IBM's neural 14-day MAE is 0.92% worse. The paired baseline-minus-neural improvement is −4.00, with a 95% customer-bootstrap interval of **[−10.00, +2.10]**, resampling all windows of each of 230 test customers (2,000 replicates). Underprediction is 9.97% higher. MoneyData's neural MAE is 6.64% worse; the improvement interval is **[−393.93, +279.09]** using circular blocks of four date-ordered origins. That is only 24 test windows from one person, not population evidence. Its neural underprediction is about 153.4% higher than the selected ridge baseline.

The precommitted gate required at least 5% lower 14-day MAE, an improvement interval entirely above zero, no more than 5% higher mean underprediction, valid processing, and representative real multi-customer evidence. Both fail the numeric and evidence requirements. These intervals describe errors of the selected fitted models, not uncertainty in each future forecast; they omit architecture-selection/training uncertainty.

## Data and splits

| Source | Raw rows / people | Training windows | Validation windows | Test windows | Target periods |
|---|---|---:|---:|---:|---|
| IBM TabFormer | 24,386,900 / 2,000 synthetic users | 26,579 | 5,822 | 5,481 | 2016 / 2017 / 2018, disjoint user groups |
| MoneyData author sheet | 6,567 / 1 real person | 96 | 24 | 24 | 2016–2019 / 2020 / 2021, one-person temporal split |

Every forecast uses 56 previous days to predict 14 subsequent days. Origins are spaced 15 days apart and cover all seven starting weekdays. Related IBM cards are pooled by user. Target dates are chronological across splits; preprocessing statistics fit training examples only. Full numeric audit and source/license evidence are in `data-audit.md`, `acquisition.md`, and `source-manifest.json`.

The IBM target excludes failed attempts and nonpositive charges; refunds are not netted and positive successful fraud-labelled charges remain. MoneyData uses gross positive posted debits, including bills, transfers and withdrawals, without netting credits. An 84,000-unit transfer strongly affects MoneyData's validation period. Weekend MoneyData activity is posted on Monday. Neither target excludes known bills, and neither is validated residual spending.

The audit found 2,621 exact day/month swaps in the Mendeley workbook relative to the author-linked sheet. The workbook is retained unchanged for provenance but excluded; the checked CSV snapshot is the modelling source. Currency was changed from presumed GBP to `SOURCE_NATIVE` before training because the available source does not explicitly establish it.

## Models and selection

Classical controls were a 28-day mean and eight-week weekday mean. Ridge used 99 standardized history/calendar features with alpha in 0.1, 1, 10, 100, an unpenalized intercept, and nonnegative-clipped outputs. The MLP has 8,942 parameters: 99→64 ReLU→32 ReLU→14 softplus. Inputs and labels use a past-only scale of max(last-28-day mean, 1 source monetary unit). Adam learning rate 0.001, batch 256, gradient norm cap 5; stop after 10 validation epochs without improvement, maximum 60.

All three seeds ran. IBM seeds 11/23/47 selected epochs 15/20/6 after 25/30/16 total epochs. MoneyData selected epoch 1 for all seeds after 11 epochs each, showing limited useful fitting under this tiny, shifted validation set. There was no final-test tuning or neural promotion by selecting a more favorable final-test seed. Full scores for every frozen model/seed are retained for transparency, not post-test selection.

## Measured local time

IBM download took 245.9 seconds; full raw preprocessing took 85.41 seconds. MLP training across three IBM seeds took **2.350 seconds** (0.835, 0.988, 0.526). The whole IBM fitting/evaluation/serialization run took 2.747 seconds, excluding download and preprocessing. Its selected MLP predicted 5,481 test windows in 0.00675 seconds as a single NumPy batch; this is not end-to-end API latency or a single-request benchmark.

MoneyData preparation took 0.036 seconds and its entire model run took 0.084 seconds. These small measurements are hardware/process dependent and are not promises for GRU, TCN, Transformer, larger datasets, or another machine. The architecture bake-off has a separate timing pilot.

## Saved artifacts and intended use

`forecasting/artifacts/{ibm,moneydata}-public-v1/` holds `default.json/.npz`, `neural-selected.json/.npz`, all three seed checkpoints, validation selection, final prediction arrays, example inputs/outputs, exact policy, fingerprints and results. `forecasting/data/processed/` contains windows, audits and manifests; raw source/licensing files are under `forecasting/data/raw/`. These directories are Git-ignored and must be retained or restored from the artifact bundle.

The predictor rejects incomplete or unobserved history, nonfinite/negative amounts, wrong currency, changed weights, incompatible versions, bad weight shapes and invalid normalization. Its 14 dated point estimates carry source, model ID, target, currency and `experimental: true`. They carry no calibrated confidence band or probability of solvency.

IBM's `card_spending` cannot be appended to a checking ledger: purchase dates and repayment dates differ. MoneyData's unknown currency blocks conversion to a currency-specific solver request. Even a known-currency total-outflow forecast requires verified non-overlap with supplied scheduled events. The adapter records a caller's non-overlap evidence; it cannot prove that assertion from aggregate amounts. It generates no cancellation/skip candidates.

The executable solver example therefore uses three labelled synthetic assumptions. Existing-solver minimum balances are 7,000 cents with schedule only, 3,500 cents with 500 cents/day residual spending, and −3,500 cents with 1,500 cents/day. This verifies conditional plumbing, not real-world forecasting benefit.

## Validation and provenance corrections

133 targeted forecasting tests passed; the unchanged backend's gate suite passed 977 tests, with six performance tests deselected. The full forecast suite includes acquisition integrity, chronological/customer split checks, amount semantics, missing data rejection, independent neural finite-difference gradients, deterministic saved inference, metadata validation and solver adapter failures. No frontend or API code was modified.

An independent review caught an artifact-format issue after IBM v1 ran: the exact policy bytes were hashed, but a reformatted equivalent JSON was saved. The exact hash-matching original was restored beside the preserved reformatted copy, with `packaging-note.json`; no weights, predictions, scores or selection changed, and no training rerun occurred. The training program now snapshots policy bytes once and never rereads a live policy during model saving. The MoneyData run used that corrected packaging. Additional predictor artifact validation also leaves saved forecasts unchanged.

## Limits and next experiment

The downloaded data supplies no independent missing-observation flags. Dates after a customer's first qualifying transaction through the source's global endpoint are assumed observed; closed accounts or missing logs could violate that assumption. All-zero histories are explicitly retained and audited. The predictor's production caller must supply a stronger observation contract.

Nedbank acquisition was initially blocked by Zindi verification and challenge terms. After v1 packaging, the user verified the account and attempted final acceptance, then reported that Zindi refused joining because the challenge had ended. Access through this challenge remains blocked; no Nedbank records were downloaded or trained. Another authorized source or organizer-provided access is required. No private bank export was opened or used. No learned pain model, reinforcement learning, calibrated intervals, live bank actions or production validation is delivered here.

The next designed experiment compares MLP, TCN, GRU and a required tiny Transformer on a new versioned split. Existing v1 tests must not be reused as fresh evidence. A paired self-supervised-transfer study can separately test whether shared representations help. Design documents are proposals, not claims that those architectures have already run.
