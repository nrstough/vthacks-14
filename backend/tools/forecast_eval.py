"""Score the checkpoints against the weekday baseline on ONE real account.

    SAFE_TO_SPEND_CSV=~/Downloads/Checking-2.csv .venv/bin/python backend/tools/forecast_eval.py

What it does: takes the everyday-spending series the import already
computes (the history with every detected recurring stream removed), rolls
a 56-day context and a 14-day target across it, and compares each model's
14-day total against the same-weekday eight-week median the product ships.

What it is NOT: validation. One account, overlapping windows, and a profile
none of these models was trained on. The profile is the sharp end — the
models take a reference for their source, currency and channel, five exist,
and a US checking account is not one of them. This runs each candidate
reference and reports the spread, because the spread is the finding.
"""

from __future__ import annotations

import csv
import datetime
import json
import os
import re
import statistics
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from app.forecast import preprocess, runtime  # noqa: E402
from app.history.detect import Row, detect_streams  # noqa: E402
from app.history.payee import payee_key  # noqa: E402
from app.history.residual import daily_outflow  # noqa: E402

ARTIFACTS = Path("/Users/nathanstough/Documents/Codex/worktrees/vthacks-forecast/forecasting/artifacts")
CHECKPOINTS = ARTIFACTS / "forecast-v3/runs"
FOLLOWUP = ARTIFACTS / "forecast-small-followup/runs"
CONTEXT, HORIZON = 56, 14


def cents(raw: str) -> int | None:
    text = raw.strip()
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1].strip()
    text = re.sub(r"[$,\s]", "", text)
    if text.startswith("-"):
        negative, text = not negative, text[1:]
    if not re.fullmatch(r"\d*(\.\d{0,2})?", text) or text in ("", "."):
        return None
    whole, _, fraction = text.partition(".")
    value = int(whole or 0) * 100 + int((fraction or "0").ljust(2, "0"))
    return -value if negative else value


def load_rows(path: str) -> list[Row]:
    out: list[Row] = []
    with open(os.path.expanduser(path), newline="") as handle:
        for index, record in enumerate(csv.DictReader(handle)):
            keys = {k.strip().lower(): k for k in record if k}
            status = record.get(keys.get("status", ""), "Posted").strip().lower()
            if status not in ("", "posted"):
                continue
            raw_date = record.get(keys.get("date", ""), "")
            amount = cents(record.get(keys.get("amount", ""), ""))
            description = (record.get(keys.get("description", ""), "") or "").strip()
            for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
                try:
                    when = datetime.datetime.strptime(raw_date.strip(), fmt).date()
                    break
                except ValueError:
                    when = None
            if when is None or amount in (None, 0) or not description:
                continue
            out.append(Row(index, when, amount, description, payee_key(description)))
    return out


def weekday_baseline(context: np.ndarray, origin_weekday: int, fraction: float = 0.6) -> np.ndarray:
    """The product's own forecast: the same-weekday 60th percentile.

    The context is ordered oldest-first and is exactly 56 days, so each
    weekday has exactly eight observations. `fraction` is exposed so this
    script can also score the 50th, which is what the product shipped
    before this evaluation moved it.
    """
    out = np.zeros(HORIZON)
    for step in range(HORIZON):
        weekday = (origin_weekday + step) % 7
        # Position 0 of the context is 56 days before the origin.
        positions = [i for i in range(CONTEXT) if (origin_weekday - CONTEXT + i) % 7 == weekday]
        out[step] = float(np.percentile(context[positions], fraction * 100))
    return out


