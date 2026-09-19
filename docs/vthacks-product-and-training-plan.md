# Overdraft Guard: product direction and training plan

Recorded September 19, 2026, following Nathan's product discussion. This document captures the expanded direction, implementation recommendations, open questions, and the first completed training experiment. It does not mean the expanded app has been built. The solver is being changed independently by Claude; inspect its current code and frozen API contract before integrating anything.

## Product we are aiming for

**“Can I afford this—and if not, what would make it work?”**

Start with transaction history, infer the ordinary schedule, and show a useful answer immediately. A person should not need to enter every future grocery trip, manually schedule every bill, or confirm a long list before getting value. The original exact cash-flow repair solver remains the calculation engine. The expansion supplies more realistic inputs and a more natural way to explore decisions.

Nathan explicitly wants a meaningful neural-network component. The proposed role is forecasting everyday spending that is absent from known bills. A learned spending forecast and an exact optimizer solve different problems; this preserves the reason to use each.

## Three separate responsibilities

| Component | Job | What it does not establish |
|---|---|---|
| Spending neural network | Estimate the next 7–14 days of ordinary outflows from prior spending and calendar context. | Exact future transactions, contractual cancellation rights, or a guarantee of avoiding an overdraft. |
| Exact optimizer | Given dated cash flows, permitted changes, protected expenses, and a cushion, calculate the best available plan under the configured objective. | Whether the forecast assumptions will happen. Optimality is conditional on these inputs and the candidate set. |
| Gemini API | Convert natural language into validated scenario changes; explain the solver's actual result in plain language. | New balances, invented savings, or permission to take financial actions. |

A normal Gemini request plus structured output is enough for conversational input. An autonomous agent system is not required. “I want to buy $180 headphones Friday, but don't touch groceries” becomes a proposed purchase and a protected category. Validate the amount, date, affected records, and constraints; calculate the alternatives; then let Gemini explain those calculated results. If parsing is ambiguous, ask one focused question. Show editable assumptions so the person can correct a misunderstanding.

Keep a deterministic fallback: amount/date controls and result templates should work if Gemini is unavailable. Never let an explanation silently change a number returned by the solver. No transfer, payment, cancellation, or merchant message is authorized merely by asking for a what-if plan.

## Where bills and future expenses come from

There are three different inputs, with different evidence:

1. **Known schedules:** a bill record or user-entered obligation with a date and amount. Nessie has bill resources, but exact semantics and current API behavior need an authenticated smoke test.
2. **Inferred recurring events:** repeated payroll, rent, subscriptions, or other charges detected in history. Normalize descriptors, group plausible streams, estimate cadence and amount variation, and project occurrences. Three observations can be an initial heuristic; it is not proof that a payment will recur. Handle month ends and calendar shifts explicitly.
3. **Unscheduled ordinary spending:** food, transport, and other purchases that cannot be projected as exact future charges. This is the proposed network's target.

The current fixture's exact future grocery/food-delivery schedule demonstrates the solver but is not what real transaction history gives us. An adapter must replace that artificial certainty with known events plus an estimate of the remaining spending.

Remove known recurring charges from the historical residual target and add their future occurrences separately. Otherwise the same bill gets counted twice. In backtests, recurrence detection must use only information available at the forecast date—not the entire future history. Also distinguish transfers, refunds, pending and posted transactions, and missing data from actual zero-spend days.

Ask the user only about uncertainty that materially affects the result: “Is this deposit your paycheck?” or “Does this cancellation take effect before Tuesday?” Prefer a useful provisional outlook with visible assumptions to an onboarding questionnaire. Do not infer that an expense is expendable simply from its merchant or category.

## Proposed interaction

The first screen shows the current outlook, the next important date, a daily balance chart, and an input such as “What are you thinking of buying?” Add example chips for common questions. A secondary panel holds detected bills and assumptions for correction; it is not mandatory setup homework.

For a purchase question, compare three alternatives:

| Card | Calculation | Useful output |
|---|---|---|
| Buy now | Insert the purchase at the requested date and replay the schedule. | Lowest projected balance and date; whether the cushion survives. |
| Wait | Evaluate specific later purchase dates, including payday. | Earliest tested date that meets the constraints. Say which dates were searched. |
| Make room | Give the optimizer the proposed purchase plus verified or explicitly assumed change options. | Dated changes, their consequences, and any unresolved cash gap. |

The user can protect an expense, change a purchase amount, or reject an action. Recalculate and show what changed. Do not promise that all three cards will always offer a workable option. “There is still a $X gap by Tuesday” is a useful answer if it is calculated honestly.

When history changes, first replay the **existing plan** against the new inputs. Say whether it still holds, then offer to replan. Silently finding a different solution would hide that the old plan broke.

