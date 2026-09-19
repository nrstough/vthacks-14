### Scorecard

| Dimension | Grade | Notes |
|-----------|-------|-------|
| Plan adherence | **Fail** | Balance cutoff and cadence requirements have reproducible violations. |
| Scope discipline | Excellent | Changes remain within the import feature and its supporting integration. |
| Test coverage | **Fail** | Tests miss both defects below; required screenshot evidence is unavailable. |
| Review compliance | **Fail** | Codex findings 2 and 3 remain incompletely resolved. |
| Freeze integrity | Acceptable | Skipped: no P1/P2/P3 hashes present. |
| Regression check | Acceptable | 2275 backend tests passed; four environmental setup errors. Frontend: 304 passed. |
| Documentation | Acceptable | Declared documentation updated; minor internal wording drift. |
| **Overall** | **Fail** | Two confirmed defects can introduce income that should not be projected. |

### Commentary

1. **Plan adherence, Review compliance, Test coverage — causes Fail.**  
   [project.py:116](/Users/nathanstough/Desktop/vthacks-history-import/backend/app/history/project.py:116) suppresses income only when its **projected date** equals `as_of`. A paycheck posted early can therefore be counted again. Reproducer: nine Friday payments followed by the next payment posted Thursday, September 10; import with `as_of=2026-09-10` and a balance already including that payment. The endpoint projects another **50,000 cents on September 11**, with no withheld-income provenance. This violates the posted-today safeguard in A16 and leaves review finding 3 unresolved. Match historical occurrences to their cadence periods before projecting; add early-posting tests for weekly and biweekly income.

2. **Plan adherence, Review compliance, Test coverage — causes Fail.**  
   [detect.py:277](/Users/nathanstough/Desktop/vthacks-history-import/backend/app/history/detect.py:277) calculates semimonthly coverage using only months containing transactions. Missing months disappear from the denominator, contrary to the review amendment requiring coverage across the stream’s span. Six equal inflows on January 15/30, May 15/29, and September 15/30 are classified as active semimonthly income. An October 1 import projects **50,000 cents on both October 15 and October 30**, reporting zero unscheduled inflows. Count every month in the span and reject unsupported gaps; add this sparse-history counterexample.

3. **Test coverage — contributes to Fail.**  
   A10 requires browser verification with a screenshot, but the [run results](/Users/nathanstough/Desktop/vthacks-history-import/docs/specs/2026-09-19_history-import.md:194) explicitly retain only DOM assertions. Capture reviewable screenshot evidence for the panel, untick interaction, and offline behavior.

4. **Regression check — limits grade to Acceptable; no demonstrated suite regression.**  
   On `history-import` at `fd3ef29`, Python 3.14.7 ran `.venv/bin/pytest backend/ -q --capture=sys -p no:cacheprovider` with bytecode writes disabled: **2275 passed, 10 deselected, four setup errors**, all caused by unavailable writable temporary directories. Node 22.17.1 ran frontend lint and **304 passing tests**. Both TypeScript configurations passed with `--noEmit --incremental false`. A fresh Vite build was not run under the read-only restriction; bundle tests used existing build artifacts.

5. **Documentation — limits grade to Acceptable, not Fail.**  
   [import_local.py:32](/Users/nathanstough/Desktop/vthacks-history-import/backend/tools/import_local.py:32) still calls its amount parser “The browser’s grammar,” although the browser now rejects malformed signs and separators that this script accepts. Correct that internal description or align the parsers. The declared feature and API documentation otherwise covers the changed behavior.
