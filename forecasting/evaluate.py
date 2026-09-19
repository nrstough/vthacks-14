"""Point forecast metrics and paired uncertainty preserving related windows."""
import numpy as np


def metrics(actual, predicted):
    if actual.shape != predicted.shape or actual.ndim != 2 or actual.shape[1] != 14 or not len(actual):
        raise ValueError("metrics require matching nonempty N x 14 arrays")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("metrics require finite values")
    error = predicted.sum(1) - actual.sum(1)
    return {
        "daily_mae": float(np.abs(actual - predicted).mean()),
        "7day_total_mae": float(np.abs(actual[:, :7].sum(1) - predicted[:, :7].sum(1)).mean()),
        "14day_total_mae": float(np.abs(error).mean()),
        "14day_bias_pred_minus_actual": float(error.mean()),
        "14day_mean_underprediction": float(np.maximum(-error, 0).mean()),
    }


def paired_interval(actual, baseline, neural, groups, origins, config):
    """Positive difference means the network has lower 14-day MAE.

    Customer bootstrap resamples whole groups, retaining all their origins.
    A one-person series uses circular blocks of four date-sorted origins; its
    interval concerns only that history and cannot establish population validity.
    """
    difference = np.abs(actual.sum(1) - baseline.sum(1)) - np.abs(actual.sum(1) - neural.sum(1))
    rng = np.random.default_rng(config["seed"])
    unique, inverse = np.unique(groups, return_inverse=True)
    samples = []
    if len(unique) > 1:
        totals = np.bincount(inverse, weights=difference)
        counts = np.bincount(inverse)
        for _ in range(config["replicates"]):
            ids = rng.integers(0, len(unique), size=len(unique))
            samples.append(totals[ids].sum() / counts[ids].sum())
        unit = "customer"
    else:
        difference = difference[np.argsort(origins)]
        block = 4
        for _ in range(config["replicates"]):
            starts = rng.integers(0, len(difference), size=int(np.ceil(len(difference) / block)))
            indices = ((starts[:, None] + np.arange(block)) % len(difference)).ravel()[:len(difference)]
            samples.append(difference[indices].mean())
        unit = "circular blocks of 4 consecutive origins; one-person temporal case study"
    return {
        "paired_improvement": float(difference.mean()),
        "ci95": np.quantile(samples, [.025, .975]).tolist(),
        "unit": unit, "groups": len(unique), "replicates": config["replicates"],
        "sign": "positive favors neural; baseline MAE minus neural MAE",
        "scope": "conditional on selected fitted models; excludes model-selection/training uncertainty",
    }


def promotion_decision(baseline, neural, interval, *, representative_real_data, valid=True, thresholds=None):
    thresholds = thresholds or {"minimum_relative_14day_mae_gain": .05,
                                "paired_improvement_ci_lower_must_exceed": 0,
                                "maximum_underprediction_ratio": 1.05}
    base_mae, net_mae = baseline["14day_total_mae"], neural["14day_total_mae"]
    relative_gain = (base_mae - net_mae) / base_mae if base_mae > 0 else 0.0
    base_under, net_under = baseline["14day_mean_underprediction"], neural["14day_mean_underprediction"]
    checks = {
        "at_least_required_mae_gain": relative_gain >= thresholds["minimum_relative_14day_mae_gain"],
        "paired_ci_excludes_zero_in_favor": interval["ci95"][0] > thresholds["paired_improvement_ci_lower_must_exceed"],
        "underprediction_within_threshold": net_under <= thresholds["maximum_underprediction_ratio"] * base_under,
        "comparison_valid": bool(valid),
        "representative_real_multicustomer_evidence": bool(representative_real_data),
        "multiple_customer_groups": interval.get("groups", 0) > 1 and interval.get("unit") == "customer",
    }
    return {"promote_neural": all(checks.values()), "relative_mae_gain": relative_gain, "checks": checks}
