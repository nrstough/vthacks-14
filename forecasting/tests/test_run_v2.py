"""Policy, holdout and resumability checks; optimizer work is independently tested."""
import json

import numpy as np
import pytest

from forecasting import run_v2 as run
from forecasting.models import features
from forecasting.sequence_models import make_model
from forecasting.sequence_training import ForecastPredictor


def save(path, value):
    path.write_text(json.dumps(value))


@pytest.fixture
def dataset(tmp_path):
    config = json.loads(run.CONFIG.read_text())
    config["bootstrap"]["replicates"] = 20
    config["training"]["threads"] = 1
    config_path = tmp_path / "evaluation-v2.json"
    save(config_path, config)
    directory = tmp_path / "ibm-v2"
    directory.mkdir()
    rng, arrays = np.random.default_rng(12), {}
    for i, split in enumerate(("train", "validation", "test")):
        arrays.update({f"{split}_history": rng.uniform(0, 10, (7, 56)),
                       f"{split}_y": rng.uniform(0, 10, (7, 14)),
                       f"{split}_origin": np.arange(7, dtype=np.int64) * 15 + 17000 + i * 365,
                       f"{split}_group": np.asarray([f"{split}-{j}" for j in range(7)])})
    np.savez_compressed(directory / "ibm_windows.npz", **arrays)
    audit = {"blocking_items": [], "train_verdict": "train_for_limited_research_only",
             "split_integrity": {key: {"shared_groups": 0, "all_target_dates_strictly_ordered": True}
                                 for key in ("train_vs_validation", "train_vs_test", "validation_vs_test")}}
    save(directory / "ibm_audit.json", audit)
    manifest = {"source": "ibm", "target": "card_spending", "currency": "USD", "synthetic": True,
                "data_sha256": run.digest(directory / "ibm_windows.npz"),
                "audit_sha256": run.digest(directory / "ibm_audit.json"),
                "evaluation_sha256": run.digest(config_path)}
    save(directory / "ibm_manifest.json", manifest)
    return {"config_path": config_path, "data_dir": directory, "artifact_root": tmp_path / "artifacts"}


@pytest.fixture
def fake_training(monkeypatch):
    calls = []
    def fit(kind, h, y, origins, vh, vy, vo, config, seed, init_encoder=None, fixed_updates=None):
        calls.append((kind, seed, init_encoder is not None, fixed_updates))
        x, _, _ = features(h, origins)
        model = make_model(kind, seed)
        if init_encoder is not None:
            model.trunk.load_state_dict(init_encoder)
        updates = fixed_updates or 6
        log = {"epochs_run": 3, "optimizer_updates": updates, "examples_processed": updates * 7,
               "fixed_updates_reached": fixed_updates is not None, "training_seconds": .01}
        return ForecastPredictor(model, x.mean(0), np.maximum(x.std(0), .1), {"training": log}), log
    def ssl(h, origins, config, seed):
        model = make_model("transformer", seed)
        return {k: v.detach().clone() for k, v in model.trunk.state_dict().items()}, {
            "optimizer_updates": 2, "epochs_run": 2, "examples_processed": 14, "training_seconds": .01}
    monkeypatch.setattr(run, "fit_model", fit)
    monkeypatch.setattr(run, "pretrain_ssl", ssl)
    return calls


def test_train_never_reads_test_arrays(dataset, monkeypatch):
    original = np.load
    seen = []
    class Guard:
        def __init__(self, archive): self.archive = archive
        def __enter__(self): return self
        def __exit__(self, *args): self.archive.close()
        def __getitem__(self, key):
            seen.append(key)
            if key.startswith("test_"): raise AssertionError("opened final test")
            return self.archive[key]
    monkeypatch.setattr(run.np, "load", lambda *a, **k: Guard(original(*a, **k)))
    run.load_data("ibm", dataset["config_path"], dataset["data_dir"])
    assert len(seen) == 8 and all(not key.startswith("test_") for key in seen)


def test_moneydata_and_corrupt_policy_rejected(dataset):
    with pytest.raises(ValueError, match="MoneyData"):
        run.load_data("moneydata")
    audit_path = dataset["data_dir"] / "ibm_audit.json"
    audit = json.loads(audit_path.read_text())
    audit["split_integrity"]["train_vs_test"]["shared_groups"] = 1
    save(audit_path, audit)
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        run.load_data("ibm", dataset["config_path"], dataset["data_dir"])
    manifest_path = dataset["data_dir"] / "ibm_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["audit_sha256"] = run.digest(audit_path)
    save(manifest_path, manifest)
    with pytest.raises(ValueError, match="groups or target chronology overlap"):
        run.load_data("ibm", dataset["config_path"], dataset["data_dir"])


def test_complete_training_resume_and_separate_final_test(dataset, fake_training):
    selection = run.train("ibm", "fixture", **dataset)
    directory = dataset["artifact_root"] / "ibm-fixture"
    assert selection["required_architecture_bakeoff_complete"]
    assert len(fake_training) == 18
    assert [row[3] for row in fake_training if row[3]] == [8, 8, 8]
    assert not (directory / "predictions-test.npz").exists()
    assert not (directory / "results.json").exists()
    assert all(c["eligible"] for c in selection["conditions"].values())
    assert run.train("ibm", "fixture", resume=True, **dataset) == selection
    assert len(fake_training) == 18
    with pytest.raises(ValueError, match="--resume"):
        run.train("ibm", "fixture", **dataset)
    result = run.evaluate("ibm", "fixture", **dataset)
    assert len(result["test"]) == 24  # 6 baselines plus 18 fitted forecasts
    assert result["primary_comparison"]["decision"]["promote_neural"] is False
    assert result["default_model"] == selection["selected_baseline"]
    assert set(result["primary_ssl_same_seed_comparisons"]) == {"11", "23", "47"}
    assert all(v["matched_actual_updates"] == v["matched_target_updates"] == 8 for v in result["primary_ssl_same_seed_comparisons"].values())
    assert run.digest(directory / "source-policy.json") == run.digest(dataset["config_path"])
    with pytest.raises(ValueError, match="already evaluated"):
        run.evaluate("ibm", "fixture", **dataset)


