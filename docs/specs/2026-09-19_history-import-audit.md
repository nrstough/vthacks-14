### Scorecard

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Plan adherence | Fail | Projection, parsing, and provenance defects remain. |
| Scope discipline | Excellent | Changes stay within the import feature and supporting infrastructure. |
| Test coverage | Fail | Passing tests miss reproduced defects; A10 screenshot evidence is absent. |
| Review compliance | Excellent | Referenced Codex findings have corresponding fixes and tests. |
| Freeze integrity | Acceptable | Skipped: no P1/P2/P3 hashes supplied. |
| Regression check | Acceptable | 2261 backend tests passed; four environmental setup errors. Frontend: 295 passed, lint clean. |
| Documentation | Fail | Documented lapse and balance-cutoff rules contradict implementation. |
| **Overall** | **Fail** | |

### Commentary

1. **Plan adherence — causes Fail.** [Weekly projection](/Users/nathanstough/Desktop/vthacks-history-import/backend/app/history/project.py:38) clips nominal dates before weekend shifting. Reproduced: a Sunday bill projected through Friday October 2 omits the October 4 occurrence that should move into October 2. Saturday income with `as_of=2026-09-20` similarly omits Monday September 21. Generate dates beyond both window boundaries, shift them, then clip. Add weekly and biweekly boundary tests.

2. **Plan adherence — contributes to Fail.** [CSV status filtering](/Users/nathanstough/Desktop/vthacks-history-import/frontend/src/lib/importCsv.ts:175) accepts blank statuses when a `STATUS` column exists, contrary to D11/A1. Ten blank-status rows produced ten usable transactions and zero exclusions. Require `Posted` whenever that column is present; test blank and missing cells.

3. **Plan adherence — contributes to Fail.** [Payday provenance](/Users/nathanstough/Desktop/vthacks-history-import/backend/app/history/__init__.py:155) selects cadence from the income stream with most occurrences, independently of the next payday. A two-employer reproduction returned September 18 with `weekly`, although that payment belonged to the biweekly employer. Derive date and cadence from the same projected occurrence.

4. **Plan adherence — contributes to Fail.** Provenance conflates zero residual spending with insufficient history. A reproduced 71-day history containing eleven recurring bills returned `assumed_method: null`, triggering [“Not enough history”](/Users/nathanstough/Desktop/vthacks-history-import/frontend/src/lib/history.ts:153). It also reported all 71 days as “nothing spent” because [the zero-day count](/Users/nathanstough/Desktop/vthacks-history-import/backend/app/history/residual.py:50) is computed after removing bills. Distinguish insufficient history, zero medians, and truncation; count quiet days from the original history or explicitly label residual-only days.

5. **Test coverage — causes Fail.** Existing tests pass despite findings 1–4. A10 also explicitly requires a browser screenshot; the run spec records that none was retained. Add regression cases for these reproductions and retain the required browser evidence.

6. **Documentation — causes Fail.** D3 specifies lapse after two intervals, but [income detection](/Users/nathanstough/Desktop/vthacks-history-import/backend/app/history/detect.py:43) uses three; this deviation is not recorded in the run spec’s deviation list. Additionally, [the API contract](/Users/nathanstough/Desktop/vthacks-history-import/docs/api-contract.md:442) describes posted-today suppression by **payee**, while implementation correctly suppresses by **stream**. These rules affect whether income or bills enter the schedule. Reconcile the documented rules and explicitly record the intended lapse policy.

7. **Regression check — Acceptable due to verification limits, not demonstrated regressions.** Audited `25212e1`, branch `history-import`, in the supplied worktree. Python 3.14.7: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest backend/ -q --capture=sys -p no:cacheprovider` yielded **2261 passed, 10 deselected, four setup errors**, all caused by unavailable writable temporary directories. Node 22.17.1: `npm run lint && npm test` yielded clean lint and **295 passed**. A fresh production build was not performed under read-only permissions; frontend bundle tests used the existing build.
