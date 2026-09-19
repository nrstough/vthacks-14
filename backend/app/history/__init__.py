"""Plan from a person's own bank export, storing nothing.

The order of operations matters and is the whole of this module:

  filter -> history bounds -> detect -> project -> residual -> assume
         -> candidates from DETECTED ROWS ONLY -> relabel -> provenance

Two of those steps exist because of a specific failure they prevent.

`candidates from detected rows only` is the guard that stops the solver
offering to skip spending that has not happened. An assumed row is
`discretionary` and matches no keyword, which is exactly the shape the
candidate generator turns into "Skip this charge" — so if assumed rows were
ever passed to it, the product would tell someone to cancel a number it had
invented on their behalf.

`relabel` is the guard that stops a private statement leaking. The generator
reproduces the merchant descriptor verbatim in a candidate's detail, and picks
its brand for the label, so a row that reached the response would carry the
person's real payees into every later solve request, the chat request sent to
Gemini, and any validation error body. Detection needs the raw text; nothing
downstream does.
"""

from __future__ import annotations

import datetime

from app.candidates import generate
from app.schemas import (
    Candidate,
    CandidatesRequest,
    ImportRequest,
    IMPORT_LOOKBACK_DAYS,
    MAX_FREE,
    MAX_SCHED,
    ScheduledTxn,
)

from .detect import Row, detect_streams
from .errors import ImportRefused
from .labels import candidate_detail, candidate_label
from .payee import payee_key
from .project import project
from .residual import (
    ASSUMED_DESCRIPTION,
    ASSUMED_PREFIX,
    CONTEXT_DAYS,
    WEEKS,
    assumed_rows,
    daily_outflow,
)

STALE_AFTER_DAYS = 7
# Fewer rows than this is not a history: there is no rhythm to find and no
# spending to summarise, and answering "sufficient" over one transaction is
# worse than refusing.
MIN_ROWS = 10


__all__ = ["ImportRefused", "import_account"]


def is_assumed(txn_id: str) -> bool:
    """THE guard. Assumed rows never reach the candidate generator.

    Named rather than inlined so a test can take it away and prove the
    generator really would offer to cancel spending that does not exist.

    The second guard, the label-map equality below, is a bare `assert` and is
    therefore removed by `python -O`. The service is not run that way today
    (`deploy/overdraft-guard.service` starts plain uvicorn), and it must not
    be: with both guards gone, an assumed row reaching the generator is
    silent rather than loud.
    """
    return txn_id.startswith(ASSUMED_PREFIX)


def _filtered(req: ImportRequest, as_of: datetime.date) -> tuple[list[Row], list[dict]]:
    oldest = as_of - datetime.timedelta(days=IMPORT_LOOKBACK_DAYS)
    kept: list[Row] = []
    rejected: list[dict] = []
    for index, raw in enumerate(req.rows):
        day = datetime.date.fromisoformat(raw.date)
        if day > as_of:
            rejected.append({"index": index, "reason": "after_as_of"})
            continue
        if day < oldest:
            rejected.append({"index": index, "reason": "older_than_3_years"})
            continue
        kept.append(Row(index, day, raw.amount_cents, raw.description, payee_key(raw.description)))
    return kept, rejected


