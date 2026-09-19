from datetime import date, timedelta
import hashlib
import json

import numpy as np
import pytest

from forecasting.evaluate import metrics, paired_interval, promotion_decision
from forecasting.models import features, fit_ridge, forward, initialize, loss_gradients, predict_arrays
from forecasting.predict import Predictor


def test_weekday_features_use_correct_dates_and_history_only():
    origin = (date(2026, 9, 21) - date(1970, 1, 1)).days  # Monday
    days = (np.arange(origin - 56, origin) + 3) % 7
    h = (days + 1)[None, :].astype(float)
    x, scale, weekday = features(h, np.array([origin]))
    np.testing.assert_array_equal(weekday, [list(range(1, 8)) * 2])
    assert x.shape == (1, 99) and scale[0] == 4
    for kind in ["recent_28day_mean", "weekday_8week_mean"]:
        np.testing.assert_array_equal(predict_arrays(kind, {}, h.tolist(), [origin]),
                                      predict_arrays(kind, {}, h, np.array([origin])))


def test_all_calendar_start_days_differ_and_zero_history_is_finite():
    x, scale, weekday = features(np.zeros((7, 56)), np.arange(7))
    assert np.isfinite(x).all() and np.all(scale == 1) and np.all(weekday == 0)
    assert len(np.unique(x[:, 70:98], axis=0)) == 7


@pytest.mark.parametrize("history,origin", [
    (np.zeros((1, 55)), np.array([0])), (np.zeros((0, 56)), np.array([], dtype=int)),
    (np.full((1, 56), np.nan), np.array([0])), (np.full((1, 56), -1), np.array([0])),
    (np.zeros((1, 56)), np.array([.5])),
])
def test_invalid_features_rejected(history, origin):
    with pytest.raises(ValueError):
        features(history, origin)


def test_neural_gradient_against_independent_central_difference():
    rng = np.random.default_rng(109)
    p = initialize(42)
    x, y = rng.normal(0, .3, (5, 99)), rng.uniform(0, 2, (5, 14))
    _, grads = loss_gradients(x, y, p)
    for name in p:
        for _ in range(4):
            ix = tuple(rng.integers(size) for size in p[name].shape)
            value, epsilon = p[name][ix], 1e-5
            p[name][ix] = value + epsilon
            plus = np.mean((forward(x, p)[0] - y) ** 2)
            p[name][ix] = value - epsilon
            minus = np.mean((forward(x, p)[0] - y) ** 2)
            p[name][ix] = value
            assert abs(grads[name][ix] - (plus - minus) / (2 * epsilon)) < 1e-6


def test_ridge_unpenalized_intercept_can_predict_constant():
    rng = np.random.default_rng(12)
    x = rng.normal(size=(150, 99))
    coef = fit_ridge(x, np.full((150, 14), 3.), alpha=1e6)
    np.testing.assert_allclose(np.column_stack((x, np.ones(150))) @ coef, 3, atol=1e-10)


def test_metrics_totals_bias_and_underprediction():
    actual = np.full((2, 14), 10.)
    predicted = np.array([[8.] * 14, [11.] * 14])
    assert metrics(actual, predicted) == {
        "daily_mae": 1.5, "7day_total_mae": 10.5, "14day_total_mae": 21.,
        "14day_bias_pred_minus_actual": -7., "14day_mean_underprediction": 14.,
    }


def test_cluster_bootstrap_does_not_pretend_repeated_windows_independent():
    actual = np.full((8, 14), 10.)
    baseline = actual - 2
    neural = actual - 1
    groups = np.repeat(["a", "b"], 4)
    result = paired_interval(actual, baseline, neural, groups, np.arange(8), {"seed": 2, "replicates": 100})
    assert result["groups"] == 2 and result["unit"] == "customer"
    assert result["ci95"] == [14., 14.] and result["paired_improvement"] == 14
    assert promotion_decision(metrics(actual, baseline), metrics(actual, neural), result, representative_real_data=True)["promote_neural"]
    assert not promotion_decision(metrics(actual, baseline), metrics(actual, neural), result, representative_real_data=False)["promote_neural"]
    single = paired_interval(actual, baseline, neural, np.array(["a"] * 8), np.arange(8), {"seed": 2, "replicates": 100})
    assert not promotion_decision(metrics(actual, baseline), metrics(actual, neural), single, representative_real_data=True)["promote_neural"]