Use forecast shading only if its meaning is supported. The current pilot produces point estimates, not calibrated intervals. A shaded range of deliberately tested scenarios can be labeled “scenario range”; it must not be called a 90% confidence band. Per-day quantiles alone also do not establish the probability of staying solvent throughout a multi-day horizon.

## What makes the plan credible

Attach evidence and an effective date to candidate changes. Distinguish confirmed terms, user assumptions, and unverified possibilities. A transaction record does not prove a cancellation will prevent the next charge. A deferral is a later obligation, not permanent savings; show the return date and known costs. Protect essentials through explicit user preferences. Retain a preview beyond payday so an apparent fix cannot simply conceal tomorrow's deficit.

An exact answer should read as conditional: sufficient under the schedule, forecast, available actions, horizon, and protections shown. Strong minimum-action wording also requires the optimizer's appropriate optimality status. Use the existing solver contract and certificate logic as the authority.

Stress tests can examine late payroll, lower payroll, and additional spending separately and together. Test the same selected plan, specify extra-spend timing, and extend the horizon when a delayed paycheck falls beyond it. A finite scenario grid is evidence about those scenarios; it is not a probability model or a claim about every possible shock.

## Competitive position

Cash-flow charts, budget allocation, subscription cancellation, and conversational finance already exist. The earlier research compares Simplifi, PocketSmith, PocketGuard, YNAB, Rocket Money, and Cleo. Cleo's advertised adaptive forecasting and financial actions make it a particularly close comparator. See [the research brief](overdraft-guard-research-and-neural-net.md) for primary links and limitations.

The strongest proposed distinction is an inspectable, dated repair plan with explicit alternatives and a checkable conditional certificate. Avoid “nobody does this” claims. We have reviewed public product descriptions, not every competitor's implementation.

## Training data: what we have and what we need

**Dataset research update (Sept 19):** [The source investigation](vthacks-dataset-research.md) now identifies Nedbank/Zindi as the first real-history candidate, MoneyData as an independent case study, and IBM TabFormer as the synthetic fallback. The older options below remain background; no new dataset has been downloaded or validated.

**Nessie is a banking simulation API, not an established training corpus.** Its records can feed a demo and can carry histories we generate, but writing synthetic transactions into Nessie does not make them real training observations. No Nessie data was downloaded for this pilot; all its training values were generated locally. The live-doc review did not establish a sufficiently large, representative, licensed history dataset behind the API. See [the Nessie brief](nessie-agent-brief.md) for endpoint coverage and unresolved documentation discrepancies.

