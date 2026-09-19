# Spending forecasting workstream

This directory is owned by the Codex forecasting workstream on branch `codex/spending-forecast`.

Read [the goal and acceptance criteria](../docs/forecasting/goal.md) before implementing changes.

Status: public-source v1 benchmark complete. IBM synthetic card histories and MoneyData's single-person posted ledger were acquired, audited, and evaluated. Both selected neural candidates failed the promotion gate; saved defaults are the validation-selected baselines. All artifacts remain experimental. Nedbank download access is pending user verification/terms steps. A four-architecture v2 comparison, including the requested tiny Transformer, is designed but not implemented or run.

The existing backend/frontend and frozen API remain dependencies. New implementation, tests, environment, and local data live here; workstream documentation lives in `docs/forecasting/`.

## Read first

- [Results and model card](../docs/forecasting/model-card.md)
- [Data audit](../docs/forecasting/data-audit.md) and [source provenance](../docs/forecasting/acquisition.md)
- [Standalone solver adapter](../docs/forecasting/adapter.md)
- [Architecture bake-off design](../docs/forecasting/architecture-bakeoff.md)

## Reproduce

Use Python 3.14 and an isolated environment. Run from this worktree's root:

```sh
python3 -m venv forecasting/.venv
forecasting/.venv/bin/python -m pip install -r forecasting/requirements.txt
forecasting/.venv/bin/python -m forecasting.acquire ibm
forecasting/.venv/bin/python -m forecasting.acquire moneydata
forecasting/.venv/bin/python -m forecasting.prepare --source ibm
forecasting/.venv/bin/python -m forecasting.prepare --source moneydata
forecasting/.venv/bin/python -m forecasting.train --source ibm --run-id reproduction-1
forecasting/.venv/bin/python -m forecasting.train --source moneydata --run-id reproduction-1
PYTHONPATH="$PWD:$PWD/backend" forecasting/.venv/bin/python -m pytest forecasting/tests -q
PYTHONPATH="$PWD:$PWD/backend" forecasting/.venv/bin/python -m forecasting.examples.solver_adapter
```

Training refuses an existing run directory or a changed configuration/data/audit fingerprint. Keep the original `public-v1` results; exact reproduction is not a new independent holdout. Do not tune using its final test. `forecasting.acquire` uses only the standard library; the full reproduction environment needs NumPy, pandas, and the adapter's backend dependencies. The initial setup installed from the existing read-only local wheel cache and did not modify any other agent's environment.

## Predict

```sh
forecasting/.venv/bin/python -m forecasting.predict \
  --model forecasting/artifacts/ibm-public-v1/default.json \
  --history forecasting/artifacts/ibm-public-v1/example-history.json
```

History is JSON `{currency, days}` with exactly 56 consecutive rows containing ISO `date`, nonnegative major-unit `amount`, and `observed: true`. Unknown/missing dates cannot be filled with zero silently. The saved model fixes source, currency, target and version; output contains 14 dated estimates and experimental provenance. Weights are checksum-verified and loaded without pickle.

**Accounting boundary:** the IBM predictor emits `card_spending`, which the adapter rejects as checking-account flow. MoneyData emits `total_posted_outflow` with unknown `SOURCE_NATIVE` currency, also blocked from currency-dependent integration. The runnable solver example uses explicitly synthetic residual assumptions. These benchmarks are research artifacts, not an already validated residual-spending service.
