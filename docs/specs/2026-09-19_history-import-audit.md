### Scorecard

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Plan adherence | Fail | Semimonthly month-end pay can be projected early, violating A3/D4. |
| Scope discipline | Excellent | Changes remain within the import workflow and its verification. |
| Test coverage | Fail | Semimonthly tests miss incorrect dates; required browser screenshot is absent. |
| Review compliance | Acceptable | Referenced Codex findings have corresponding implementation changes and tests. |
| Freeze integrity | Acceptable | Skipped: no P1/P2/P3 hashes present. |
| Regression check | Acceptable | 2,272 backend tests passed; four environmental setup errors. Frontend: 304 passed. |
| Documentation | Excellent | Declared documentation covers the changed behavior and limitations. |
| **Overall** | **Fail** | |

### Commentary

1. **Plan adherence — causes Fail.** [detect.py:235](/Users/nathanstough/Desktop/vthacks-history-import/backend/app/history/detect.py:235) chooses a numeric day-of-month mode instead of preserving a month-end anchor. Reproduced through the import endpoint with equal income payments on April 15/30, May 15, June 1/15/30, 2026—the 15th/month-end pattern with weekend income shifted forward. With `as_of=2026-07-01`, it projects July 15 and **July 30**, rather than July 31. This makes income available a day early. Preserve month-end semantics when fitting anchors, then apply the weekend shift during projection.

2. **Test coverage — causes Fail.** The [detection test](/Users/nathanstough/Desktop/vthacks-history-import/backend/tests/test_history_detect.py:76) accepts any second anchor ≥28; the [projection test](/Users/nathanstough/Desktop/vthacks-history-import/backend/tests/test_history_project.py:135) checks count and spacing, not exact dates. Add endpoint regressions pinning dates for short semimonthly histories across different month lengths and weekend shifts.

3. **Test coverage — additional acceptance gap.** A10 requires browser verification with a screenshot, but the [results](/Users/nathanstough/Desktop/vthacks-history-import/docs/specs/2026-09-19_history-import.md:194) explicitly report none retained. DOM assertions do not verify layout. Retain a screenshot of the imported plan and provenance panel.

4. **Regression check — limits grade to Acceptable; no demonstrated test regression.** Audited HEAD `ec54b18` on `history-import` in the supplied worktree. Python 3.14.7: `.venv/bin/pytest backend/ -q -p no:cacheprovider --capture=sys` produced **2,272 passed, 10 deselected, four setup errors**, all from unavailable writable temporary directories. Node 22.17.1: `npm run lint && npm test` passed all **304 tests**; both TypeScript projects passed no-emit checks. A fresh production build was not run because the filesystem is read-only; bundle tests used the existing build.
