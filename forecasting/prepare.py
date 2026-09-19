"""Prepare audited daily forecast windows from untouched, licensed raw sources.

Run ``python -m forecasting.prepare --source ibm`` (or ``moneydata``). The
evaluation policy must already be frozen. Raw files are verified, never edited.
Dates absent from the source are assumed observed zeros inside the explicitly
described observation interval; this assumption is not proof of completeness.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import tarfile
import time
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SPLITS = ("train", "validation", "test")
EPOCH = date(1970, 1, 1)


def day_number(value: str | date) -> int:
    return ((date.fromisoformat(value) if isinstance(value, str) else value) - EPOCH).days


def date_string(value: int) -> str:
    return str(np.datetime64(int(value), "D"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def group_split(group: str, version: str = "forecast-v1") -> str:
    number = int.from_bytes(hashlib.sha256(f"{version}:{group}".encode()).digest(), "big")
    # Integer comparisons reproduce exact 70/15/15 fractions without float loss.
    if number * 10 < (1 << 256) * 7:
        return "train"
    if number * 20 < (1 << 256) * 17:
        return "validation"
    return "test"


def money_cents(values: pd.Series, *, dollar_prefix: bool = False, allow_blank: bool = False) -> np.ndarray:
    """Parse decimal source money without rounding malformed/fractional cents."""
    text = values.astype(str).str.strip()
    if dollar_prefix:
        text = text.str.removeprefix("$")
    if allow_blank:
        text = text.replace("", "0")
    good = text.str.fullmatch(r"-?\d+(?:\.\d{1,2})?")
    if not good.all():
        raise ValueError(f"Malformed monetary values: {text[~good].head(20).tolist()}")
    # Validated strings have at most two decimal places. Integer-string parsing
    # avoids dependence on floating point at the source aggregation boundary.
    negative = text.str.startswith("-").to_numpy()
    unsigned = text.str.removeprefix("-")
    pieces = unsigned.str.split(".", n=1, expand=True)
    whole_text = pieces[0].str.lstrip("0").replace("", "0")
    if (whole_text.str.len() > 11).any():
        raise ValueError("Source monetary amount exceeds supported bound")
    whole = pd.to_numeric(whole_text, errors="raise").to_numpy(dtype=np.int64)
    if np.any(whole > 10**10):
        raise ValueError("Source monetary amount exceeds supported bound")
    fraction = pieces[1].fillna("").str.pad(2, side="right", fillchar="0") if pieces.shape[1] == 2 else pd.Series("00", index=text.index)
    cents = whole * 100 + pd.to_numeric(fraction, errors="raise").to_numpy(dtype=np.int64)
    return np.where(negative, -cents, cents)


@dataclass
class DailyData:
    """Integer-cent daily arrays over a shared calendar; earliest is causal."""

    start: int
    end: int
    amounts: dict[str, np.ndarray]
    earliest: dict[str, int]
    source_start: int
    source_end: int
    audit: dict[str, Any]


def calendar_bounds(config: dict, source: str) -> tuple[int, int]:
    years = [year for values in config[source]["years"].values() for year in values]
    return day_number(date(min(years), 1, 1)) - config["context_days"], day_number(date(max(years), 12, 31))


def _require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing raw columns: {sorted(missing)}")


def _add_daily(amounts: dict[str, np.ndarray], groups: np.ndarray, dates: np.ndarray, cents: np.ndarray, start: int, end: int) -> None:
    selected = (dates >= start) & (dates <= end)
    frame = pd.DataFrame({"group": groups[selected], "date": dates[selected], "cents": cents[selected]})
    for group, block in frame.groupby("group", sort=False):
        values = amounts.setdefault(str(group), np.zeros(end - start + 1, dtype=np.int64))
        np.add.at(values, block["date"].to_numpy(dtype=np.int64) - start, block["cents"].to_numpy(dtype=np.int64))


def aggregate_ibm(raw_path: Path, config: dict, *, chunksize: int = 250_000) -> DailyData:
    """Stream IBM archive/CSV, retaining exact rows including repeated events."""
    start, end = calendar_bounds(config, "ibm")
    amounts: dict[str, np.ndarray] = {}
    earliest: dict[str, int] = {}
    counts = {key: 0 for key in ("raw_rows", "qualifying_rows", "error_rows", "nonpositive_rows", "error_and_nonpositive_rows", "positive_fraud_rows_kept", "negative_refund_rows", "zero_amount_rows")}
    raw_groups: set[str] = set()
    hashes = []
    source_start, source_end = 10**12, -10**12
    weekday_counts = np.zeros(7, dtype=np.int64)
    archive = None
    stream = None
    try:
        if tarfile.is_tarfile(raw_path):
            archive = tarfile.open(raw_path, "r:*")
            members = [member for member in archive.getmembers() if member.isfile() and member.name.lower().endswith(".csv")]
            if len(members) != 1:
                raise ValueError(f"Expected exactly one CSV archive member; found {[member.name for member in members]}")
            stream = archive.extractfile(members[0])
            archive_member = members[0].name
        else:
            stream = raw_path.open("rb")
            archive_member = None
        for frame in pd.read_csv(stream, dtype=str, keep_default_na=False, chunksize=chunksize):
            _require_columns(frame, ["User", "Card", "Year", "Month", "Day", "Amount", "Errors?"])
            groups = frame["User"].to_numpy(dtype=str)
            if (frame["User"].str.strip() == "").any():
                raise ValueError("Missing customer identifier")
            parsed = pd.to_datetime(frame[["Year", "Month", "Day"]].rename(columns=str.lower), errors="coerce")
            if parsed.isna().any():
                raise ValueError(f"Invalid source dates at rows {frame.index[parsed.isna()].tolist()[:20]}")
            dates = parsed.to_numpy(dtype="datetime64[D]").astype(np.int64)
            cents = money_cents(frame["Amount"], dollar_prefix=True)
            errors = frame["Errors?"].str.strip().ne("").to_numpy()
            nonpositive = cents <= 0
            keep = ~errors & ~nonpositive
            counts["raw_rows"] += len(frame)
            counts["qualifying_rows"] += int(keep.sum())
            counts["error_rows"] += int(errors.sum())
            counts["nonpositive_rows"] += int(nonpositive.sum())
            counts["error_and_nonpositive_rows"] += int((errors & nonpositive).sum())
            counts["negative_refund_rows"] += int((cents < 0).sum())
            counts["zero_amount_rows"] += int((cents == 0).sum())
            if "Is Fraud?" in frame:
                counts["positive_fraud_rows_kept"] += int((keep & frame["Is Fraud?"].str.casefold().eq("yes").to_numpy()).sum())
            raw_groups.update(groups.tolist())
            source_start, source_end = min(source_start, int(dates.min())), max(source_end, int(dates.max()))
            weekday_counts += np.bincount((dates + 3) % 7, minlength=7)
            # Hash all columns, never index; duplicate count is an explicitly
            # disclosed 64-bit row-hash estimate, not an event deduplication rule.
            hashes.append(pd.util.hash_pandas_object(frame, index=False).to_numpy())
            causal_first = pd.DataFrame({"group": groups[keep], "date": dates[keep]}).groupby("group")["date"].min()
            for group, value in causal_first.items():
                earliest[str(group)] = min(earliest.get(str(group), int(value)), int(value))
            _add_daily(amounts, groups[keep], dates[keep], cents[keep], start, end)
        if not counts["raw_rows"]:
            raise ValueError("Empty source")
        all_hashes = np.concatenate(hashes)
        duplicate_estimate = int(len(all_hashes) - len(np.unique(all_hashes)))
    finally:
        if stream is not None:
            stream.close()
        if archive is not None:
            archive.close()
    # Include historically active customers even if all dates in the evaluated
    # interval are zero, avoiding future-activity-conditioned selection.
    for group in earliest:
        amounts.setdefault(group, np.zeros(end - start + 1, dtype=np.int64))
    audit = {
        **counts, "raw_groups": len(raw_groups), "qualifying_groups": len(earliest),
        "raw_exact_duplicate_estimate": duplicate_estimate,
        "duplicate_method": "All rows/all columns; pandas 64-bit row hash, collision possibility. Retain every row because no unique event identifier proves duplication.",
        "raw_weekday_counts_monday_first": weekday_counts.tolist(),
        "archive_member": archive_member,
        "missing_day_policy": "Observed-zero assumption from first qualifying successful positive transaction through global dataset end. Account-specific closure or missing coverage is unverified; no future last-activity eligibility filter.",
        "bill_exclusion": "none; target is synthetic card spending, not residual checking-account outflow",
        "fraud_policy": "Positive successful charges retained regardless of fraud annotation; annotation is neither feature nor eligibility signal.",
    }
    return DailyData(start, end, amounts, earliest, source_start, source_end, audit)


def aggregate_moneydata(raw_path: Path, config: dict) -> DailyData:
    frame = pd.read_csv(raw_path, dtype=str, keep_default_na=False)
    _require_columns(frame, ["Transaction Number", "Transaction Date", "Debit Amount", "Credit Amount"])
    if not len(frame):
        raise ValueError("Empty source")
    dates = pd.to_datetime(frame["Transaction Date"], format="%d/%m/%Y", errors="coerce")
    if dates.isna().any():
        raise ValueError(f"Invalid source dates at rows {frame.index[dates.isna()].tolist()[:20]}")
    days = dates.to_numpy(dtype="datetime64[D]").astype(np.int64)
    debits = money_cents(frame["Debit Amount"], allow_blank=True)
    credits = money_cents(frame["Credit Amount"], allow_blank=True)
    if np.any(debits < 0) or np.any(credits < 0):
        raise ValueError("Unexpected negative debit/credit requires target-policy review")
    if np.any((debits > 0) & (credits > 0)):
        raise ValueError("Rows containing both debit and credit require target-policy review")
    start, end = calendar_bounds(config, "moneydata")
    amounts: dict[str, np.ndarray] = {}
    group = "moneydata-person-1"
    _add_daily(amounts, np.full(len(frame), group), days, debits, start, end)
    amounts.setdefault(group, np.zeros(end - start + 1, dtype=np.int64))
    audit = {
        "raw_rows": len(frame), "raw_groups": 1, "qualifying_rows": int((debits > 0).sum()),
        "credit_rows_excluded_from_outflow": int((credits > 0).sum()),
        "zero_amount_rows": int(((debits == 0) & (credits == 0)).sum()),
        "raw_exact_duplicates": int(frame.duplicated().sum()),
        "duplicate_transaction_numbers": int(frame["Transaction Number"].duplicated().sum()),
        "duplicate_method": "Exact complete string-row comparison; all rows retained.",
        "raw_weekday_counts_monday_first": np.bincount((days + 3) % 7, minlength=7).tolist(),
        "missing_day_policy": "Absent posted dates are assumed observed zero from first through last published entry. Weekend transactions post on Monday; this measures posted debits rather than actual purchase timing.",
        "bill_exclusion": "none; gross positive posted debits include bills, transfers, cash withdrawals, and discretionary purchases; credits never offset debits",
        "representativeness": "Exactly one person, temporal case study only; group generalization cannot be measured.",
    }
    return DailyData(start, end, amounts, {group: int(days.min())}, int(days.min()), int(days.max()), audit)


def build_windows(daily: DailyData, config: dict, source: str) -> tuple[dict[str, np.ndarray], dict]:
    context, horizon, stride = (int(config[key]) for key in ("context_days", "horizon_days", "origin_stride_days"))
    if context != 56 or horizon != 14 or stride != 15:
        raise ValueError("This experiment requires frozen 56/14/15 window dimensions")
    if source == "ibm" and config[source]["split_fractions"] != [.7, .15, .15]:
        raise ValueError("This experiment requires the frozen customer split fractions")
    arrays: dict[str, np.ndarray] = {}
    eligibility = {}
    for split in SPLITS:
        histories, targets, groups, origins = [], [], [], []
        considered, outside_coverage, insufficient_history = 0, 0, 0
        for group in sorted(daily.amounts):
            if source == "ibm" and group_split(group, config["version"]) != split:
                continue
            for year in config[source]["years"][split]:
                first, last = day_number(date(year, 1, 1)), day_number(date(year, 12, 31))
                for origin in range(first, last - horizon + 2, stride):
                    considered += 1
                    if origin - context < daily.source_start or origin + horizon - 1 > daily.source_end:
                        outside_coverage += 1
                        continue
                    if group not in daily.earliest or daily.earliest[group] > origin - context:
                        insufficient_history += 1
                        continue
                    offset = origin - daily.start
                    history = daily.amounts[group][offset - context:offset]
                    target = daily.amounts[group][offset:offset + horizon]
                    if len(history) != context or len(target) != horizon:
                        raise ValueError("Aggregation calendar does not cover requested window")
                    histories.append(history.astype(np.float64) / 100)
                    targets.append(target.astype(np.float64) / 100)
                    groups.append(group)
                    origins.append(origin)
        arrays[f"{split}_history"] = np.asarray(histories, dtype=np.float64).reshape(-1, context)
        arrays[f"{split}_y"] = np.asarray(targets, dtype=np.float64).reshape(-1, horizon)
        arrays[f"{split}_group"] = np.asarray(groups, dtype=str)
        arrays[f"{split}_origin"] = np.asarray(origins, dtype=np.int64)
        eligibility[split] = {"candidate_windows": considered, "outside_global_observation_span": outside_coverage, "first_qualifying_transaction_after_context_start": insufficient_history, "included_windows": len(origins)}
    return arrays, eligibility


def _summary(values: np.ndarray) -> dict:
    return {"min": float(values.min()), "max": float(values.max()), "mean": float(values.mean()), "quantiles_p0_p50_p90_p95_p99_p100": np.quantile(values, [0, .5, .9, .95, .99, 1]).tolist(), "zero_count": int((values == 0).sum())}


def audit_windows(arrays: dict[str, np.ndarray], source: str) -> dict:
    report: dict[str, Any] = {"splits": {}, "blocking_items": [], "warnings": []}
    sets, history_sets, key_sets = {}, {}, {}
    for split in SPLITS:
        history, y, groups, origins = [arrays[f"{split}_{name}"] for name in ("history", "y", "group", "origin")]
        n = len(origins)
        shapes = [list(history.shape), list(y.shape), list(groups.shape), list(origins.shape)]
        if history.shape != (n, 56) or y.shape != (n, 14) or groups.shape != (n,):
            report["blocking_items"].append(f"{split}: inconsistent tensor shapes {shapes}")
        nonfinite = int((~np.isfinite(history)).sum() + (~np.isfinite(y)).sum())
        negative = int((history < 0).sum() + (y < 0).sum())
        if nonfinite or negative or not n:
            report["blocking_items"].append(f"{split}: n={n}, nonfinite={nonfinite}, negative={negative}")
        if not n:
            report["splits"][split] = {"windows": 0, "shapes_history_y_group_origin": shapes}
            sets[split], history_sets[split], key_sets[split] = set(), set(), set()
            continue
        keys = [(str(group), int(origin)) for group, origin in zip(groups, origins, strict=True)]
        if len(set(keys)) != n:
            report["blocking_items"].append(f"{split}: duplicate group/origin records")
        weekdays = np.bincount((origins + 3) % 7, minlength=7)
        if np.any(weekdays == 0):
            report["blocking_items"].append(f"{split}: missing forecast start weekday")
        hashes = [hashlib.sha256(np.ascontiguousarray(row).tobytes()).hexdigest() for row in history]
        zero_rows = int(np.all(history == 0, axis=1).sum())
        report["splits"][split] = {
            "windows": n, "groups": len(set(groups)), "shapes_history_y_group_origin": shapes,
            "history_dtype": str(history.dtype), "target_dtype": str(y.dtype), "nonfinite": nonfinite,
            "negative": negative, "all_zero_histories": zero_rows,
            "constant_histories": int((np.ptp(history, axis=1) == 0).sum()),
            "duplicate_history_content_count": n - len(set(hashes)),
            "duplicate_group_origin_count": n - len(set(keys)),
            "history_length_min_max_mean_median_p5_p95": [56] * 6,
            "target_length_min_max_mean_median_p5_p95": [14] * 6,
            "origin_weekdays_monday_first": weekdays.tolist(),
            "context_start_min": date_string(int(origins.min()) - 56),
            "target_start_min": date_string(int(origins.min())),
            "target_end_max": date_string(int(origins.max()) + 13),
            "history_amounts": _summary(history), "target_total_14days": _summary(y.sum(axis=1)),
            "target_heads": [{"day": i + 1, **_summary(y[:, i])} for i in range(14)],
        }
        if zero_rows:
            report["warnings"].append(f"{split}: {zero_rows}/{n} histories entirely zero; retained under causal activity/completeness policy, not treated as missing automatically")
        sets[split], history_sets[split], key_sets[split] = set(groups), set(hashes), set(keys)
    comparisons = {}
    for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
        group_overlap, key_overlap = len(sets[a] & sets[b]), len(key_sets[a] & key_sets[b])
        ah, bh = arrays[f"{a}_origin"], arrays[f"{b}_origin"]
        chronological = not len(ah) or not len(bh) or int(ah.max()) + 13 < int(bh.min())
        comparisons[f"{a}_vs_{b}"] = {"shared_groups": group_overlap, "identical_group_origin_records": key_overlap, "shared_history_content_hashes": len(history_sets[a] & history_sets[b]), "all_target_dates_strictly_ordered": chronological}
        if key_overlap or not chronological or (source == "ibm" and group_overlap):
            report["blocking_items"].append(f"{a}/{b}: split leakage or chronological-order violation")
    report["split_integrity"] = comparisons
    report["group_overlap_policy"] = "No customer may cross splits" if source == "ibm" else "The same single customer intentionally appears in temporal splits; this cannot establish generalization to unseen people"
    report["content_duplicate_policy"] = "Identical numeric histories alone do not prove record leakage (especially all-zero histories). Report content overlap separately from group/origin keys."
    report["train_verdict"] = "do_not_train" if report["blocking_items"] else "train_for_limited_research_only"
    return report


def prepare(source: str, *, config_path: Path = ROOT / "evaluation.json", raw_dir: Path = ROOT / "data" / "raw", output_dir: Path = ROOT / "data" / "processed") -> dict:
    started = time.perf_counter()
    config = json.loads(config_path.read_text())
    if config.get("frozen_before_training") is not True:
        raise ValueError("Freeze evaluation policy before preparing training data")
    manifest_path = raw_dir / f"{source}-source.json"
    raw_manifest = json.loads(manifest_path.read_text())
    raw_path = raw_dir / raw_manifest["raw_relative_path"]
    raw_hash = file_sha256(raw_path)
    if raw_hash != raw_manifest["download"]["sha256"] or raw_path.stat().st_size != raw_manifest["download"]["bytes"]:
        raise ValueError("Raw source checksum/size changed after acquisition")
    daily = aggregate_ibm(raw_path, config) if source == "ibm" else aggregate_moneydata(raw_path, config)
    arrays, eligibility = build_windows(daily, config, source)
    audit = audit_windows(arrays, source)
    audit.update({"source": source, "raw": daily.audit, "source_start": date_string(daily.source_start), "source_end": date_string(daily.source_end), "eligibility": eligibility})
    # A long raw scan may overlap work on an unrelated source's metadata. The
    # output records the final evaluation document only when every setting that
    # governed this preparation still agrees; a changed source policy aborts.
    final_config = json.loads(config_path.read_text())
    relevant_keys = ("version", "frozen_before_training", "context_days", "horizon_days", "origin_stride_days", source)
    if any(config[key] != final_config[key] for key in relevant_keys):
        raise ValueError("Source preparation policy changed during the raw scan; rerun against the frozen policy")
    metadata = {
        "schema_version": 1, "source": source, "target": config[source]["target"], "currency": config[source]["currency"],
        "synthetic": config[source]["synthetic"], "experimental": True,
        "context_days": 56, "horizon_days": 14, "amount_units": "major currency units", "origin_units": "days since 1970-01-01; first forecast day",
        "source_sha256": raw_hash, "evaluation_sha256": file_sha256(config_path),
        "source_manifest": str(manifest_path.relative_to(ROOT) if manifest_path.is_relative_to(ROOT) else manifest_path),
        "observation_assumption": daily.audit["missing_day_policy"], "bill_exclusion": daily.audit["bill_exclusion"],
        "real_world_validated": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_path, data_path = output_dir / f"{source}_audit.json", output_dir / f"{source}_windows.npz"
    audit["elapsed_seconds"] = time.perf_counter() - started
    audit_path.write_text(json.dumps(audit, indent=2) + "\n")
    if audit["blocking_items"]:
        raise ValueError(f"Numeric audit blocks training; see {audit_path}: {audit['blocking_items']}")
    arrays["metadata"] = np.asarray(json.dumps(metadata, sort_keys=True))
    np.savez_compressed(data_path, **arrays)
    manifest = {**metadata, "data_file": data_path.name, "data_sha256": file_sha256(data_path), "data_bytes": data_path.stat().st_size, "audit_file": audit_path.name, "audit_sha256": file_sha256(audit_path), "window_counts": {split: len(arrays[f"{split}_origin"]) for split in SPLITS}, "preprocessing_seconds": time.perf_counter() - started}
    (output_dir / f"{source}_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, choices=("ibm", "moneydata"))
    parser.add_argument("--config", type=Path, default=ROOT / "evaluation.json")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "processed")
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, config_path=args.config, raw_dir=args.raw_dir, output_dir=args.output_dir), indent=2), flush=True)


if __name__ == "__main__":
    main()
