"""Frozen v2 orchestration: train/choose first, open final outcomes separately.

No MoneyData data are accepted. All saved arrays use NPZ without pickle. Resume
reuses only complete, fingerprint-verified units; partial artifacts are refused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import time

import numpy as np
import torch

from .evaluate import metrics, paired_interval, promotion_decision
from .models import features, fit_ridge, predict_arrays
from .sequence_models import KINDS, make_model, parameter_count
from .sequence_training import fit_model, load_predictor, pretrain_ssl

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "evaluation-v2.json"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False, sort_keys=True) + "\n")
    temporary.replace(path)


def load_data(source, config_path=CONFIG, data_dir=None, *, final=False):
    if source not in ("ibm", "berka"):
        raise ValueError("v2 accepts only IBM or Berka; MoneyData is excluded")
    config_path = Path(config_path)
    config = read_json(config_path)
    if config.get("frozen_before_training") is not True or config["training"]["seeds"] != [11, 23, 47]:
        raise ValueError("v2 policy must be frozen with all three declared seeds")
    if tuple(config["architectures"]) != KINDS or config["maximum_parameters"] != 50_000:
        raise ValueError("all four frozen architectures and parameter ceiling are required")
    directory = Path(data_dir) if data_dir else ROOT / "data" / "processed" / (source + "-v2")
    data_path = directory / f"{source}_windows.npz"
    audit_path, manifest_path = directory / f"{source}_audit.json", directory / f"{source}_manifest.json"
    audit, manifest = read_json(audit_path), read_json(manifest_path)
    policy_path = config_path if source == "ibm" else directory / "policy.json"
    policy = read_json(policy_path)
    if policy.get("frozen_before_training") is not True:
        raise ValueError("source split policy is not frozen")
    verdict = "train_for_limited_research_only" if source == "ibm" else "train_for_limited_retrospective_research_only"
    if audit.get("blocking_items") != [] or audit.get("train_verdict") != verdict:
        raise ValueError("source numeric audit blocks training")
    if manifest.get("source") != source or manifest.get("data_sha256") != digest(data_path) or manifest.get("audit_sha256") != digest(audit_path) or manifest.get("evaluation_sha256") != digest(policy_path):
        raise ValueError("source, data, audit or frozen source policy fingerprint mismatch")
    expected = config[source] if source == "ibm" else policy
    if any(manifest.get(k) != expected[k] for k in ("currency", "target")) or manifest.get("synthetic") != (source == "ibm"):
        raise ValueError("source accounting metadata disagrees with frozen policy")
    integrity = audit.get("split_integrity", {})
    group_keys = ("shared_groups",) if source == "ibm" else ("shared_accounts", "shared_components")
    if len(integrity) != 3 or any(any(v.get(key) != 0 for key in group_keys) or not v.get("all_target_dates_strictly_ordered") for v in integrity.values()):
        raise ValueError("audited person groups or target chronology overlap")
    split = {}
    # np.load does not decompress test arrays unless explicitly indexed here.
    with np.load(data_path, allow_pickle=False) as archive:
        for name in (("test",) if final else ("train", "validation")):
            values = {key: archive[f"{name}_{key}"] for key in ("history", "y", "origin", "group")}
            h, y, origins, groups = (values[k] for k in ("history", "y", "origin", "group"))
            features(h, origins)
            if y.shape != (len(h), 14) or groups.shape != (len(h),) or not np.isfinite(y).all() or (y < 0).any():
                raise ValueError(f"invalid {name} target/groups")
            split[name] = values
    if not final:
        tr, va = split["train"], split["validation"]
        if set(tr["group"]) & set(va["group"]) or tr["origin"].max() + 13 >= va["origin"].min():
            raise ValueError("loaded training/validation split leakage")
    fingerprints = {
        "source": source, "evaluation_sha256": digest(config_path),
        "source_policy_sha256": digest(policy_path), "data_sha256": digest(data_path),
        "audit_sha256": digest(audit_path), "manifest_sha256": digest(manifest_path),
        "code_sha256": {name: digest(ROOT / name) for name in ("run_v2.py", "sequence_models.py", "sequence_training.py", "models.py", "evaluate.py")},
        "python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__,
    }
    return config, manifest, policy, split, fingerprints


def _record(directory, name):
    path = directory / (name + ".json")
    weights = directory / (name + ".npz")
    if path.exists():
        record = read_json(path)
        if record["name"] != name or record["sha256"] != digest(weights):
            raise ValueError("finished unit artifact changed: " + name)
        return record
    if weights.exists():
        raise ValueError("partial unit exists; inspect it before choosing a fresh run-id: " + name)
    return None


def _save_record(directory, name, record):
    value = {"name": name, "sha256": digest(directory / (name + ".npz")), **record}
    write_json(directory / (name + ".json"), value)
    return value


def _metadata(manifest):
    return {k: manifest[k] for k in ("source", "target", "currency", "synthetic")} | {
        "experimental": True, "real_world_validated": False,
        "accounting_warning": "Gross source outflow; no validated known-bill exclusion or currency conversion",
    }


def _baseline_predict(path, history, origins):
    with np.load(path, allow_pickle=False) as archive:
        raw = archive["metadata"]
        if raw.dtype != np.uint8 or raw.ndim != 1 or len(raw) > 1_000_000:
            raise ValueError("invalid baseline metadata")
        metadata = json.loads(raw.tobytes().decode())
        state = {k: archive[k] for k in archive.files if k != "metadata"}
        kind = metadata["kind"]
        expected = {"feature_mean": (99,), "feature_std": (99,), "coef": (100, 14)} if kind == "ridge" else {}
        if kind not in ("ridge", "recent_28day_mean", "weekday_8week_mean") or set(state) != set(expected) or len(archive.files) != len(state) + 1:
            raise ValueError("invalid baseline archive schema")
        if any(state[key].shape != shape or state[key].dtype != np.float64 or not np.isfinite(state[key]).all() for key, shape in expected.items()) or (kind == "ridge" and (state["feature_std"] <= 0).any()):
            raise ValueError("invalid baseline weights/standardizer")
    return predict_arrays(metadata["kind"], state, history, origins)


def _encoder(path):
    with np.load(path, allow_pickle=False) as archive:
        expected = make_model("transformer").trunk.state_dict()
        if set(archive.files) != set(expected) or len(archive.files) != len(expected):
            raise ValueError("invalid encoder schema")
        result = {key: torch.from_numpy(archive[key].copy()) for key in archive.files}
        if any(result[k].shape != v.shape or result[k].dtype != v.dtype or not torch.isfinite(result[k]).all() for k, v in expected.items()) or not torch.equal(result["position_encoding"], expected["position_encoding"]):
            raise ValueError("invalid encoder tensors")
        return result


def _check_complete(records, config, source):
    conditions = set(config["ssl"]["conditions_" + source]) - {"scratch", "berka_scratch"}
    expected = {f"scratch_{kind}_seed_{seed}" for kind in KINDS for seed in config["training"]["seeds"]}
    expected |= {f"{condition}_transformer_seed_{seed}" for condition in conditions for seed in config["training"]["seeds"]}
    expected |= {f"ssl_seed_{seed}" for seed in config["training"]["seeds"]}
    expected |= {"recent_28day_mean", "weekday_8week_mean"} | {f"ridge_alpha_{alpha:g}" for alpha in config["ridge_alphas"]}
    if len(records) != len(expected) or {r["name"] for r in records} != expected:
        raise ValueError("all expected architecture, SSL, transfer and matched runs must finish before closing training")


def choose(records, config, source):
    minimum, seeds = config["training"]["minimum_epochs_for_selection"], config["training"]["seeds"]
    baselines = [r for r in records if r["family"] == "baseline"]
    forecasts = [r for r in records if r["family"] == "learned"]
    eligible, reasons = [], {}
    for kind in KINDS:
        candidates = [r for r in forecasts if r["condition"] == "scratch" and r["kind"] == kind]
        okay = sorted(r["seed"] for r in candidates) == seeds and all(r["training"]["epochs_run"] >= minimum for r in candidates)
        reasons[kind] = {"eligible": okay, "seeds": [r["seed"] for r in candidates]}
        if okay:
            eligible.extend(candidates)
    best = lambda rows: min(rows, key=lambda r: r["validation"]["14day_total_mae"])["name"] if rows else None
    conditions = {}
    for condition in sorted({r["condition"] for r in forecasts}):
        rows = [r for r in forecasts if r["condition"] == condition and r["kind"] == "transformer"]
        okay = sorted(r["seed"] for r in rows) == seeds and all(r["training"]["epochs_run"] >= minimum for r in rows)
        if condition == "compute_matched_scratch":
            okay = okay and all(r["training"].get("fixed_updates_reached") for r in rows)
        conditions[condition] = {"eligible": okay, "selected": best(rows) if okay else None}
    if not baselines or not eligible:
        raise ValueError("no eligible baseline/neural architecture; report incomplete training before final evaluation")
    return {"source": source, "training_closed": True, "selection_rule": "lowest validation 14-day total MAE only",
            "selected_before_final_test": True, "selected_baseline": best(baselines), "selected_neural": best(eligible),
            "architecture_eligibility": reasons, "required_architecture_bakeoff_complete": all(v["eligible"] for v in reasons.values()),
            "conditions": conditions, "records": records,
            "limitations": ["Compute matching uses optimizer updates and fixed batch size, not identical FLOPs or wall time", "No MoneyData fitting or evaluation", "No representative current real-population evidence", "Berka transfer from later-calendar IBM data is retrospective, not historical deployment"]}


def train(source, run_id, *, config_path=CONFIG, data_dir=None, artifact_root=None, resume=False, ibm_run=None):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("run-id must contain only letters, digits, underscores or hyphens")
    config, manifest, policy, split, fingerprints = load_data(source, config_path, data_dir)
    if source == "berka" and ibm_run is None:
        raise ValueError("Berka transfer study requires --ibm-run from closed IBM training")
    donor = None
    if ibm_run:
        ibm_run = Path(ibm_run)
        donor = read_json(ibm_run / "selection.json")
        frozen = read_json(ibm_run / "training-closed.json")
        if donor.get("source") != "ibm" or donor.get("training_closed") is not True or frozen["selection_sha256"] != digest(ibm_run / "selection.json") or frozen["fingerprints_sha256"] != digest(ibm_run / "fingerprints.json"):
            raise ValueError("IBM donor training/selection is not frozen")
        donor_fp = read_json(ibm_run / "fingerprints.json")
        if donor_fp["evaluation_sha256"] != fingerprints["evaluation_sha256"] or donor_fp["code_sha256"] != fingerprints["code_sha256"]:
            raise ValueError("IBM donor policy/code differs from this experiment")
        _check_complete(donor["records"], config, "ibm")
        fingerprints["ibm_donor"] = {"path": str(ibm_run.resolve()), "selection_sha256": digest(ibm_run / "selection.json"), "fingerprints_sha256": digest(ibm_run / "fingerprints.json")}
    directory = Path(artifact_root or ROOT / "artifacts") / f"{source}-{run_id}"
    if directory.exists():
        if not resume or read_json(directory / "fingerprints.json") != fingerprints:
            raise ValueError("existing run requires --resume and identical policy/data/code/runtime fingerprints")
        if (directory / "training-closed.json").exists():
            closed = read_json(directory / "training-closed.json")
            if closed["selection_sha256"] != digest(directory / "selection.json"):
                raise ValueError("closed selection changed")
            return read_json(directory / "selection.json")
    else:
        directory.mkdir(parents=True)
        write_json(directory / "fingerprints.json", fingerprints)
        (directory / "evaluation-v2.json").write_bytes(Path(config_path).read_bytes())
        source_policy_path = Path(config_path) if source == "ibm" else Path(data_dir or ROOT / "data" / "processed" / "berka-v2") / "policy.json"
        (directory / "source-policy.json").write_bytes(source_policy_path.read_bytes())
    torch.set_num_threads(config["training"]["threads"])
    units = directory / "units"
    units.mkdir(exist_ok=True)
    tr, va = split["train"], split["validation"]
    records = []
    source_metadata = _metadata(manifest)
    tr_x, tr_scale, _ = features(tr["history"], tr["origin"])
    standardizer = {"feature_mean": tr_x.mean(0), "feature_std": np.maximum(tr_x.std(0), .1)}
    for kind, alpha in [("recent_28day_mean", None), ("weekday_8week_mean", None)] + [("ridge", a) for a in config["ridge_alphas"]]:
        name = kind if alpha is None else f"ridge_alpha_{alpha:g}"
        record = _record(units, name)
        if record is None:
            started = time.monotonic()
            state = {} if alpha is None else dict(standardizer, coef=fit_ridge((tr_x - standardizer["feature_mean"]) / standardizer["feature_std"], tr["y"] / tr_scale[:, None], alpha))
            metadata = {**source_metadata, "kind": kind, "alpha": alpha}
            np.savez_compressed(units / (name + ".npz"), metadata=np.frombuffer(json.dumps(metadata).encode(), dtype=np.uint8), **state)
            prediction = _baseline_predict(units / (name + ".npz"), va["history"], va["origin"])
            record = _save_record(units, name, {"family": "baseline", "kind": kind, "validation": metrics(va["y"], prediction), "training_seconds": time.monotonic() - started})
        records.append(record)

    def forecast(kind, seed, condition, encoder=None, updates=None):
        name = f"{condition}_{kind}_seed_{seed}"
        record = _record(units, name)
        if record is None:
            print(f"training source={source} condition={condition} kind={kind} seed={seed}", flush=True)
            settings = dict(config["training"])
            if updates is not None:
                settings["max_seconds"] = config["ssl"]["matched_scratch_max_seconds"]
            predictor, log = fit_model(kind, tr["history"], tr["y"], tr["origin"], va["history"], va["y"], va["origin"], settings, seed, init_encoder=encoder, fixed_updates=updates)
            if parameter_count(predictor.model) > config["maximum_parameters"]:
                raise ValueError("parameter ceiling exceeded")
            predictor.metadata.update({**source_metadata, "condition": condition, "model_id": source + "-" + name})
            path = predictor.save(units / (name + ".npz"))
            restored = load_predictor(path)
            check = min(3, len(va["history"]))
            np.testing.assert_allclose(restored.predict(va["history"][:check], va["origin"][:check]), predictor.predict(va["history"][:check], va["origin"][:check]), rtol=0, atol=0)
            record = _save_record(units, name, {"family": "learned", "kind": kind, "seed": seed, "condition": condition, "parameter_count": parameter_count(predictor.model), "training": log, "matched_target_updates": updates, "validation": metrics(va["y"], restored.predict(va["history"], va["origin"])), "serialization_roundtrip": True})
            print(f"finished {name}: epochs={log['epochs_run']} updates={log['optimizer_updates']} seconds={log['training_seconds']:.2f}", flush=True)
        records.append(record)
        return record

    for kind in KINDS:
        for seed in config["training"]["seeds"]:
            forecast(kind, seed, "scratch")
    for seed in config["training"]["seeds"]:
        ssl_name = f"ssl_seed_{seed}"
        ssl_record = _record(units, ssl_name)
        if ssl_record is None:
            print(f"training source={source} masked_ssl seed={seed}", flush=True)
            state, log = pretrain_ssl(tr["history"], tr["origin"], {**config["training"], **config["ssl"]}, seed)
            np.savez_compressed(units / (ssl_name + ".npz"), **{k: v.numpy() for k, v in state.items()})
            ssl_record = _save_record(units, ssl_name, {"family": "ssl", "kind": "transformer", "seed": seed, "training": log})
        records.append(ssl_record)
        local = forecast("transformer", seed, f"{source}_ssl_then_{source}_forecast", _encoder(units / (ssl_name + ".npz")))
        pretrain_updates = ssl_record["training"]["optimizer_updates"]
        primary = local
        if source == "berka":
            donor_ssl = _record(ibm_run / "units", ssl_name)
            donor_forecast_name = f"scratch_transformer_seed_{seed}"
            donor_forecast = _record(ibm_run / "units", donor_forecast_name)
            if donor_ssl is None or donor_forecast is None:
                raise ValueError("IBM donor lacks one of the required seeded encoder artifacts")
            frozen_donors = {r["name"]: r for r in donor["records"]}
            if donor_ssl != frozen_donors.get(ssl_name) or donor_forecast != frozen_donors.get(donor_forecast_name):
                raise ValueError("IBM donor record differs from frozen validation selection")
            primary = forecast("transformer", seed, "ibm_ssl_then_berka_forecast", _encoder(ibm_run / "units" / (ssl_name + ".npz")))
            forecast("transformer", seed, "ibm_forecast_then_berka_forecast", load_predictor(ibm_run / "units" / (donor_forecast_name + ".npz")).encoder_state())
            pretrain_updates = donor_ssl["training"]["optimizer_updates"]
        forecast("transformer", seed, "compute_matched_scratch", updates=pretrain_updates + primary["training"]["optimizer_updates"])
    _check_complete(records, config, source)
    selection = {**choose(records, config, source), "all_expected_runs_finished": True}
    write_json(directory / "selection.json", selection)
    write_json(directory / "training-closed.json", {"selection_sha256": digest(directory / "selection.json"), "fingerprints_sha256": digest(directory / "fingerprints.json"), "training_closed": True})
    print(json.dumps({"training_closed": str(directory), "selected_neural": selection["selected_neural"], "selected_baseline": selection["selected_baseline"]}), flush=True)
    return selection


def evaluate(source, run_id, *, config_path=CONFIG, data_dir=None, artifact_root=None):
    directory = Path(artifact_root or ROOT / "artifacts") / f"{source}-{run_id}"
    closed = read_json(directory / "training-closed.json")
    if not closed.get("training_closed") or closed["selection_sha256"] != digest(directory / "selection.json") or closed["fingerprints_sha256"] != digest(directory / "fingerprints.json"):
        raise ValueError("training or validation selection is not frozen")
    selection = read_json(directory / "selection.json")
    if not selection.get("selected_before_final_test") or not selection.get("all_expected_runs_finished") or selection.get("source") != source:
        raise ValueError("invalid frozen selection")
    if (directory / "results.json").exists() or (directory / "predictions-test.npz").exists():
        raise ValueError("final test was already evaluated; retained outcomes cannot be overwritten")
    config, manifest, _, split, fingerprints = load_data(source, config_path, data_dir, final=True)
    old = read_json(directory / "fingerprints.json")
    if {k: v for k, v in old.items() if k != "ibm_donor"} != fingerprints:
        raise ValueError("frozen run policy/data/code/runtime changed")
    _check_complete(selection["records"], config, source)
    torch.set_num_threads(config["training"]["threads"])
    final, predictions, scores = split["test"], {}, {}
    for record in selection["records"]:
        checked = _record(directory / "units", record["name"])
        if checked != record:
            raise ValueError("frozen unit record changed")
        if record["family"] == "ssl":
            continue
        path = directory / "units" / (record["name"] + ".npz")
        prediction = _baseline_predict(path, final["history"], final["origin"]) if record["family"] == "baseline" else load_predictor(path).predict(final["history"], final["origin"])
        predictions[record["name"]] = prediction
        scores[record["name"]] = metrics(final["y"], prediction)
    def compare(reference, candidate):
        interval = paired_interval(final["y"], predictions[reference], predictions[candidate], final["group"], final["origin"], config["bootstrap"])
        decision = promotion_decision(scores[reference], scores[candidate], interval, representative_real_data=False, thresholds=config["promotion"])
        if source == "berka":
            interval["unit"] = "account-client connected component"
        return {"reference": reference, "candidate": candidate, "paired_uncertainty": interval, "decision": decision}
    baseline, neural = selection["selected_baseline"], selection["selected_neural"]
    conditions, comparisons = selection["conditions"], {}
    scratch = conditions["scratch"]["selected"]
    matched = conditions["compute_matched_scratch"]["selected"]
    for name, condition in conditions.items():
        candidate = condition["selected"]
        if candidate:
            references = {"baseline": baseline, "scratch_transformer": scratch, "compute_matched_scratch": matched}
            comparisons[name] = {label: compare(reference, candidate) for label, reference in references.items() if reference and reference != candidate}
    by_name = {record["name"]: record for record in selection["records"]}
    per_seed = {}
    primary_condition = f"ibm_ssl_then_{source}_forecast"
    for seed in config["training"]["seeds"]:
        candidate, reference, matched_name = (f"{condition}_transformer_seed_{seed}" for condition in (primary_condition, "scratch", "compute_matched_scratch"))
        match_record = by_name[matched_name]
        achieved = bool(match_record["training"].get("fixed_updates_reached"))
        per_seed[str(seed)] = {"versus_same_seed_scratch": compare(reference, candidate), "matched_target_updates": match_record["matched_target_updates"], "matched_actual_updates": match_record["training"]["optimizer_updates"], "update_match_achieved": achieved,
                             "versus_same_seed_matched_scratch": compare(matched_name, candidate) if achieved else None}
    report = {**_metadata(manifest), "selection": selection, "test": scores, "primary_comparison": compare(baseline, neural), "condition_comparisons": comparisons, "primary_ssl_same_seed_comparisons": per_seed,
              "default_model": baseline, "test_windows": len(final["y"]), "test_groups": len(set(final["group"])),
              "limitations": selection["limitations"] + ["Independently validation-selected condition seeds can have different update budgets; cross-seed condition comparisons are exploratory, not exact matched-compute pairs", "All frozen final candidates are reported for transparency; no re-selection on test", "Bootstrap conditions on selected fitted models; excludes training/selection uncertainty"]}
    np.savez_compressed(directory / "predictions-test.npz", actual=final["y"], origin=final["origin"], group=final["group"], **predictions)
    report["predictions_sha256"] = digest(directory / "predictions-test.npz")
    write_json(directory / "results.json", report)
    print(json.dumps({"results": str(directory / "results.json"), "default_model": baseline, "primary_comparison": report["primary_comparison"]}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("ibm", "berka"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stage", choices=("train", "evaluate"), required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--ibm-run", type=Path)
    args = parser.parse_args()
    if args.stage == "train":
        train(args.source, args.run_id, resume=args.resume, ibm_run=args.ibm_run)
    elif args.resume or args.ibm_run:
        parser.error("--resume/--ibm-run apply only to training")
    else:
        evaluate(args.source, args.run_id)


if __name__ == "__main__":
    main()