| Source | Useful for | Status and limitation |
|---|---|---|
| Locally generated histories | Test shapes, learnable patterns, evaluation, and the app's plumbing without personal data. | Used for this pilot. Evidence applies only to the simulator. |
| Nessie sandbox records | Demonstrate bank-style ingestion and account relationships. | Integration still needs runtime verification. Not assumed to be representative human behavior. |
| Authorized real transaction histories | Test whether forecasting helps on actual spending patterns. | Not used. Need sufficient time coverage, appropriate permission, normalization, and a chronological holdout. One person's history cannot establish broad accuracy. |
| CTU/PKDD'99 Financial | Candidate historical real transaction data for a separate external benchmark. | Public repository describes real measurements and 1,090,086 rows across eight tables, not that many customers. It was organized around loan outcomes. Inspect actual transactions, units, coverage, and usage terms before adapting it; it is not current US spending data. [Dataset](https://relational.fel.cvut.cz/dataset/Financial). |
| Pretrained Chronos-Bolt | Another neural forecasting candidate requiring no custom training for initial inference. | Official model card supports zero-shot forecasts; Tiny has 9M parameters. It still needs evaluation on this task. Not downloaded or benchmarked in this pilot. [Model card](https://huggingface.co/amazon/chronos-bolt-small). |

Avoid choosing a dataset just because its title says “financial.” Fraud labels, credit default labels, and generated card purchases do not automatically provide the complete dated outflows needed here. We do not need humans to annotate “tomorrow's spending”: for an observed historical window, later observed daily spending supplies the target. We do need reliable extraction of the spending being predicted.

## What ran tonight

A small original NumPy neural network was trained locally: **8,942 parameters**, 56 prior days as context, and 14 daily outflow predictions. This is a residual-spending pipeline pilot, not a model of full bank balances. There are 1,800 training accounts, 300 validation accounts, 300 test accounts, and 300 separate stress accounts, all synthetic.

Three random initializations with validation-based early stopping, checkpoint saving, and evaluation took **2.05 seconds** in the measured training command. That excludes data generation and auditing. No GPU rental or overnight process was needed.

On the held-out synthetic accounts, average error in total spending over the next 14 days was **$103.26 for the network, $113.43 for a recent-28-day average, and $103.16 for an eight-week weekday average**. Lower is better. The network beat the weaker baseline but did not beat the stronger one; this does not justify making it the default predictor. These are errors in artificial dollar-valued data, not expected accuracy for a customer.

The full report documents important limitations, including ordinary forecast windows starting on just one weekday, correlated windows within accounts, no missing-data test, no real-data validation, and no calibration. The stress set combines a different start weekday with an abrupt spending change, so it does not isolate the cause of failure. The dataset has been retained unchanged for reproducibility.

See [the training report](vthacks-training-pilot.md). Reproducible code, audit files, metrics, and checkpoints accompany it in the experiment bundle and project experiment directory.

## How long the useful next model takes

Small tabular/sequence networks on a dataset this size can train in seconds to minutes here; more data, larger architectures, or multiple experiments can take longer. The measured 2.05 seconds is specific to this pilot, not a forecast for an arbitrary model. Training Gemini from scratch is neither needed nor proposed.

The larger work is preparing representative histories and proving the result helps. Budget hours for ingestion, target extraction, evaluation, and integration. We should not spend the night repeating epochs on this same synthetic dataset: early stopping already identified its best checkpoints.

Recommended next experiment: agree on a new dataset version with forecast origins across all weekdays; retain the current pilot; split unseen accounts and dates before training; reserve an untouched final evaluation set. Include the weekday average and a regularized linear model as serious baselines. If available, add an independent real-data benchmark. Compare 7-/14-day totals, daily errors, and costly underprediction, then evaluate the downstream plans under realized spending. Use account-level resampling for uncertainty because multiple windows from one account are correlated. Do not tune against this pilot's already viewed test results and call them a fresh holdout.

Only promote the learned model if it supplies meaningful, repeatable value on an appropriate holdout. Until then, keep a tested simple predictor as the operational fallback and label the neural path experimental. The pilot proves we can train a network tonight; it does not yet prove the network improves the product.

## Build sequence and timeboxes

This is the proposed expansion order after a working core; it is not a replacement frozen implementation spec. Keep each increment independently demoable.

| Block | Target | Planning allowance |
|---|---|---|
| Automatic history ingestion | Adapter, normalization, recurrence, residual extraction, visible assumptions. | 4 hours |
| Forecasting | Strong baseline, neural evaluation, saved predictor, forecast metadata. | 4 hours |
| Affordability + Gemini | Validated purchase/preference input and three calculated alternatives. | 3 hours |
| Shock handling | Replay current plan, stress scenarios, explicit replanning. | 2 hours |
| UX | Editable assumptions, protections, readable results, chart semantics. | 2 hours |
| Integration and delivery | Failure paths, offline demo, tests, deployment, presentation. | 3 hours |

These sum to 18 hours and are rough allocations, not commitments. Cut scope if the core slips. A coherent purchase decision flow is more useful than several disconnected sponsor integrations. Keep cancellation execution, financial transactions, a large bespoke transformer, and complex multi-agent infrastructure outside this proposed hackathon build.

## Prize corrections and Gemini's purpose

Nathan clarified **three VT tracks and unlimited MLH tracks**. This replaces the earlier uncertainty about MLH consuming the three slots; the source for the cap is Nathan's clarification. Category-specific eligibility still applies. There is no need to add an unrelated VT integration merely to fill the third slot.

The event's **Best Use of Gemini API** prize is **Google Swag Kits**, as listed on [VTHacks 14 Devpost](https://vthacks-14.devpost.com/). The proposed Gemini feature is the natural-language purchase/preference interface and explanation of calculated alternatives. Training our own spending network does not by itself use the Gemini API or qualify for that track. The previous suggestion of a separate “Best Use of Gen AI” event track was incorrect.

Prioritize Nessie where it improves ingestion, keep the already planned Vultr/domain entries, and enter Gemini if the actual integration is completed. Do not treat the broader MLH allowance as a reason to add tools without a product role.

## Instructions for the next implementation agent

Read current solver docs and the frozen API contract first; the repository is actively changing. This document records the intended product direction, while the linked research briefs are dated snapshots. The training pilot is isolated and has not been integrated into the API or UI. Avoid rewriting the solver or changing its objective to accommodate a model.

Implement the data-to-schedule boundary before connecting neural outputs. Every predicted amount must identify its forecast date, horizon, source/model version, and whether it overlaps a known scheduled charge. Convert dollars to integer cents only at the solver boundary with an explicit rounding rule. Avoid mutating an in-progress plan silently when a forecast changes.

Prepare a focused integration spec from this direction and the current code. Preserve the simple predictor, offline fixtures, provenance labels, and the existing solver's proof-status handling. Report neural results with their synthetic-data limitation and do not describe this prototype as a validated financial predictor.
