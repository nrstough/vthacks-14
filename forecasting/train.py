"""Frozen public-data experiment. Selection uses validation; final test follows once."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np

from .evaluate import metrics, paired_interval, promotion_decision
from .models import features, fit_neural, fit_ridge, predict_arrays
from .predict import Predictor

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def save_model(directory, filename, kind, state, source, run_id, config, config_hash, extra=None):
    weights_path = directory / (filename + ".npz")
    np.savez_compressed(weights_path, **state)
    metadata = {
        "format_version": 1, "model_id": f"{source}-{run_id}-{filename}", "kind": kind,
        "source": "IBM TabFormer synthetic card transactions" if source == "ibm" else "MoneyData published single-person history",
        "target": config[source]["target"], "currency": config[source]["currency"],
        "experimental": True, "synthetic_training": config[source]["synthetic"],
        "context_days": 56, "horizon_days": 14, "weights": weights_path.name,
        "weights_sha256": digest(weights_path), "evaluation_config_sha256": config_hash,
        "target_warning": "No validated known-bill exclusion. Do not append to an overlapping schedule.",
        "validity": "No representative real multi-customer validation; point estimates only.",
    }
    if extra:
        metadata.update(extra)
    write_json(directory / (filename + ".json"), metadata)
    return metadata


def train(source, run_id):
    if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in run_id):
        raise ValueError("run-id may contain only letters, digits, underscore, hyphen")
    config_path = ROOT / "evaluation.json"
    config_bytes = config_path.read_bytes()
    config_hash = hashlib.sha256(config_bytes).hexdigest()
    config = json.loads(config_bytes)
    data_path = ROOT / "data" / "processed" / f"{source}_windows.npz"
    audit_path = data_path.with_name(f"{source}_audit.json")
    manifest_path = data_path.with_name(f"{source}_manifest.json")
    audit = json.loads(audit_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    if audit.get("blocking_items") != [] or audit.get("train_verdict") != "train_for_limited_research_only":
        raise ValueError("audit blocks training")
    if (manifest.get("data_sha256") != digest(data_path)
            or manifest.get("audit_sha256") != digest(audit_path)
            or manifest.get("evaluation_sha256") != config_hash):
        raise ValueError("processed data, audit, or frozen configuration changed")
    for key in ("currency", "target", "synthetic"):
        if manifest.get(key) != config[source][key]:
            raise ValueError(f"manifest {key} does not match frozen source policy")
    if manifest.get("source") != source:
        raise ValueError("source manifest mismatch")
    directory = ROOT / "artifacts" / f"{source}-{run_id}"
    directory.mkdir(parents=True, exist_ok=False)
    # Freeze an exact record before model selection; never overwrite a prior run.
    (directory / "evaluation.json").write_bytes(config_bytes)
    write_json(directory / "input-fingerprints.json", {
        "windows_sha256": digest(data_path), "audit_sha256": digest(audit_path),
        "manifest_sha256": digest(manifest_path), "config_sha256": config_hash,
        "source_code_sha256": {p.name: digest(p) for p in ROOT.glob("*.py")},
        "python": platform.python_version(), "numpy": np.__version__,
    })
    started = time.perf_counter()
    with np.load(data_path, allow_pickle=False) as data:
        arrays = {k: data[k] for k in data.files}
    split = {}
    for name in ("train", "validation", "test"):
        h, y, origins, groups = [arrays[f"{name}_{key}"] for key in ("history", "y", "origin", "group")]
        if y.shape != (len(h), 14) or not np.isfinite(y).all() or (y < 0).any():
            raise ValueError(f"invalid target array in {name}")
        x, scale, weekday = features(h, origins)
        split[name] = dict(history=h, y=y, origin=origins, group=groups, x=x, scale=scale, weekday=weekday)
    feature_mean = split["train"]["x"].mean(0)
    feature_std = np.maximum(split["train"]["x"].std(0), .1)
    standardizer = dict(feature_mean=feature_mean, feature_std=feature_std)
    for values in split.values():
        values["normalized"] = (values["x"] - feature_mean) / feature_std
    feature_seconds = time.perf_counter() - started
    tr, va = split["train"], split["validation"]
    validation, models, fit_times = {}, {}, {}
    for kind in ("recent_28day_mean", "weekday_8week_mean"):
        models[kind] = (kind, {})
        validation[kind] = metrics(va["y"], predict_arrays(kind, {}, va["history"], va["origin"]))
        fit_times[kind] = 0.0
    for alpha in config["ridge_alphas"]:
        began = time.perf_counter()
        state = dict(standardizer, coef=fit_ridge(tr["normalized"], tr["y"] / tr["scale"][:, None], alpha))
        name = f"ridge_alpha_{alpha:g}"
        fit_times[name] = time.perf_counter() - began
        models[name] = ("ridge", state)
        validation[name] = metrics(va["y"], predict_arrays("ridge", state, va["history"], va["origin"]))
    baseline = min(models, key=lambda name: validation[name]["14day_total_mae"])
    runs = []
    neural_names = []
    for seed in config["neural"]["seeds"]:
        began = time.perf_counter()
        weights, log = fit_neural(tr["normalized"], tr["y"] / tr["scale"][:, None],
                                  va["normalized"], va["y"], va["scale"], seed, config["neural"])
        name = f"neural_seed_{seed}"
        fit_times[name] = time.perf_counter() - began
        state = dict(weights, **standardizer)
        models[name] = ("neural", state)
        validation[name] = metrics(va["y"], predict_arrays("neural", state, va["history"], va["origin"]))
        log["training_seconds"] = fit_times[name]
        runs.append(log)
        neural_names.append(name)
        save_model(directory, name, "neural", state, source, run_id, config, config_hash, {"seed": seed})
    neural = min(neural_names, key=lambda name: validation[name]["14day_total_mae"])
    selection = {"selected_baseline": baseline, "selected_neural": neural,
                 "criterion": "lowest validation 14-day total MAE", "validation": validation,
                 "selected_before_final_test": True}
    write_json(directory / "selection.json", selection)
    # Selection is now immutable for this run. No hyperparameter changes follow.
    final = split["test"]
    evaluation, predictions, inference = {}, {}, {}
    for name, (kind, state) in models.items():
        began = time.perf_counter()
        prediction = predict_arrays(kind, state, final["history"], final["origin"])
        inference[name] = {"batch_seconds": time.perf_counter() - began, "windows": len(prediction)}
        evaluation[name] = metrics(final["y"], prediction)
        predictions[name] = prediction
    interval = paired_interval(final["y"], predictions[baseline], predictions[neural],
                               final["group"], final["origin"], config["bootstrap"])
    decision = promotion_decision(evaluation[baseline], evaluation[neural], interval,
                                  representative_real_data=False, thresholds=config["promotion"])
    default_name = neural if decision["promote_neural"] else baseline
    kind, state = models[default_name]
    save_model(directory, "default", kind, state, source, run_id, config, config_hash, {"selected_from": default_name})
    kind, state = models[neural]
    save_model(directory, "neural-selected", kind, state, source, run_id, config, config_hash, {"selected_from": neural})
    np.savez_compressed(directory / "predictions-test.npz", actual=final["y"], origin=final["origin"],
                        group=final["group"], **predictions)
    origin_date = date(1970, 1, 1) + timedelta(days=int(final["origin"][0]))
    history_json = {"currency": config[source]["currency"], "days": [
        {"date": (origin_date + timedelta(days=i - 56)).isoformat(), "amount": float(amount), "observed": True}
        for i, amount in enumerate(final["history"][0])]}
    write_json(directory / "example-history.json", history_json)
    for filename, selected in (("default", default_name), ("neural-selected", neural)):
        result = Predictor(directory / (filename + ".json")).predict(history_json["days"], currency=history_json["currency"])
        # Batch matrix operations may differ by a few float ulps from one-row inference.
        actual = np.array([row["amount"] for row in result["days"]])
        np.testing.assert_allclose(actual, predictions[selected][0], rtol=1e-12, atol=1e-10)
        write_json(directory / (filename + "-example-forecast.json"), result)
    by_weekday = {}
    for weekday in range(7):
        ix = (final["origin"] + 3) % 7 == weekday
        by_weekday[str(weekday)] = {"windows": int(ix.sum()), "baseline": metrics(final["y"][ix], predictions[baseline][ix]),
                                    "neural": metrics(final["y"][ix], predictions[neural][ix])}
    report = {
        "source": source, "currency": config[source]["currency"], "target": config[source]["target"],
        "provenance": "synthetic" if source == "ibm" else "real single-person posted history",
        "selection": selection, "test": evaluation, "neural_runs": runs,
        "paired_uncertainty": interval, "decision": decision, "default_model": default_name,
        "test_start_weekday": by_weekday, "training_seconds": fit_times,
        "feature_preparation_seconds": feature_seconds, "inference": inference,
        "total_run_seconds": time.perf_counter() - started,
        "serialization_roundtrip": "default and neural-selected matched one-row batch prediction within1e-10",
        "limitations": ["No validated known-bill exclusion", "No calibrated prediction intervals or probability of solvency",
                        "Completeness of empty transaction dates is assumed, not independently proven",
                        "No representative real multi-customer validation; every artifact is experimental",
                        "Final test also reports other frozen models for transparency; they are not used to change selection"],
    }
    write_json(directory / "results.json", report)
    print(json.dumps({"run": str(directory), "selected_baseline": baseline, "selected_neural": neural,
                      "final_baseline": evaluation[baseline], "final_neural": evaluation[neural],
                      "paired_uncertainty": interval, "decision": decision,
                      "total_seconds": report["total_run_seconds"]}, indent=2), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["ibm", "moneydata"], required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    train(args.source, args.run_id)
