# Authorized v2 execution

Nathan authorized both proposed workstreams on September 19, 2026: execute the tiny Transformer/SSL study on IBM, and acquire/audit a real multi-account alternative to blocked Nedbank. This execution plan makes the prior design operational. It does not authorize editing Claude's solver, API or frontend, deploying, or spending on cloud hardware.

## Ownership and sequence

All work stays on `codex/spending-forecast`, in the isolated forecasting worktree. Existing v1 data, model results, predictor and adapter remain unchanged. Parent owns v2 policy, IBM preparation, orchestration, reports and packaging. A model agent owns new sequence model/training modules and their tests. A data agent owns Berka acquisition/preparation and its tests. An independent reviewer checks splits, masking, transfer, metrics and serialization.

1. Create a private Python 3.11 environment (already installed locally; chosen instead of the design's example 3.12) with official PyPI dependencies. Freeze v2 policy and concrete IBM split manifest before training. Preserve the v1 IBM customer hash salt.
2. Acquire Berka through its official research repository; retain source evidence, original fields, checksums and redistribution uncertainty. Freeze its own grouping/date policy after source audit and before any training. Unknown currency remains native units and blocks currency-dependent product integration, but not within-source research comparisons.
3. Run numeric dataset validation. Exclude MoneyData entirely from this execution. Instantiate and freeze actual parameter counts and timing pilots for MLP, TCN, GRU and Transformer, each under 50,000 parameters; run three seeds each. DLinear is omitted before seeing scores to keep scope on required models and SSL.
4. Compare the IBM Transformer trained from scratch with IBM masked-history pretraining then forecast fitting. Add an update-matched scratch control. If Berka passes audit, run the four-architecture comparison there and compare real-only SSL, IBM SSL transfer, IBM forecast transfer, and update-matched scratch. All transfer experiments reset the forecast head and use Berka training-only normalization. Later-calendar IBM to 1990s Berka is explicitly retrospective transfer.
5. Save validation selections before final test, then measure the frozen selections on their designated test periods. Retain seed-level results, update/example counts, timing, source hashes, checkpoints, predictions and conditional group-bootstrap intervals. No re-selection on test. Neither source establishes present-day US student population validity.
6. Run required checks, independent review, document results and limits, package source/run artifacts without redistributing Berka raw data while its redistribution terms remain unresolved, and commit only owned paths.

Training budgets and exact settings are in `forecasting/evaluation-v2.json`. Per-model caps are limits, not promises. A capped or failed run is reported, not silently dropped. The existing application default is unchanged even if a research model wins.

## Checks

- New sequence and Berka tests run in `forecasting/.venv-sequence`.
- Existing forecasting tests run in the original `forecasting/.venv` with both project root and `backend` on `PYTHONPATH`; sequence-only tests require the new environment.
- Full backend regression gate follows the repository README: `python -m pytest backend -q -m 'not perf'`, using the existing backend-compatible environment. Frontend lint/build is unnecessary because no frontend files change.
- Validate exact source/processed hashes, finite shapes, correct chronological/customer grouping, no hidden-value leakage through SSL normalization, all three seeds, exact prediction replay after safe serialization, and independent metrics recomputation.

Raw/prepared data and models are ignored by Git; retention and archive hashes must be delivered with the final results. Do not clean either environment or run directory during this task.