def test_promotion_fails_when_underprediction_increases_from_zero():
    actual = np.full((8, 14), 10.)
    base, net = actual + 2, actual - .1
    interval = {"groups": 2, "unit": "customer", "ci95": [1, 2]}
    decision = promotion_decision(metrics(actual, base), metrics(actual, net), interval, representative_real_data=True)
    assert not decision["promote_neural"]
    assert not decision["checks"]["underprediction_within_threshold"]


def fixture_predictor(tmp_path, kind="recent_28day_mean"):
    weights = tmp_path / "weights.npz"
    state = initialize(11) if kind == "neural" else {}
    if kind == "neural":
        state.update(feature_mean=np.zeros(99), feature_std=np.ones(99))
    np.savez_compressed(weights, **state)
    metadata = {"format_version": 1, "context_days": 56, "horizon_days": 14,
                "model_id": "unit-test", "kind": kind, "source": "test fixture", "target": "total_posted_outflow",
                "currency": "USD", "experimental": True, "weights": weights.name,
                "weights_sha256": hashlib.sha256(weights.read_bytes()).hexdigest()}
    model = tmp_path / "model.json"
    model.write_text(json.dumps(metadata))
    history = [{"date": (date(2026, 1, 1) + timedelta(days=i)).isoformat(), "amount": 10., "observed": True} for i in range(56)]
    return model, history


@pytest.mark.parametrize("kind", ["recent_28day_mean", "neural"])
def test_saved_predictor_is_deterministic_and_dated(tmp_path, kind):
    model, history = fixture_predictor(tmp_path, kind)
    one = Predictor(model).predict(history, currency="USD")
    two = Predictor(model).predict(history, currency="USD")
    assert one == two and one["context_end"] == "2026-02-25"
    assert one["days"][0]["date"] == "2026-02-26" and one["days"][-1]["date"] == "2026-03-11"
    assert one["experimental"] is True
    if kind == "recent_28day_mean":
        assert {row["amount"] for row in one["days"]} == {10.}


@pytest.mark.parametrize("corruption", ["missing", "unobserved", "duplicate", "unsorted", "nan", "negative", "boolean", "dateformat", "currency"])
def test_predictor_rejects_corrupt_or_unknown_history(tmp_path, corruption):
    model, history = fixture_predictor(tmp_path)
    currency = "USD"
    if corruption == "missing": history.pop()
    elif corruption == "unobserved": history[10]["observed"] = False
    elif corruption == "duplicate": history[10] = history[9].copy()
    elif corruption == "unsorted": history.reverse()
    elif corruption == "nan": history[10]["amount"] = "nan"
    elif corruption == "negative": history[10]["amount"] = -1
    elif corruption == "boolean": history[10]["amount"] = True
    elif corruption == "dateformat": history[10]["date"] = "20260111"
    elif corruption == "currency": currency = "GBP"
    with pytest.raises(ValueError):
        Predictor(model).predict(history, currency=currency)


def test_changed_weights_fail_checksum(tmp_path):
    model, _ = fixture_predictor(tmp_path)
    (tmp_path / "weights.npz").write_bytes(b"corruption")
    with pytest.raises(ValueError, match="checksum"):
        Predictor(model)


@pytest.mark.parametrize("field,value", [("format_version", 2), ("format_version", True),
                                        ("context_days", 55), ("horizon_days", 7),
                                        ("experimental", "yes"), ("source", ""), ("kind", "unknown")])
def test_incompatible_model_metadata_rejected(tmp_path, field, value):
    model, _ = fixture_predictor(tmp_path)
    metadata = json.loads(model.read_text())
    metadata[field] = value
    model.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        Predictor(model)


def test_invalid_standardizer_rejected_even_with_valid_checksum(tmp_path):
    model, _ = fixture_predictor(tmp_path, "neural")
    weights = tmp_path / "weights.npz"
    with np.load(weights) as loaded:
        state = dict(loaded)
    state["feature_std"][0] = 0
    np.savez_compressed(weights, **state)
    metadata = json.loads(model.read_text())
    metadata["weights_sha256"] = hashlib.sha256(weights.read_bytes()).hexdigest()
    model.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="positive"):
        Predictor(model)
