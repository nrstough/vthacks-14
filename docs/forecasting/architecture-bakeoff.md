# Proposed architecture comparison and deadline plan

Design written September 19, 2026. **This is a proposed v2 experiment, not a report of completed training.** It does not change `evaluation.json`, execute a sweep, or supersede the completed v1 three-seed MLP comparison. No winning v2 architecture is known. At initial planning time there were approximately 29 hours until Sunday, September 20 at 08:00 Eastern. Devpost's written requirements specify that submission time; use it as the conservative deadline. [Event requirements](https://vthacks-14.devpost.com/).

## Recommendation

Retain the completed v1 audit, three-seed MLP comparison, saved predictor, baseline default, and solver adapter. The proposed next step is **at most four additional hours** implementing and running a separate, frozen v2 comparison of a small MLP, temporal convolutional network (TCN), GRU, and **tiny Transformer as four required contenders**, against recent-average, weekday-average, and ridge forecasts. Nathan explicitly requested the Transformer; it receives the same three seeds, data, training allowance, and eligibility criteria as the other neural models. Add a DLinear-style baseline if its predeclared implementation gate is met. These are engineering allowances, not benchmarked runtime promises.

Nathan's revised source roles control v2: **IBM supplies synthetic pretraining/control data; Nedbank is the intended primary real-user fine-tuning and evaluation source; MoneyData is external case-study evaluation only.** No MoneyData rows enter v2 training, SSL, fine-tuning, global normalization fitting, or model selection. V1's existing MoneyData-trained result remains an unchanged historical experiment. The full real-data study is contingent on authorized Nedbank access and audit; an IBM-only four-architecture fallback would test mechanics, not complete or validate real-data transfer.

The product value is an automatic, intelligible cash-flow scenario with credible accounting. More architectures are useful only if the evaluation can tell whether they help. The strongest outcome by the deadline is a reproducible comparative experiment plus a stable, clearly labelled integration—not a promise that the most elaborate network will win.

## Preserve the meaning of the prediction

All models predict **14 nonnegative daily outflow amounts using the previous 56 observed days**. They are direct multi-output forecasts; no true future values enter an autoregressive decoder. Keep source roles, targets, and reports distinct:

| Source | Honest target | Units and limitation | Solver use |
|---|---|---|---|
| IBM TabFormer | Successful positive card charges aggregated over all cards of a synthetic user | USD, synthetic people; no population validation | Existing adapter rejects `card_spending`: purchase dates are not checking-account repayment dates |
| MoneyData | Gross posted debit outflow, without verified bill exclusion | One real person; use `SOURCE_NATIVE` until currency is established from source evidence; posting-date behavior may differ from purchase dates | Unknown units cannot be forced into the adapter's three-letter currency field; total outflow also requires an explicitly non-overlapping schedule |
| Nedbank, if acquired and audited | Determined from actual dictionary/accounting fields | Real multi-person evidence only if access, accounting semantics, completeness, and relevance are established | Requires its own validated accounting mapping; the bank's name does not prove representativeness for this product |

The architecture comparison establishes scratch controls on IBM and, after audit, Nedbank. The separately frozen [transfer study](transfer-learning-design.md) compares IBM pretraining with real-only scratch and SSL controls before Nedbank fine-tuning. It does not assume every source helps.

V1's frozen configuration uses `SOURCE_NATIVE` for MoneyData after the pre-training source audit. **Do not change that label to GBP without documentary support.** An unknown currency is a metadata limitation, not an invitation to relabel or convert values. It prevents cash-flow integration while still permitting within-source prediction-error comparisons in native amount units.

Neither synthetic data nor one person's history can justify production promotion, even when a numerical comparison favors the network. A model can be saved as an experimental winner for that benchmark while a simple baseline remains the product default. Never describe these targets as residual spending until exclusion of known scheduled outflows has been validated using information available at forecast time.

## Freeze v2 before choosing architectures or opening its final test

Create and commit a distinct `evaluation-v2.json` and split manifest before architecture selection. Record dataset hashes, source versions, preprocessing revision, concrete customer IDs and date windows, configurations, seeds, runtime caps, evaluation rules, and optional-model admission gates. Retain v1 files and results unchanged. Freeze the actual parameter counts after model construction and before comparing validation scores; the proposed ceiling is **50,000 trainable parameters per learned model**.

Once v1's final results are read, its test becomes prior research evidence. **Do not repeatedly reuse the v1 final test as the claim-bearing test of the architecture search.** Candidate fresh v2 targets are:

