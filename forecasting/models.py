"""History-only features, linear baselines, and a small NumPy neural regressor.

Amounts are major currency units. Each training example is scaled independently
using its past, then feature standardization is fit on training examples only.
"""
from __future__ import annotations

import numpy as np

CONTEXT = 56
HORIZON = 14
FEATURES = 99


def features(history: np.ndarray, origins: np.ndarray):
    history = np.asarray(history, dtype=np.float64)
    origins = np.asarray(origins)
    if history.ndim != 2 or history.shape[1] != CONTEXT or not len(history):
        raise ValueError("history must be nonempty N x 56")
    if origins.shape != (len(history),) or origins.dtype.kind not in "iu":
        raise ValueError("origins must be integer Unix-day offsets, one per history")
    if not np.isfinite(history).all() or (history < 0).any():
        raise ValueError("history must contain finite nonnegative outflows")
    scale = np.maximum(history[:, -28:].mean(axis=1), 1.0)
    # Unix day zero was Thursday (Monday=0). Calendar inputs cover all weekdays.
    future_days = (origins[:, None] + np.arange(HORIZON) + 3) % 7
    past_days = (origins[:, None] + np.arange(-CONTEXT, 0) + 3) % 7
    day_means = np.stack([
        np.sum(history * (past_days == d), axis=1) / 8 for d in range(7)
    ], axis=1)
    weekday = np.take_along_axis(day_means, future_days, axis=1)
    x = np.concatenate((history / scale[:, None], weekday / scale[:, None],
                        np.sin(2 * np.pi * future_days / 7),
                        np.cos(2 * np.pi * future_days / 7),
                        np.log1p(scale)[:, None]), axis=1)
    return x, scale, weekday


def initialize(seed: int):
    rng = np.random.default_rng(seed)
    return {
        "w1": rng.normal(0, np.sqrt(2 / FEATURES), (FEATURES, 64)), "b1": np.zeros(64),
        "w2": rng.normal(0, np.sqrt(2 / 64), (64, 32)), "b2": np.zeros(32),
        "w3": rng.normal(0, .03, (32, HORIZON)),
        "b3": np.full(HORIZON, np.log(np.expm1(1.0))),
    }


def forward(x, weights):
    a = np.maximum(x @ weights["w1"] + weights["b1"], 0)
    b = np.maximum(a @ weights["w2"] + weights["b2"], 0)
    z = b @ weights["w3"] + weights["b3"]
    return np.logaddexp(0, z), (a, b, z)


def loss_gradients(x, y, weights):
    prediction, (a, b, z) = forward(x, weights)
    loss = np.mean((prediction - y) ** 2)
    dz = 2 * (prediction - y) / prediction.size / (1 + np.exp(-np.clip(z, -60, 60)))
    db = (dz @ weights["w3"].T) * (b > 0)
    da = (db @ weights["w2"].T) * (a > 0)
    return float(loss), {
        "w3": b.T @ dz, "b3": dz.sum(0), "w2": a.T @ db,
        "b2": db.sum(0), "w1": x.T @ da, "b1": da.sum(0),
    }


def fit_ridge(x, y, alpha):
    design = np.column_stack((x, np.ones(len(x))))
    penalty = np.eye(design.shape[1]) * alpha
    penalty[-1, -1] = 0
    return np.linalg.solve(design.T @ design + penalty, design.T @ y)


def predict_arrays(kind, state, history, origins):
    history = np.asarray(history, dtype=np.float64)
    x, scale, weekday = features(history, origins)
    if kind == "recent_28day_mean":
        predicted = np.repeat(history[:, -28:].mean(1)[:, None], HORIZON, axis=1)
    elif kind == "weekday_8week_mean":
        predicted = weekday
    elif kind in {"ridge", "neural"}:
        normalized = (x - state["feature_mean"]) / state["feature_std"]
        if kind == "ridge":
            values = np.column_stack((normalized, np.ones(len(x)))) @ state["coef"]
            predicted = np.maximum(values, 0) * scale[:, None]
        else:
            predicted = forward(normalized, state)[0] * scale[:, None]
    else:
        raise ValueError(f"unknown model kind: {kind}")
    if not np.isfinite(predicted).all() or (predicted < 0).any():
        raise ValueError("model produced invalid forecast")
    return predicted


def fit_neural(x, y, val_x, val_y, val_scale, seed, config):
    """Select epoch on validation only, returning all epoch scores for audit."""
    rng = np.random.default_rng(seed)
    weights = initialize(seed)
    first = {k: np.zeros_like(v) for k, v in weights.items()}
    second = {k: np.zeros_like(v) for k, v in weights.items()}
    best_score, bad, steps = float("inf"), 0, 0
    history = []
    for epoch in range(1, config["max_epochs"] + 1):
        order = rng.permutation(len(x))
        for start in range(0, len(x), config["batch_size"]):
            ix = order[start:start + config["batch_size"]]
            _, gradients = loss_gradients(x[ix], y[ix], weights)
            norm = np.sqrt(sum(float(np.sum(g * g)) for g in gradients.values()))
            steps += 1
            for key in weights:
                gradient = gradients[key] * min(1, config["gradient_norm_clip"] / max(norm, 1e-12))
                first[key] = .9 * first[key] + .1 * gradient
                second[key] = .999 * second[key] + .001 * gradient ** 2
                weights[key] -= config["learning_rate"] * (first[key] / (1 - .9 ** steps)) / (
                    np.sqrt(second[key] / (1 - .999 ** steps)) + 1e-8)
        prediction = forward(val_x, weights)[0] * val_scale[:, None]
        score = float(np.abs(val_y.sum(1) - prediction.sum(1)).mean())
        if not np.isfinite(score):
            raise ValueError("nonfinite validation score")
        history.append(score)
        if score < best_score:
            best_score, best_epoch, bad = score, epoch, 0
            checkpoint = {k: v.copy() for k, v in weights.items()}
        else:
            bad += 1
        if epoch == 1 or epoch % 5 == 0:
            print(f"seed={seed} epoch={epoch} validation_14day_MAE={score:.4f}", flush=True)
        if bad >= config["patience"]:
            break
    return checkpoint, {"seed": seed, "best_epoch": best_epoch, "epochs_run": epoch,
                        "validation_14day_mae": best_score, "validation_history": history}