def test_changed_frozen_selection_prevents_final_test(dataset, fake_training):
    run.train("ibm", "tamper", **dataset)
    path = dataset["artifact_root"] / "ibm-tamper" / "selection.json"
    changed = json.loads(path.read_text())
    changed["selected_neural"] = "arbitrary"
    save(path, changed)
    with pytest.raises(ValueError, match="not frozen"):
        run.evaluate("ibm", "tamper", **dataset)


def test_partial_units_are_not_overwritten(tmp_path):
    np.savez(tmp_path / "unfinished.npz", weight=np.zeros(3))
    with pytest.raises(ValueError, match="partial unit"):
        run._record(tmp_path, "unfinished")


def test_berka_transfer_uses_frozen_donor_and_separate_source_policy(dataset, fake_training):
    run.train("ibm", "donor", **dataset)
    ibm_run = dataset["artifact_root"] / "ibm-donor"
    directory = dataset["data_dir"].parent / "berka-v2"
    directory.mkdir()
    (directory / "berka_windows.npz").write_bytes((dataset["data_dir"] / "ibm_windows.npz").read_bytes())
    audit = json.loads((dataset["data_dir"] / "ibm_audit.json").read_text())
    audit["train_verdict"] = "train_for_limited_retrospective_research_only"
    for v in audit["split_integrity"].values():
        v["shared_accounts"] = v.pop("shared_groups")
        v["shared_components"] = 0
    save(directory / "berka_audit.json", audit)
    save(directory / "policy.json", {"frozen_before_training": True, "currency": "SOURCE_NATIVE", "target": "total_posted_outflow"})
    save(directory / "berka_manifest.json", {"source": "berka", "synthetic": False, "currency": "SOURCE_NATIVE", "target": "total_posted_outflow",
         "data_sha256": run.digest(directory / "berka_windows.npz"), "audit_sha256": run.digest(directory / "berka_audit.json"), "evaluation_sha256": run.digest(directory / "policy.json")})
    arguments = {**dataset, "data_dir": directory}
    selection = run.train("berka", "transfer", ibm_run=ibm_run, **arguments)
    assert selection["all_expected_runs_finished"]
    assert set(selection["conditions"]) == {"scratch", "berka_ssl_then_berka_forecast", "ibm_ssl_then_berka_forecast", "ibm_forecast_then_berka_forecast", "compute_matched_scratch"}
    assert len(fake_training) == 42
    out = dataset["artifact_root"] / "berka-transfer"
    assert run.digest(out / "source-policy.json") == run.digest(directory / "policy.json")
    result = run.evaluate("berka", "transfer", **arguments)
    assert result["primary_comparison"]["paired_uncertainty"]["unit"] == "account-client connected component"
    fingerprints_path = ibm_run / "fingerprints.json"
    fingerprints_path.write_text(fingerprints_path.read_text() + " ")
    with pytest.raises(ValueError, match="not frozen"):
        run.train("berka", "bad-donor", ibm_run=ibm_run, **arguments)


def test_completeness_and_baseline_schema_are_enforced(dataset, tmp_path):
    config = json.loads(dataset["config_path"].read_text())
    with pytest.raises(ValueError, match="all expected"):
        run._check_complete([], config, "ibm")
    path = tmp_path / "ridge.npz"
    np.savez(path, metadata=np.frombuffer(b'{"kind":"ridge"}', dtype=np.uint8),
             feature_mean=np.zeros(99), feature_std=np.zeros(99), coef=np.zeros((100, 14)))
    with pytest.raises(ValueError, match="weights/standardizer"):
        run._baseline_predict(path, np.ones((1, 56)), np.array([0]))


def test_selection_requires_all_three_seeds_and_compute_match(dataset):
    config = json.loads(dataset["config_path"].read_text())
    records = [{"name": "baseline", "family": "baseline", "validation": {"14day_total_mae": 5}}]
    for kind in run.KINDS:
        for seed in (11, 23, 47):
            records.append({"name": f"{kind}-{seed}", "family": "learned", "condition": "scratch", "kind": kind,
                            "seed": seed, "training": {"epochs_run": 3}, "validation": {"14day_total_mae": 1 if kind == "mlp" else 3}})
    records[1]["training"]["epochs_run"] = 2
    for seed in (11, 23, 47):
        records.append({"name": f"matched-{seed}", "family": "learned", "condition": "compute_matched_scratch", "kind": "transformer",
                        "seed": seed, "training": {"epochs_run": 3, "fixed_updates_reached": seed != 47}, "validation": {"14day_total_mae": .5}})
    selection = run.choose(records, config, "ibm")
    assert not selection["architecture_eligibility"]["mlp"]["eligible"]
    assert not selection["selected_neural"].startswith("mlp")
    assert not selection["required_architecture_bakeoff_complete"]
    assert selection["conditions"]["compute_matched_scratch"]["selected"] is None