- **IBM:** preserve the original deterministic customer groups. Fit using the training group's eligible 2016–2017 targets, select using the validation group's 2018 targets, and reserve the test group's eligible **2019 targets** for one final comparison. Verify that raw observation coverage actually contains the selected 2019 windows. These are the same held-out customers used for v1's 2018 evaluation. They remain absent from model fitting, but their cohort has already informed v1 research results: call this a **new future-period test of a known held-out cohort**, not a new population or an untouched person-level research holdout.
- **MoneyData:** exclude every row from v2 training, SSL, fine-tuning, and selection. After the final model and evaluation rules are frozen, apply the fixed predictor to predeclared eligible **2022 targets** ending within audited source coverage. Only each origin's observed historical context may be used as inference input and for the frozen history-only scaling formula; no parameters are fitted to this person. The history extends into July, not a full 2022 calendar year. V1's 2021 results have already been seen, so this is an external single-person future-period case study—not a pristine unseen dataset. Do not select an architecture, seed, baseline, calibration, or checkpoint from its results.
- **Nedbank primary real-data study:** access still depends on the authorized acquisition path. Audit the dictionary, observation coverage, account/person grouping, units, and target semantics before freezing exact customer groups and chronological cutoffs. Reserve genuinely uninspected people/periods, then compare every required architecture on the same real training/validation/test definitions. No exact year split is defensible before that audit. If access arrives after IBM-only selection starts, freeze a separate real-data stage before any Nedbank selection; an IBM-only result does not substitute for the planned real study.

Past context may cross the beginning of a target year because those observations would be available at forecast time. No target extends beyond the declared target-year/coverage boundary. Use the same predeclared 15-day origin stride, cover all seven forecast-start weekdays when coverage allows, and retain every eligible window consistently across models. Freeze coverage rules based on source metadata, not final-test error. If new targets do not exist or were already used for tuning, report validation comparisons only and explicitly leave fresh-test performance unestablished.

Across sources, enforce a pretraining observation cutoff no later than the target study's permitted training cutoff when claiming a historical deployment simulation. Training on later-calendar IBM records and evaluating earlier-calendar Nedbank records must instead be explicitly labelled a retrospective cross-domain experiment; it cannot support an as-of deployment claim. Source-level splits alone do not solve this temporal issue.

## Match information and training conditions

Each model receives the same account grouping, observed windows, target values, scale, and allowed calendar information. No model receives category, fraud, customer identity, future balance, payroll, or merchant features that competitors lack. Related cards/accounts stay grouped by person. Missing observations remain distinguishable from genuine zeroes; any unavoidable assumption about absent posted dates is recorded and held constant.

Keep v1's history-only scale `max(mean(last 28 days), 1 native amount unit)` and normalized daily MSE training loss. Fit normalization on training windows only. Freeze the normalization implementation and save its parameters. Compare all predictions after inversion into original source units and nonnegative output handling.

The MLP/ridge input remains the 99-feature view: 56 normalized daily lags; 14 historical weekday means aligned to the forecast days; 14 future weekday sine and 14 cosine values; and the log scale. Sequence models receive the same normalized 56 daily lags arranged chronologically, historical weekday sine/cosine derived from the same calendar, plus the same 43 non-lag features at the output head. Historical calendar values are determined by the known origin, so they add no private or future-observed information. Record that this tests architecture-specific representations of the same available information, not identical matrix shapes. Classical mean baselines deliberately use simpler functions of that information.

Train the same three random initializations—**11, 23, 47**—for every admitted gradient-trained architecture. Use Adam with learning rate 0.001, batch size 256, gradient-norm clipping at 5, maximum 60 epochs, and patience 10 on validation 14-day cumulative MAE. Use no architecture-specific hyperparameter sweep or dataset-dependent manual tweaks after validation inspection. The fixed ridge search remains alpha in `{0.1, 1, 10, 100}` with an unpenalized intercept. Deterministic baselines do not require duplicate seeded runs.

## Concrete candidate set

The counts below are design estimates except the existing MLP's arithmetic count. Implementation must count actual trainable tensors; failing the ceiling is an implementation failure, not a reason to quietly raise it.

