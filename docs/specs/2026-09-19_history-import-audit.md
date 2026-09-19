### Scorecard

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Plan adherence | Fail | Reproduced omitted bills and incorrect semi-monthly anchors. |
| Scope discipline | Excellent | Changes remain within the import feature and supporting integration. |
| Test coverage | Fail | Projection defects escape tests; required browser screenshot missing. |
| Review compliance | Fail | Review finding 3’s balance cutoff remains incorrect for split merchant streams. |
| Freeze integrity | Acceptable | Skipped: no P1/P2/P3 hashes present. |
| Regression check | Acceptable | 2,258 backend passes; four environmental setup errors. Frontend: 295 passes. |
| Documentation | Fail | Incorrect privacy disclosure and substantive feature limitation. |
| **Overall** | **Fail** | |

### Commentary

1. **Plan adherence — causes Fail.** [project.py:65](/Users/nathanstough/Desktop/vthacks-history-import/backend/app/history/project.py:65) stops generating monthly occurrences before accounting for weekend shifts. With `as_of=2026-10-18` and a 14-day horizon, a November 1 bill should move to Friday, October 30, but disappears. Reproduced through the endpoint: a $1,000 rent stream produced an empty schedule and tier 1 with only $500 available. Generate adjacent occurrences before shifting and clipping; add an endpoint regression test.

2. **Plan adherence / Review compliance — causes Fail.** [project.py:101](/Users/nathanstough/Desktop/vthacks-history-import/backend/app/history/project.py:101) suppresses today’s bills by **payee**, rather than stream membership. Two detected subscriptions at one merchant, $15.99 and $22.99, both disappear when only the $15.99 subscription posted today. This violates D13/A16 and leaves review finding 3 incompletely resolved. Check whether the particular stream contains a posted-today row; test both subscriptions together.

3. **Plan adherence — causes Fail.** [detect.py:231](/Users/nathanstough/Desktop/vthacks-history-import/backend/app/history/detect.py:231) calculates semi-monthly modes from deduplicated day clusters, losing occurrence frequencies. A fixture paying predominantly on the 15th, with isolated 16th/17th occurrences, anchors to the 17th. It also retains those old deviations despite recent occurrences returning to the 15th. Compute anchors from actual recent occurrences and add a jittered semi-monthly test.

4. **Test coverage — causes Fail.** A10 requires a retained browser screenshot covering render-level verification. The [results record](/Users/nathanstough/Desktop/vthacks-history-import/docs/specs/2026-09-19_history-import.md:191) explicitly says no image was kept and does not record the required offline-message check. Repeat that browser verification and retain its evidence.

5. **Documentation — causes Fail.** [ProvenancePanel.tsx:84](/Users/nathanstough/Desktop/vthacks-history-import/frontend/src/components/ProvenancePanel.tsx:84) tells users, “Merchant names stayed in your browser.” Raw descriptions are sent to the import endpoint. Replace this substantive privacy misstatement with an accurate explanation of server processing and omission from returned schedules.

6. **Documentation — contributes to Fail.** [history-import.md:66](/Users/nathanstough/Desktop/vthacks-history-import/docs/features/history-import.md:66) states that accounts without recurring bills cannot receive candidates. Reproduced counterexample: ten weekly grocery transactions yield one `discretionary` stream and four candidates, with no bills. Describe the limitation in terms of eligible detected outflows, and distinguish that rule from the particular consented account’s result.

7. **Regression check — limits grade to Acceptable; no demonstrated existing-test regression.** On `history-import` in the supplied worktree, Python 3.14.7 ran `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest backend/ -q --capture=sys -p no:cacheprovider --tb=short`: **2,258 passed, 10 deselected, four setup errors** caused by unavailable writable temporary directories. Node 22.17.1 ran the frontend suite: **295 passed**; lint and both TypeScript project checks passed. A fresh production build was not run because the sandbox is read-only; bundle tests inspected the existing build.