def main() -> int:
    path = os.environ.get("SAFE_TO_SPEND_CSV")
    if not path:
        print("set SAFE_TO_SPEND_CSV", file=sys.stderr)
        return 2

    rows = load_rows(path)
    start, end = min(r.date for r in rows), max(r.date for r in rows)
    streams, _unscheduled = detect_streams(rows, end)
    used = {r.index for s in streams for r in s.rows}
    series, _imputed = daily_outflow(rows, used, start, end)
    days = sorted(series)
    values = np.array([series[d] / 100.0 for d in days], dtype=np.float64)  # dollars
    print(f"account: {len(rows)} rows, {start} to {end} ({len(days)} days)")
    print(f"recurring streams removed: {len(streams)}; residual days with spending: {int((values > 0).sum())}")

    windows = []
    for origin_index in range(CONTEXT, len(days) - HORIZON + 1):
        context = values[origin_index - CONTEXT : origin_index]
        target = values[origin_index : origin_index + HORIZON]
        windows.append((days[origin_index], context, target))
    print(f"rolling windows: {len(windows)} (overlapping, so not independent)")
    if not windows:
        print("not enough history")
        return 1

    history = np.stack([w[1] for w in windows])
    targets = np.stack([w[2] for w in windows])
    origins = np.array([preprocess.unix_day(w[0]) for w in windows], dtype=np.int64)

    baseline = np.stack([weekday_baseline(h, d.weekday(), 0.6) for (d, h, _t) in windows])
    old_baseline = np.stack([weekday_baseline(h, d.weekday(), 0.5) for (d, h, _t) in windows])

    loaded: dict[str, object] = {}
    for size in ("tiny", "small", "medium", "large"):
        for seed in (11, 23, 47):
            p = CHECKPOINTS / f"direct_{size}_seed_{seed}" / "forecast.npz"
            if p.exists():
                loaded[f"direct {size:6s} s{seed}"] = runtime.load_checkpoint(p)
    for size in ("small", "medium", "large"):
        for seed in (11, 23, 47):
            p = FOLLOWUP / f"anchor_prefix_mae_{size}_seed_{seed}" / "forecast.npz"
            if p.exists():
                loaded[f"anchor {size:6s} s{seed}"] = runtime.load_checkpoint(p)

    # Groups scored as equal-weight PREDICTION ensembles. Never "pick the best
    # seed": three seeds are three runs of one recipe differing only in their
    # random start, and choosing among them on the data being scored is
    # selection on the test set.
    groups: dict[str, list] = {}
    for label, checkpoint in loaded.items():
        family, size, _seed = label.split()
        groups.setdefault(f"{family} {size} x3", []).append(checkpoint)
    groups = {k: v for k, v in groups.items() if len(v) == 3}

    reference_metadata = next(iter(loaded.values())).metadata
    mean, std, fallbacks = preprocess.normalisation(reference_metadata)

    def score(predictions: np.ndarray) -> dict:
        daily = np.abs(predictions - targets)
        total = np.abs(predictions.sum(axis=1) - targets.sum(axis=1))
        return {
            "daily_mae": float(daily.mean()),
            "total_mae": float(total.mean()),
            "bias": float((predictions.sum(axis=1) - targets.sum(axis=1)).mean()),
        }

    base = score(baseline)
    was = score(old_baseline)
    under = float((baseline.sum(axis=1) < targets.sum(axis=1)).mean() * 100)
    under_was = float((old_baseline.sum(axis=1) < targets.sum(axis=1)).mean() * 100)
    print(
        f"\nbaseline, same-weekday 60th pct (shipped): daily MAE ${base['daily_mae']:.2f}, "
        f"14-day MAE ${base['total_mae']:.2f}, bias ${base['bias']:+.2f}, under-predicts {under:.0f}% of windows"
    )
    print(
        f"baseline, same-weekday median (was):       daily MAE ${was['daily_mae']:.2f}, "
        f"14-day MAE ${was['total_mae']:.2f}, bias ${was['bias']:+.2f}, under-predicts {under_was:.0f}% of windows"
    )

    print("\nprofile reference       model                 daily MAE   14d MAE     bias    vs baseline")
    print("-" * 94)
    results = {}
    for key in sorted(fallbacks):
        source, currency, channel = json.loads(key)
        reference = np.full(len(windows), fallbacks[key])
        sequence, auxiliary, scale, anchor = preprocess.transform(history, origins, reference, mean, std)
        label_profile = f"{source}/{currency}"
        for label, checkpoint in loaded.items():
            predictions = (
                runtime.forward(checkpoint, sequence, auxiliary, anchor if checkpoint.anchored else None)
                * scale[:, None]
            )
            s = score(predictions)
            results[(key, label)] = s
            delta = (base["total_mae"] - s["total_mae"]) / base["total_mae"] * 100
            print(
                f"{label_profile:22s}  {label:18s}  ${s['daily_mae']:7.2f}  ${s['total_mae']:8.2f}  "
                f"${s['bias']:+8.2f}   {delta:+6.2f}%"
            )
        for label, members in groups.items():
            predictions = runtime.ensemble(members, sequence, auxiliary, anchor) * scale[:, None]
            s = score(predictions)
            results[(key, label)] = s
            delta = (base["total_mae"] - s["total_mae"]) / base["total_mae"] * 100
            print(
                f"{label_profile:22s}  {label:18s}  ${s['daily_mae']:7.2f}  ${s['total_mae']:8.2f}  "
                f"${s['bias']:+8.2f}   {delta:+6.2f}%"
            )
        print()

    print("ensemble spread across the five profile references (the size of the guess):")
    for label in sorted(groups):
        values = [v["total_mae"] for (k, name), v in results.items() if name == label]
        best = (base["total_mae"] - min(values)) / base["total_mae"] * 100
        print(
            f"  {label:18s} ${min(values):7.2f} to ${max(values):7.2f}  "
            f"spread {(max(values) - min(values)) / statistics.mean(values) * 100:4.0f}%  "
            f"best vs baseline {best:+6.2f}%"
        )
    print(
        "\nOne account. Overlapping windows, so the effective sample is far smaller than the"
        f"\nwindow count. No profile here matches this account, which is the point of the spread."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
