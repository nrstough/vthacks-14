# Deadline scope and ownership check

Written September 19, 2026 after Nathan requested a realistic upper end, an architecture bake-off, a required tiny Transformer, and an honest assessment of cross-dataset self-supervised transfer. This is a product/integration recommendation; it does not authorize this forecasting workstream to edit other owners' files or deploy their app.

## Realistic upper end

At approximately Saturday 02:43 Eastern there were about 29 hours 17 minutes until Sunday 08:00. [Devpost's written requirements](https://vthacks-14.devpost.com/) give Sunday, September 20 at 08:00 Eastern as the submission deadline. Use that conservative written time even if another header displays a later one. Time estimates below are planning allowances, not measured delivery promises; account for rest and venue constraints.

The strongest plausible demo is a complete **“Can I afford this, and what would make it work?”** flow:

1. Load a clearly labelled synthetic or Nessie-backed account. Normalize history, infer recurring income/bills, and show an initial 14-day outlook. Let the user correct uncertain assumptions without entering every transaction.
2. Ask a purchase question through Gemini: “Can I buy these $180 headphones Friday without touching groceries?” Parse to a validated amount, date and protection; show editable interpretation. Deterministic controls remain usable offline.
3. Compare **buy now**, **earliest tested later date**, and **make room**. Use the exact existing solver and supplied permitted actions; display the low point, payday and remaining gap. Do not imply that a forecasted ordinary expense is itself cancellable.
4. Protect or reject changes, replay the selected plan, and show what changes. Include one understandable shock scenario, such as payroll arriving late or an extra expense. Scenario ranges are not probability bands.
5. Make the custom forecasting work inspectable: simple versus neural forecast, source and target, validation result, and experimental status. If the neural candidate loses, keep the baseline operational and demonstrate the learned model honestly in a comparison view. The current public models require further accounting work before they can drive a checking-account forecast.
6. Deploy the coherent flow, retain an offline demo, and prepare a four-minute walkthrough with a clear before/after case and provenance.

This is a polished research prototype, not a fully validated autonomous financial assistant. Real banking execution, learned user-preference policies, reliable cancellation rights, long-term personal adaptation, and calibrated overdraft probabilities are not evidence-backed deadline promises.

## Suggested work allocation

Claude can continue candidate generation, account generation and recurring-event inference while forecasting remains isolated. Once a stable account-to-solver path exists, the frontend/product owner can add purchase scenarios and Gemini interpretation. Forecasting should hand over a stable interface early, so integration does not depend on which architecture wins.

Allocate approximately four hours for the designed architecture comparison, three to four for the natural-language purchase flow, one to two for fixed scenario replay, and several for UX/integration/testing. These can partially overlap across owners but coordination and shared interfaces cannot be parallelized away. Self-supervised transfer is a separate bounded experiment; do not silently consume the final integration reserve.

Recommend a Saturday 22:00 feature freeze, leaving roughly ten hours before the conservative submission target for defects, restart/offline checks, demo assets, rehearsal, submission and rest. This is a recommendation. The older Saturday 18:30 gate is recorded as disputed in Claude's handoff and is not imposed here.

## Do the workstreams conflict?

The requested handoff was read from `/Users/nathanstough/Desktop/VT Hacks/docs/handoffs/2026-09-19_solver-core-handoff.md`. Its next-work list is complementary to this branch:

| Owner / lane | Files and responsibility | Interface with forecasting |
|---|---|---|
| Claude/backend | Existing schema/solver/API; new synthetic account generator, recurrence, candidate generation, Nessie and deployment | Supplies known events, permitted actions, protections and an account history with explicit coverage |
| Frontend/product owner | UI, scenario controls, Gemini purchase interpretation/explanation and presentation | Displays dated point forecasts, assumptions and model/source labels; calls the existing solver path |
| Codex forecasting | `forecasting/`, `docs/forecasting/`, preserved `experiments/residual_forecast/`; acquisition, audits, models, metrics and standalone adapter | Returns dated amounts/provenance plus a copied, validated request and sidecar when accounting prerequisites hold |

The live Codex branch is `codex/spending-forecast` in `/Users/nathanstough/Documents/Codex/worktrees/vthacks-forecast`. It began from committed backend revision `c6ef8fa`; it does not contain other agents' subsequent uncommitted work. It has its own environment, with no shared dependency installation. No core/frontend file was edited, and no merge, push or deploy was performed.

Isolation prevents file collisions, but these design boundaries still need agreement:

- **Avoid double counting.** The history target must exclude whatever is separately scheduled, or the integration must explicitly use a non-overlapping total-flow scenario. Neither public benchmark currently validates residual exclusion.
- **Keep card purchases distinct from checking debits.** IBM does not supply a card-repayment timing model. Its forecasts are rejected by the checking adapter.
- **Keep action generation separate.** Forecasts do not establish which future bill can be skipped, cancelled or deferred. Only the owning candidate generator/user evidence supplies those options.
- **Preserve conditional solver claims.** A proof about the supplied schedule and candidate set is not proof that the forecast will occur.
- **Preserve units.** MoneyData's currency is unverified, and the existing solver's prose uses dollar signs. No cross-currency relabelling is allowed.

Two handoff details were stale when checked against live code: the source checkout is currently on `backend`, not the handoff's `main`; and multiple candidate options may target the same transaction, while the solver enforces at most one **chosen** option. See `docs/api-contract.md` and current schema/engine rather than copying the older stronger restriction into new candidate generation. The source worktree has also changed since that handoff; inspect live state before merging.

The newest source `CLAUDE.md` contains both a worktree-first statement and a preference for a shared checkout with a worktree escape hatch. Nathan explicitly requested branch/worktree isolation for concurrent agents here, which matches that escape hatch. Continue using the dedicated forecast checkout; do not switch the branch underneath Claude.

## Related designs

- `architecture-bakeoff.md`: MLP, TCN, GRU and required tiny Transformer, with simple controls and a fresh final test.
- `transfer-learning-design.md`: matched scratch-versus-pretraining comparisons, source balance, and why current logs do not support recommendation RL.
- `model-card.md`: completed v1 evidence and the actual limitations of saved models.