def import_account(req: ImportRequest, today: datetime.date) -> dict:
    as_of = datetime.date.fromisoformat(req.as_of) if req.as_of else today
    horizon_end = as_of + datetime.timedelta(days=req.horizon_days - 1)

    rows, rejected = _filtered(req, as_of)
    if not rows:
        raise ImportRefused(
            "No usable history. Every row is either dated in the future or more than three years old."
        )
    if len(rows) < MIN_ROWS:
        raise ImportRefused(
            f"Only {len(rows)} usable transactions. That is not enough history to plan from."
        )

    history_start = min(r.date for r in rows)
    history_end = max(r.date for r in rows)
    history_days = (history_end - history_start).days + 1

    streams, unscheduled = detect_streams(rows, history_end)

    scheduled: list[dict] = []
    stream_models: list[dict] = []
    category_by_txn: dict[str, str] = {}
    raw_sample_by_txn: dict[str, str] = {}
    used_indexes: set[int] = set()
    withheld_today: list[str] = []
    income_dates: list[datetime.date] = []
    pay_cadence: str | None = None
    best_income = -1

    for number, stream in enumerate(streams, start=1):
        stream_id = f"s_{number:03d}"
        # Every stream's rows leave the residual, lapsed or not: a rent payment
        # that stopped last month is not everyday spending, and leaving it in
        # would spread it across the horizon as invented discretionary charges.
        used_indexes.update(r.index for r in stream.rows)

        projected, withheld = project(stream, as_of, horizon_end)
        if withheld:
            withheld_today.append(stream_id)

        projected_ids: list[str] = []
        for seq, (_unused, day, amount) in enumerate(projected, start=1):
            txn_id = f"t_{stream_id}_{seq:02d}"
            projected_ids.append(txn_id)
            scheduled.append(
                {
                    "id": txn_id,
                    "date": day.isoformat(),
                    "description": stream.label,
                    "amount_cents": amount,
                    "kind": stream.kind,
                    "recurring": True,
                }
            )
            category_by_txn[txn_id] = stream.category
            raw_sample_by_txn[txn_id] = stream.rows[-1].description
            if stream.kind == "income":
                income_dates.append(day)

        if stream.kind == "income" and stream.active and stream.occurrences > best_income:
            best_income, pay_cadence = stream.occurrences, stream.cadence

        stream_models.append(
            {
                "id": stream_id,
                "kind": stream.kind,
                "label": stream.label,
                "category": stream.category,
                "cadence": stream.cadence,
                "anchor": stream.anchor,
                "amount_cents": stream.amount_cents,
                "occurrences": stream.occurrences,
                "last_seen": stream.last_seen.isoformat(),
                "active": stream.active,
                "source_row_indexes": sorted(r.index for r in stream.rows),
                "projected_ids": projected_ids,
            }
        )

    if len(scheduled) > MAX_SCHED:
        raise ImportRefused(
            f"This history projects {len(scheduled)} recurring charges into the window, "
            f"more than the {MAX_SCHED} this service plans over. Try a shorter horizon."
        )

    series, imputed = daily_outflow(rows, used_indexes, history_start, history_end)
    assumed = assumed_rows(series, history_end, as_of, horizon_end) if history_days >= CONTEXT_DAYS else []

    # Assumed rows are the ones that give way when the window is full: they are
    # an estimate, and a detected charge is a fact about the person's account.
    room = MAX_SCHED - len(scheduled)
    truncated = max(0, len(assumed) - room)
    assumed = assumed[: max(room, 0)]

    assumed_ids = [txn_id for txn_id, _d, _a in assumed]
    for txn_id, day, amount in assumed:
        scheduled.append(
            {
                "id": txn_id,
                "date": day.isoformat(),
                "description": ASSUMED_DESCRIPTION,
                "amount_cents": amount,
                "kind": "discretionary",
                "recurring": False,
            }
        )

    scheduled.sort(key=lambda t: (t["date"], t["id"]))

    # ---- candidates, from detected rows only ----
    detected_rows = [t for t in scheduled if not is_assumed(t["id"])]
    assert {t["id"] for t in detected_rows} == set(category_by_txn), "the label map and the rows drifted apart"
    probe = [
        ScheduledTxn.model_validate({**t, "description": raw_sample_by_txn[t["id"]]}) for t in detected_rows
    ]
    generated = generate(
        CandidatesRequest.model_validate(
            {
                "as_of": as_of.isoformat(),
                "horizon_end": horizon_end.isoformat(),
                "scheduled": [t.model_dump() for t in probe],
                "limit": MAX_FREE,
            }
        )
    )

    candidates: list[dict] = []
    for candidate in generated.candidates:
        category = category_by_txn[candidate.target_txn_id]
        candidates.append(
            {
                **candidate.model_dump(),
                "label": candidate_label(candidate.action, category),
                "detail": candidate_detail(candidate.action, category, candidate.freed_cents),
            }
        )
    # Relabelling can collide where the brand used to separate two rows of the
    # same category. Ids stay unique; the words get a date so the list reads.
    seen: dict[str, int] = {}
    for item in candidates:
        seen[item["label"]] = seen.get(item["label"], 0) + 1
    repeats = {label for label, n in seen.items() if n > 1}
    for item in candidates:
        if item["label"] in repeats:
            item["label"] = f"{item['label']} on {item['effective_date'][5:]}"

    next_payday = min((d for d in income_dates if d >= as_of), default=None)
    stale_days = max(0, (as_of - history_end).days)

    return {
        "as_of": as_of.isoformat(),
        "horizon_end": horizon_end.isoformat(),
        "opening_balance_cents": req.opening_balance_cents,
        "buffer_cents": req.buffer_cents,
        "scheduled": scheduled,
        "candidates": candidates,
        "meta": generated.meta.model_dump(),
        "source": "import",
        "streams": stream_models,
        "provenance": {
            "history_start": history_start.isoformat(),
            "history_end": history_end.isoformat(),
            "history_days": history_days,
            "imputed_zero_days": imputed,
            "rows_used": len(rows),
            "weeks_used_for_assumed": WEEKS if assumed else None,
            "assumed_method": "same_weekday_8_week_median" if assumed else None,
            "assumed_ids": assumed_ids,
            "next_payday": next_payday.isoformat() if next_payday else None,
            "pay_cadence": pay_cadence,
            "income_not_counted_today": withheld_today,
            "stale_days": stale_days,
            "unscheduled_inflow_count": len(unscheduled),
            "unscheduled_inflow_cents": sum(r.amount_cents for r in unscheduled),
            "truncated_assumed_rows": truncated,
            "rejected_rows": rejected,
        },
    }
