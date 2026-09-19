# Proposed multi-source pretraining and adaptation experiment

September 19, 2026. **Design only: no additional training or architecture implementation is authorized by this document.** It leaves the v1 experiment unchanged and follows the [architecture comparison](architecture-bakeoff.md). This is a separately frozen follow-up, not a silent expansion of that comparison's four-hour allowance.

## What is plausible

Multi-source self-supervised pretraining followed by adaptation to a smaller dataset is a reasonable research direction. The useful question is whether transferred patterns improve held-out forecasting over the **identical small Transformer trained from scratch**. More training stages do not themselves demonstrate an improvement.

PatchTST reports masked time-series pretraining and transfer between datasets, supporting this as a testable approach. [Nie et al., 2023](https://arxiv.org/abs/2211.14730). Chronos combines public time series with synthetic pretraining data and evaluates transfer across forecasting tasks. Its architecture, size, and benchmarks differ substantially from this proposed tiny model. Neither result establishes a winner for personal banking. [Ansari et al., 2024](https://arxiv.org/abs/2403.07815).

The source set is **not limited to Zindi**, and each source now has a distinct user-directed role: **IBM for synthetic pretraining/controls, Nedbank for primary real-user fine-tuning and evaluation, MoneyData for external single-person evaluation only.** V1 already trained separate IBM and MoneyData models; those historical results remain unchanged. No MoneyData rows enter v2 training, SSL, fine-tuning, global normalization fitting, or selection. Authorized Nedbank access, terms, and audit remain prerequisites for the full real-data study. An IBM-only architecture comparison can test mechanics while access is pending; it cannot substitute for real transfer evidence.

## Sources, features, and adaptation target

Different banking datasets are different **domains**, not automatically different modalities. Daily amounts and calendar features are the common starting point. Transaction categories and description text can add distinct feature types when available; test them as separate later ablations. Adding text, categories, a new architecture, and pretraining simultaneously would obscure what helped.

Keep source provenance and accounting targets explicit. IBM contains synthetic card purchases; MoneyData is one person's posted debits with currency unconfirmed (`SOURCE_NATIVE`); Nedbank's usable target follows its dictionary and audit. History-based scaling permits numerical transfer in native units, but does not turn card purchases into checking debits or total outflows into residual spending. Missing observations must remain distinct from real zeroes.

The fine-tuning target is **audited Nedbank**, not whichever dataset is smallest. MoneyData remains outside adaptation because it represents only one person. Do not pool source-specific errors in incompatible currencies into a single monetary score.

## Concrete paired experiment

Freeze a new versioned configuration, split manifest, source hashes, and final evaluation before pretraining. Audit Nedbank before assigning exact customer groups and chronological cutoffs; reserve genuinely uninspected people/periods. Split **before SSL**, never pretraining on held-out users or test futures. IBM's proposed 2019 control is a new future period of its known held-out cohort. Across sources, restrict pretraining observations to the target study's permitted training cutoff for a historical deployment claim; otherwise label the study retrospective and disclose use of later-calendar source data.

Use the same tiny Transformer trunk and downstream 56-day → 14-day nonnegative forecast head in each condition, with seeds 11, 23, and 47:

| Condition | Purpose |
|---|---|
| Nedbank-only scratch | Primary real-domain comparator |
| Nedbank-training-only SSL → Nedbank fine-tuning | Tests SSL without synthetic transfer |
| IBM-training-only SSL → Nedbank fine-tuning | Tests whether synthetic pretraining adds value |
| IBM forecast pretraining → Nedbank fine-tuning | Controls for transfer without masked reconstruction |
| Optional IBM + Nedbank-training-only SSL → Nedbank fine-tuning | Tests mixed-source pretraining rather than assuming all sources help |
| Optional frozen IBM-SSL encoder → Nedbank forecast-head training | Tests transfer with fewer adaptable parameters |

Forecasting targets already come automatically from later observed transactions. Masked reconstruction must therefore earn its place against ordinary forecast pretraining. Select checkpoints on Nedbank validation only. Optionally precommit adaptation using the earliest 25% versus all eligible Nedbank training origins. These are training-window budgets, not savings in manual labelling.

For SSL, hide one randomly chosen contiguous seven-day patch within each 56-day **training-only observed** sequence and reconstruct its amounts. A pretraining-only reconstruction head and explicit learned mask indicator prevent hidden values from masquerading as true zeroes; discard that head for forecasting. Preserve calendar values, which are known independently.

Prevent a subtle reconstruction shortcut: **do not feed weekday means, totals, scales, or other summaries computed from the hidden amounts**. Compute each masked example's scale from visible amounts only; disable the downstream auxiliary summary features during reconstruction. Fit any global normalization on training data only. Normal forecasting may restore its usual history-only scale and summaries because the entire historical window is then observed. Add a test that changing hidden values cannot change model inputs or their normalization.

In the optional mixed-source condition, sample IBM and Nedbank training sources equally, then people and windows within source. Log oversampling and unique examples so raw source size does not silently determine the mixture. MoneyData is never sampled. Keep source-ID embeddings out initially so the transfer initialization is the principal change.

## Fair budgets and interpretation

Allocate and log total optimizer updates, examples processed, and wall time. Include a scratch run with the same **total compute allowance** as pretraining plus fine-tuning, alongside the ordinary scratch run with the same fine-tuning budget. Otherwise an apparent SSL gain may reflect extra computation. Count all source-pretraining and adaptation time, including failed runs.

Use existing forecast metrics and customer-bootstrap uncertainty on the primary Nedbank test; report negative transfer honestly. After final model and evaluation freeze, test predeclared eligible **2022 MoneyData** origins within audited coverage using fixed weights and only observed history as inference input. Do not adapt, calibrate, or select on this case. V1's 2021 MoneyData results were already seen: this is a new future-period case, not a pristine unseen dataset. Accounting/unit comparability must be explicit; do not bypass product currency guards. Synthetic and single-person findings cannot establish population promotion. If a proposed test already informed selection, reserve new evidence or label results exploratory.

## Why RL is a different problem

Transaction logs do not provide the needed recommendation actions, feasible alternatives, user discomfort rewards, and resulting counterfactual outcomes. Learning that someone spent money does not reveal whether advising a cancellation would help or whether they would accept it. Offline RL is particularly vulnerable when evaluating actions and outcomes poorly represented in its logs. [Kumar and Singh, BAIR, 2020](https://bair.berkeley.edu/blog/2020/12/07/offline/).

A simulator can provide actions and rewards for an explicitly synthetic RL experiment. Its result would validate behavior inside that simulator, not human preferences or real financial outcomes. For the existing fixed schedule, candidate set, and objective, the optimizer already solves the decision problem and reports whether optimality was proven; an RL replacement would duplicate that role without the same proof. Stochastic long-horizon policies could be later research once the decision setting, simulator assumptions, and evaluation are justified.

The practical progression is therefore **audited forecasting → measured transfer → credible residual mapping → fixed-solver replay**. Preserve RL as a separately motivated future study rather than assuming it is the necessary final training stage.