| Candidate | Frozen proposed configuration | Approximate parameters | Priority and reason |
|---|---|---:|---|
| Recent average | Repeat the prior 28-day daily mean | 0 | Required simple reference |
| Weekday average | Mean of each weekday over the prior eight weeks | 0 | Required seasonal reference |
| Ridge | 99 inputs plus intercept → 14 direct outputs; fixed four-alpha search | 1,400 coefficients | Required strong linear reference |
| Existing MLP | 99 → 64 ReLU → 32 ReLU → 14 softplus | 8,942 | Required; rerun under v2's new training/validation split |
| Compact TCN | Four residual blocks, width 24, two causal kernel-3 convolutions per block, dilations 1/2/4/8; last state plus 43 auxiliary features → 32 ReLU → 14 softplus; no dropout | About 15,000 | Required first new sequence model; 61-day receptive field covers the full 56-day history |
| Compact GRU | One layer, 48 hidden units, three historical channels; final state plus 43 auxiliary features → 32 ReLU → 14 softplus; no dropout | About 11,000 | Required second sequence model; tests a recurrent representation without a large model |
| DLinear-style | Decompose observed 56-day history using a fixed 25-day moving average with edge padding; two 56 → 14 linear maps plus a 43 → 14 auxiliary linear map; clip final forecasts to zero | About 2,200 | Optional inexpensive linear control; the auxiliary extension means this is not an exact reproduction of published DLinear |
| Tiny Transformer | Two encoder layers, width 32, **two attention heads**, feed-forward width 64, fixed positional encoding; pool observed states, concatenate 43 auxiliary features, 16-unit ReLU head → 14 softplus; no dropout | About 18,700 | **Required full contender**; same input information, three seeds, and training/validation rules as MLP/TCN/GRU |

