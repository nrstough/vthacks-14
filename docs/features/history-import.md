# Feature: history import

Living document. Run spec: `docs/specs/2026-09-19_history-import.md`.

## Status: built, on branch `history-import`

`POST /api/accounts/import`, `backend/app/history/`, and an "Import a bank
export" control on the plan tab. Verified in the browser and run once against
a real consented export.

## What is not built, and will not be by this run

- No learned forecaster in the schedule. Everyday spending is an *assumption*
  from the user's own history (same-weekday eight-week median), and the screen
  says so.
- No error bars, no probability of staying above zero.
- No storage. The export is parsed in the browser, sent once, planned, and
  forgotten, like every other request.
- No Plaid or bank connection. A CSV export is the input.
- No balance from the file. Bank exports rarely carry one; the user types
  today's balance.

## What it does

1. **Parse** a bank CSV in the browser: `DATE`, `DESCRIPTION`, `AMOUNT` in any
   column order or case, several amount and date formats, `STATUS` other than
   `Posted` excluded and counted. Descriptions go to the import endpoint and
   nowhere else.
2. **Detect recurring streams** on the server by cadence, not by name. A
   stream is income, a bill, or regular spending — the last decided by the
   lexicon category, because a weekly grocery run recurs but is not a bill.
   Cadences: weekly,
   biweekly, semi-monthly, monthly, with jitter, weekday wobble and amount
   drift. Income tolerates hours-based variation; bills do not. Lapsed streams
   are not projected. Irregular inflows (peer transfers) are reported and
   excluded.
3. **Project** each active stream across the horizon on its cadence and
   weekday, never on a weekend, at the trimmed mean of its last eight amounts.
   Name the next payday.
4. **Split the history by transaction** into stream rows and everything else.
   The everything-else series is observed everyday spending.
5. **Assume everyday spending** per day as that series' same-weekday
   eight-week median, as `discretionary` non-recurring rows with `f_` ids.
   The median, not the mean: one $900 laptop through a mean reappears as
   ~$112 every week on that weekday. Needs 56 days of history.
6. **Generate candidates from detected rows only**, so the solver can never
   propose cancelling spending that has not happened.
7. **Return** a schedule in the frozen contract's shapes plus provenance:
   streams (with cadence, anchor, and the ids they projected), assumed-row
   ids, weeks used, days the export does not mention, `stale_days` as a
   number rather than a flag, unscheduled inflows, truncation.

## Assumptions the screen states

- A quiet day in the export is a zero-spend day (the export is complete).
- Everyday spending is assumed from the last eight weeks, same weekday.
- The plan starts today; the history ends on the last exported day.

## Interfaces

`POST /api/accounts/import` — see `docs/api-contract.md`. `frontend/src/lib/
importCsv.ts` (parse), `frontend/src/lib/history.ts` (request/response
adapters), `frontend/src/components/ProvenancePanel.tsx`.

## Limits

- **Candidates come only from detected outflows, so an account with no
  recurring outflow at all gets none.** The rule is about detection, not
  about bills: a weekly grocery run is detected as regular spending and does
  yield candidates. What produces nothing is an account whose every outflow
  group is irregular in amount.

  That is not hypothetical. On a real consented export (1,060 rows, two
  years) both income streams were found correctly and *no* outflow stream
  was, because every outflow group on that account has an amount coefficient
  of variation between 0.76 and 1.30. The plan is then income plus assumed
  spending, and if it does not clear, the product can only name the outside
  amount — it cannot prescribe, because prescribing would mean inventing a
  charge to cancel. Offering an everyday-spending *lever* the person sets is
  the honest way to close that, and it is not built.
- **Income is projected conservatively, and that is deliberate.** A pay
  period whose payment already appears in the export is never projected
  again, measured against the nominal anchor date. When pay wobbles between
  two weekdays this can push the named payday a few days later than it will
  probably arrive — on the real consented export, to the 29th when the 24th
  is likelier. Late is the safe direction: the failure it produces is a
  warning the person did not need, and the failure the other way is telling
  someone they are fine when they are not.
- Detection is heuristic. The untick list exists because it will be wrong
  sometimes; a wrong stream is one click away from removal.
- The same-weekday median is the forecast the research lane's three-model
  ensemble beat by 0.4% with an interval spanning zero. It is not a stand-in
  for a model; on the evidence available it is the forecast.
- One consented real account has been run locally. That is a check, not a
  validation.
- No request-body size cap is enforced server-side. The 20,000-row limit is a
  schema bound, which rejects after the body is read.
- Everything is in memory for one request. Nothing is stored, so a page
  refresh means importing the file again.
