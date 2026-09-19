"""Prepare new IBM periods while preserving the original held-out people."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .prepare import ROOT, aggregate_ibm, audit_windows, build_windows, date_string, file_sha256, group_split


def preparation_policy(policy: dict) -> dict:
    if policy.get("version") != "forecast-v2" or policy.get("frozen_before_training") is not True:
        raise ValueError("Expected frozen forecast-v2 policy")
    if policy["ibm"].get("group_split_version") != "forecast-v1":
        raise ValueError("Preserve original IBM customer holdouts")
    if policy["ibm"]["years"] != {"train": [2016, 2017], "validation": [2018], "test": [2019]}:
        raise ValueError("Unexpected v2 target years")
    result = copy.deepcopy(policy)
    result["version"] = policy["ibm"]["group_split_version"]
    return result


def prepare_ibm_v2(config_path=ROOT / "evaluation-v2.json", output_dir=ROOT / "data/processed/ibm-v2"):
    config_path, output_dir = Path(config_path), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Preserve existing preparation: {output_dir}")
    started = time.perf_counter()
    policy_bytes = config_path.read_bytes()
    policy = json.loads(policy_bytes)
    config = preparation_policy(policy)
    source_path = ROOT / "data/raw/ibm-source.json"
    source = json.loads(source_path.read_text())
    raw_path = source_path.parent / source["raw_relative_path"]
    raw_hash = file_sha256(raw_path)
    if raw_hash != source["download"]["sha256"] or raw_path.stat().st_size != source["download"]["bytes"]:
        raise ValueError("Raw IBM source changed")
    daily = aggregate_ibm(raw_path, config)
    arrays, eligibility = build_windows(daily, config, "ibm")
    audit = audit_windows(arrays, "ibm")
    for split in ("train", "validation", "test"):
        if any(group_split(str(g), "forecast-v1") != split for g in arrays[f"{split}_group"]):
            audit["blocking_items"].append(f"{split}: original customer holdout violated")
    audit.update(source="ibm", raw=daily.audit, source_start=date_string(daily.source_start),
                 source_end=date_string(daily.source_end), eligibility=eligibility,
                 test_scope=policy["ibm"]["test_scope"])
    audit["train_verdict"] = "do_not_train" if audit["blocking_items"] else "train_for_limited_research_only"
    if config_path.read_bytes() != policy_bytes:
        raise ValueError("Policy changed during preparation")
    output_dir.mkdir(parents=True)
    (output_dir / "evaluation-v2.json").write_bytes(policy_bytes)
    audit["elapsed_seconds"] = time.perf_counter() - started
    audit_path = output_dir / "ibm_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, allow_nan=False) + "\n")
    if audit["blocking_items"]:
        raise ValueError(f"Audit blocks training: {audit['blocking_items']}")
    metadata = {
        "schema_version": 2, "source": "ibm", "target": "card_spending", "currency": "USD",
        "synthetic": True, "experimental": True, "context_days": 56, "horizon_days": 14,
        "amount_units": "major source monetary units", "origin_units": "integer Unix day, first forecast date",
        "source_sha256": raw_hash, "evaluation_sha256": hashlib.sha256(policy_bytes).hexdigest(),
        "group_split_version": "forecast-v1", "real_world_validated": False,
        "observation_assumption": daily.audit["missing_day_policy"], "bill_exclusion": daily.audit["bill_exclusion"],
    }
    arrays["metadata"] = np.asarray(json.dumps(metadata, sort_keys=True))
    data_path = output_dir / "ibm_windows.npz"
    np.savez_compressed(data_path, **arrays)
    manifest = dict(metadata, data_file=data_path.name, data_sha256=file_sha256(data_path),
                    data_bytes=data_path.stat().st_size, audit_file=audit_path.name,
                    audit_sha256=file_sha256(audit_path),
                    window_counts={s: len(arrays[f"{s}_origin"]) for s in ("train", "validation", "test")},
                    preprocessing_seconds=time.perf_counter() - started)
    (output_dir / "ibm_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # IDs and origins make the actual split independently inspectable before fitting.
    split_manifest = {s: {"groups": sorted(set(arrays[f"{s}_group"].tolist())),
                          "origins": sorted(set(arrays[f"{s}_origin"].tolist())),
                          "windows": len(arrays[f"{s}_origin"])} for s in ("train", "validation", "test")}
    (output_dir / "split-manifest.json").write_text(json.dumps(split_manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "evaluation-v2.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/ibm-v2")
    args = parser.parse_args()
    print(json.dumps(prepare_ibm_v2(args.config, args.output_dir), indent=2), flush=True)