The TCN paper supports testing convolutional sequence models alongside recurrent models across a broad benchmark set; it does not establish that a TCN wins on bank histories. [Bai, Kolter and Koltun, 2018](https://arxiv.org/abs/1803.01271).

DLinear's source argues for checking simple linear forecasting models against more elaborate time-series architectures. Its experiments concern different datasets and forecasting conditions. The proposed decomposition adds no new information to the window; with linear heads it partly overlaps the role of a differently regularized linear baseline. [Zeng et al., 2022](https://arxiv.org/abs/2205.13504).

The GRU study motivates a compact gated recurrent comparator; its reported music and speech experiments do not predict our financial-data result. [Chung et al., 2014](https://arxiv.org/abs/1412.3555).

The Transformer contender uses the attention-based sequence architecture introduced by [Vaswani et al., 2017](https://arxiv.org/abs/1706.03762), scaled down for a 56-day input and direct 14-day forecast. The estimated 18,670 parameters assume a 3 → 32 input projection, two standard encoder layers, and the 75 → 16 → 14 head, with fixed positions and no final extra encoder normalization. Verify the actual implementation count. Tiny size makes it a reasonable local contender; this paper does not establish its runtime or financial accuracy here. Benchmark a short training-only timing pilot for **each** neural architecture before its main run.

## Four-hour allowance and stopping rules

The proposed allowance covers implementation, training, and packaging—not four hours of unrestricted search:

| Work | Allowance | Concrete stop/output |
|---|---:|---|
| Environment, frozen v2 configuration, model implementations | 60 minutes | Admission closes at the end of this hour; only candidates passing shape, chronology, gradient/autograd smoke, nonnegativity, and serialization checks proceed |
| Training and validation selection | 120 minutes total wall time | Includes IBM synthetic controls and the audited Nedbank real-data study, all admitted seeds, baseline fits, and overhead; zero MoneyData training; no cloud spend |
| Final eligible comparison and targeted review | 40 minutes | Evaluate frozen finalists on their designated tests, then the fixed real-data finalist in the external MoneyData case if accounting semantics permit; save predictions and cluster/block bootstrap report |
| Artifact packaging, model card, integration handoff | 20 minutes | Save exact configurations, durations, failure logs, checkpoints, hashes, and claim limits |

For the compute allocation, each neural seed gets at most **four minutes** of training, stopping at a safe checkpoint; DLinear-style seeds get one minute each. The four required architectures × three seeds × **IBM and Nedbank** reserve at most **96 minutes**, and optional DLinear at most six, leaving about 18 minutes of the training allowance for baselines, short timing pilots, and orchestration. MoneyData consumes inference/evaluation time only. These caps are planning arithmetic, **not measured speed estimates**. Apply the same failure and time-cap policy to every neural contender, including the Transformer. If actual epochs make the budget unrealistic, stop and report the incomplete comparison explicitly; do not silently remove a required architecture or extend the search until a favorable answer appears. Pending Nedbank access leaves the real-data stage incomplete rather than reallocating its role to MoneyData.

The optional DLinear gate depends on implementation completion and resource availability, not on whether another model's validation score looks disappointing. The four required neural contenders all undergo the same admission checks and timing pilot. A learned candidate is selectable only if all three seeds have valid artifacts and at least three completed epochs. Record time-capped convergence explicitly. Choose the best checkpoint of each seed by validation 14-day MAE, then choose the architecture/seed with the best validation score; publish all seeded validation results so a favorable initialization is visible. Also choose the strongest baseline using validation. Do not pick either finalist using the new final test.

For the final comparison, the learned family is MLP/TCN/GRU/Transformer; the baseline family is recent average/weekday average/ridge plus DLinear-style if admitted. Select any gradient-trained DLinear checkpoint/seed using validation only, and keep it in the baseline family. Do not omit a strong linear result because it makes the neural comparison harder to win.

Use a dedicated forecasting environment. If PyTorch wheels are unavailable for the existing Python 3.14 environment, an isolated Python 3.12 environment is acceptable **if that interpreter is already available**. Do not modify the shared `.venv`, shared frontend dependencies, or other checkouts. If dependency setup consumes more than 20 minutes without a verified working local environment, retain the completed NumPy v1 artifacts and report that the required v2 architecture comparison is blocked/incomplete; do not describe the remaining subset as the completed requested bakeoff. CPU or already-working local acceleration is the intended local execution path; timing pilots verify feasibility before main runs. No GPU rental or unapproved cloud expenditure is part of the design.

## Evaluation and promotion decision

Report source-specific daily MAE, 7- and 14-day cumulative MAE, 14-day signed bias, and mean 14-day underprediction, plus preprocessing, training, and inference duration. Preserve predictions for audit. Resample whole customers for IBM and Nedbank paired improvement intervals; for the external MoneyData case use predeclared blocks of four chronological origins and state the short single-person scope. Compare only already-fixed models and baselines there. The smaller partial-2022 sample further limits precision. Cross-domain native-unit evaluation requires explicit accounting comparability and must not bypass the product predictor's currency checks or invent an FX conversion. Bootstrap uncertainty is conditional on selected fitted models; it does not include all architecture-selection or training uncertainty.

Apply the existing proposed acceptance numbers to the **one frozen primary Nedbank finalist comparison**: at least 5% lower 14-day MAE than the selected baseline, a paired 95% improvement interval wholly above zero, and underprediction no more than 5% worse. If baseline underprediction is zero, no increase is acceptable. Comparison validity and representative real multi-customer evidence remain separate mandatory production gates; audited access to Nedbank does not automatically establish domain representativeness. IBM controls and the MoneyData case cannot independently pass the population-evidence gate. Do not interpret an architecture search victory as a financial guarantee or a calibrated confidence band.

## A separate second phase: does the forecast improve decisions?

Prediction error is not the same as better spending advice. A later, separately frozen solver replay can compare the selected baseline and learned forecast with the **same** opening balances, buffers, known events, user locks, and supplied candidate set. Score actual subsequent cash shortfalls, unnecessary changes, and optimism of the predicted minimum balance. Retain the original exact solver and objective. Any hindsight oracle belongs in evaluation only, never in forecast inputs or candidate construction.

This replay proceeds only when a defensible residual-outflow mapping exists and the known events/candidates could actually have been known at each origin. It cannot be implemented honestly by feeding IBM purchase dates directly into checking balances, renaming total MoneyData debits as residual spending, or inventing real cancellation options after observing outcomes. Synthetic scenario replay is still useful as an explicitly synthetic integration test; it cannot establish real decision benefit. This phase is outside the four-hour architecture allowance and should not block a stable demonstration.

## Deadline and coordination recommendation

A realistic high-end demonstration by Sunday morning has a working history-to-schedule path, explicit modelled-data provenance, a saved forecast that can be inspected, natural-language purchase scenarios if the owning agents deliver them, and the existing solver's conditional explanation. A neural-versus-baseline comparison panel can explain the experimental result even when the network is not the default. A learned pain model, autonomous bank actions, and production-quality residual training data are not evidence-backed promises for this deadline.

Recommend a **Saturday 22:00 Eastern feature freeze**, leaving roughly ten hours before the assumed 08:00 deadline for integration defects, restart/offline checks, demo rehearsal, submission assets, and rest. This is a planning recommendation, not a claim that an older 18:30 gate is binding. The solver handoff records that older gate as disputed; Nathan's current scope and the integration owner's actual status control the decision.

Codex owns the forecasting branch/worktree and its `forecasting/` and `docs/forecasting/` paths. Claude's backend workstream owns candidate generation, synthetic account generation, recurrence/Nessie work, and deployment; the frontend workstream owns UI and its dependencies. Provide the predictor contract and standalone adapter as a handoff; do not wire them into another agent's checkout or merge/deploy without authorization. The existing adapter generates no candidate actions. In the current solver, multiple candidate options may refer to one transaction, while at most one may be **chosen**; do not copy the older handoff's stronger wording as a schema restriction.

The handoff to Claude should state exactly which model ran, whether it is a baseline or experimental neural candidate, its source/target/units, what overlaps must be excluded, where its artifacts and tests live, and what remains unimplemented. An architecture proposed in this document must never be described as tested merely because it appears in the comparison table.

## Separate proposed follow-up

[Multi-source pretraining and adaptation](transfer-learning-design.md) specifies a possible tiny-Transformer SSL/transfer study and explains the limits of RL on transaction logs. It requires a fresh evaluation freeze and its own explicit budget; it does not expand this four-hour architecture comparison or change v1.
