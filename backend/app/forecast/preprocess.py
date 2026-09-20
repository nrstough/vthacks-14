"""Turn a daily history into the arrays the checkpoints expect.

A transcription of `forecasting/v3/corpus.py::_scale_and_raw` and
`transform_input_arrays`, in NumPy alone. Like the forward pass, it is only
safe because `tools/forecast_parity.py` checks it against the original.

The shape of it: the history is divided by the account's OWN typical
positive day, so the model never sees a currency. What it does see, in one
of the 43 auxiliary features, is the log of that scale against a reference
for the account's source, currency and channel — and a reference exists for
exactly five profiles. That single feature is why a US checking history has
no supported profile.
"""

from __future__ import annotations

import json

import numpy as np

CONTEXT, HORIZON, AUXILIARY = 56, 14, 43

# Unix day 0 is a Thursday, and the reference adds 3 so that Monday is 0.
_MONDAY_OFFSET = 3


def unix_day(day) -> int:
    return day.toordinal() - 719163


def scale_and_raw(
    history: np.ndarray,
    origins: np.ndarray,
    fallbacks: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (sequence N x 56 x 3, raw auxiliary N x 43, scale N).

    `fallbacks` is the per-row reference for its profile. `origins` is the
    Unix day number of the FIRST forecast day.
    """
    history = np.asarray(history, dtype=np.float64)
    origins = np.asarray(origins, dtype=np.int64)
    n = len(history)
    if history.shape != (n, CONTEXT) or origins.shape != (n,):
        raise ValueError("history must be N x 56 with one origin each")
    if not np.isfinite(history).all() or (history < 0).any():
        raise ValueError("history must be finite and non-negative")
    fallbacks = np.asarray(fallbacks, dtype=np.float64)
    if fallbacks.shape != (n,) or not np.isfinite(fallbacks).all() or (fallbacks <= 0).any():
        raise ValueError("each row needs a positive profile reference")

    positive = history > 0
    count = positive.sum(axis=1)
    positive_mean = np.divide(history.sum(axis=1), count, out=np.zeros(n), where=count > 0)
    scale = np.where(count > 0, positive_mean, fallbacks)

    past = (origins[:, None] + np.arange(-CONTEXT, 0) + _MONDAY_OFFSET) % 7
    future = (origins[:, None] + np.arange(HORIZON) + _MONDAY_OFFSET) % 7
    # Eight, always: 56 days is exactly eight of each weekday, so this is a
    # per-weekday mean written as a fixed divisor.
    weekday = np.stack([(history * (past == d)).sum(1) / 8 for d in range(7)], axis=1)
    weekday_future = np.take_along_axis(weekday, future, axis=1)

    sequence = np.stack(
        (history / scale[:, None], np.sin(2 * np.pi * past / 7), np.cos(2 * np.pi * past / 7)),
        axis=-1,
    )
    auxiliary = np.concatenate(
        (
            weekday_future / scale[:, None],
            np.sin(2 * np.pi * future / 7),
            np.cos(2 * np.pi * future / 7),
            np.log1p(positive_mean / fallbacks)[:, None],
        ),
        axis=1,
    )
    return sequence, auxiliary, scale


def transform(
    history: np.ndarray,
    origins: np.ndarray,
    fallbacks: np.ndarray,
    feature_mean: np.ndarray,
    feature_std: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = np.asarray(feature_mean, dtype=np.float64)
    std = np.asarray(feature_std, dtype=np.float64)
    if mean.shape != (AUXILIARY,) or std.shape != (AUXILIARY,) or (std <= 0).any():
        raise ValueError("invalid feature standardiser")
    sequence, auxiliary, scale = scale_and_raw(history, origins, fallbacks)
    # The anchored checkpoints add the person's NORMALISED weekday baseline to
    # their output. It is already here: the first 14 raw auxiliary columns are
    # exactly `weekday_future / scale`. Returning that slice rather than
    # recomputing it is what stops a second definition drifting from this one.
    #
    # Note it is the same-weekday eight-week MEAN, not the 60th percentile the
    # product displays. The models were trained against the mean.
    baseline = auxiliary[:, :HORIZON].copy()
    auxiliary = (auxiliary - mean) / std
    if not np.isfinite(sequence).all() or not np.isfinite(auxiliary).all():
        raise ValueError("non-finite transformed input")
    return sequence, auxiliary, scale, baseline


def normalisation(metadata: dict) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """The standardiser and profile references the checkpoint carries."""
    state = metadata["normalization"]
    return (
        np.asarray(state["feature_mean"], dtype=np.float64),
        np.asarray(state["feature_std"], dtype=np.float64),
        {key: float(value) for key, value in state["source_fallback"].items()},
    )


def profile_key(source: str, currency: str, channel: str) -> str:
    return json.dumps([source, currency, channel], separators=(",", ":"))
