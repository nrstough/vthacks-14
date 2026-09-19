"""Acquire the original PKDD'99 archive and prepare a frozen research benchmark.

No balances, demographic fields, or loan labels become forecasting inputs.
Raw data stays local; modern redistribution terms are not established.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.request import urlopen
import zipfile

import numpy as np
import pandas as pd

from forecasting.prepare import SPLITS, audit_windows, date_string, day_number, file_sha256, group_split, money_cents

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data/raw/berka"
OUT = ROOT / "data/processed/berka-v2"
URL = "https://web.archive.org/web/20070214120527id_/http://lisp.vse.cz/pkdd99/DATA/data_berka.zip"
SHA256 = "affa4477572e9d8f2de6beff8a525d37c056d5d8e4a9670dd8c7636208c002ce"
BYTES = 18074591
DICTIONARY = "https://web.archive.org/web/20180506035658/http://lisp.vse.cz/pkdd99/Challenge/berka.htm"
CALL = "https://web.archive.org/web/20180506061559/http://lisp.vse.cz/pkdd99/Challenge/chall.htm"


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def acquire(raw_dir: Path = RAW) -> dict:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / "data_berka.zip"
    if not path.exists():
        partial = path.with_suffix(".zip.partial")
        with urlopen(URL, timeout=90) as response, partial.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        if partial.stat().st_size != BYTES or file_sha256(partial) != SHA256:
            raise ValueError("Downloaded Berka archive differs from frozen source")
        partial.rename(path)
    if path.stat().st_size != BYTES or file_sha256(path) != SHA256:
        raise ValueError("Berka archive checksum or size mismatch")
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archive CRC failure")
        members = {item.filename: {"bytes": item.file_size, "sha256": hashlib.sha256(archive.read(item)).hexdigest()} for item in archive.infolist()}
    manifest = {
        "source": "Original PKDD'99 Financial / Berka archive", "archive_url": URL,
        "archive_original_url": "http://lisp.vse.cz/pkdd99/DATA/data_berka.zip",
        "accessed_utc": datetime.now(timezone.utc).isoformat(), "raw_file": path.name,
        "bytes": BYTES, "sha256": SHA256, "members": members,
        "dictionary_url": DICTIONARY, "original_research_call_url": CALL,
        "current_repository_url": "https://relational.fel.cvut.cz/dataset/Financial",
        "rights": {
            "research_basis": "Original authors publicly supplied the archive for a knowledge-discovery research challenge; CTU currently publicly offers database export to support relational machine learning. Used locally for this authorized research benchmark.",
            "formal_license": "No modern standardized data license found in the reviewed original guide, call, or current repository page.",
            "redistribution": "Not established; do not publish raw or derived records or imply an unrelated mirror's license applies.",
            "attribution": "Petr Berka and Marta Sochorova, PKDD'99 Financial Data Set; current repository context: Jan Motl and Oliver Schulte, The CTU Prague Relational Learning Repository.",
        },
    }
    save_json(raw_dir / "source.json", manifest)
    return manifest


def default_policy() -> dict:
    return {
        "version": "berka-forecast-v2", "frozen_before_training": True,
        "context_days": 56, "horizon_days": 14, "origin_stride_days": 15,
        "years": {"train": [1993, 1994, 1995, 1996], "validation": [1997], "test": [1998]},
        "period_choice": "Chosen from raw coverage 1993-01-01 through 1998-12-31, before model training or scores; targets must end in assigned year.",
        "origin_grid": "January 1 plus multiples of 15 days within each assigned year",
        "split_fractions": [0.7, 0.15, 0.15],
        "split_unit": "Connected component of account-client bipartite disposition graph; stable ID is berka-component- plus numerically smallest account ID",
        "split_hash": "Full sha256('berka-forecast-v2:' + component), exact integer thresholds 70/15/15",
        "record_unit": "Individual account at forecast origin; component is cluster/bootstrap key",
        "debit_types": ["VYDAJ", "VYBER"], "credit_types": ["PRIJEM"],
        "type_note": "Dictionary defines VYDAJ as withdrawal; raw source also has VYBER only with operation VYBER (dictionary: cash withdrawal). Include both as debit types and audit balance-change evidence; never treat VYBER as credit.",
        "target": "total_posted_outflow", "amount_policy": "Sum strictly positive debits in exact hundredths; zero debits excluded, credits not netted. Includes cash withdrawals, transfers, bills and charges; no residual/discretionary claim.",
        "currency": "SOURCE_NATIVE", "currency_note": "Historical Czech-bank context suggests Czech crowns but inspected primary dictionary/archive do not explicitly identify currency. No currency conversion or USD relabeling.",
        "observation_assumption": "Absent dates are assumed observed zeros from max(account opening date, first recorded transaction) through global source end; account closure/feed completeness unverified. No last-activity or future-activity eligibility filter.",
        "features": "Only historical daily outflow and causal calendar features; no balance, demographics, loan outcome, permanent-order or future-derived feature.",
        "source_sha256": SHA256, "synthetic": False,
        "transfer_scope": "IBM 2016-2017 pretraining into Berka 1990s is retrospective domain-transfer research; it is not an as-of-1990s deployed forecast.",
        "final_test": "Freeze before any training; select with validation only; final 1998 held-out components once after selection. No retuning on test.",
    }


def parse_dates(values: pd.Series) -> np.ndarray:
    text = values.astype(str)
    if not text.str.fullmatch(r"9[0-9][0-9]{4}").all():
        raise ValueError("Expected explicit 1990s YYMMDD source dates")
    parsed = pd.to_datetime("19" + text, format="%Y%m%d", errors="raise")
    return parsed.to_numpy(dtype="datetime64[D]").astype(np.int64)


def components(accounts: pd.DataFrame, dispositions: pd.DataFrame, clients: pd.DataFrame) -> tuple[dict[str, str], dict]:
    account_ids, client_ids = set(accounts.account_id), set(clients.client_id)
    if accounts.account_id.duplicated().any() or clients.client_id.duplicated().any() or dispositions.disp_id.duplicated().any():
        raise ValueError("Duplicate relational primary key")
    if set(dispositions.account_id) - account_ids or set(dispositions.client_id) - client_ids:
        raise ValueError("Broken disposition foreign key")
    if account_ids - set(dispositions.account_id):
        raise ValueError("Accounts without client dispositions")
    parent = {"a:" + a: "a:" + a for a in account_ids}
    parent.update({"c:" + c: "c:" + c for c in client_ids})

    def root(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for row in dispositions.itertuples(index=False):
        left, right = root("a:" + row.account_id), root("c:" + row.client_id)
        if left != right:
            parent[right] = left
    clusters: dict[str, list[str]] = {}
    for account in account_ids:
        clusters.setdefault(root("a:" + account), []).append(account)
    lookup = {account: "berka-component-" + min(members, key=int) for members in clusters.values() for account in members}
    report = {
        "accounts": len(account_ids), "clients": len(client_ids), "dispositions": len(dispositions),
        "components": len(clusters), "component_account_sizes": dict(Counter(len(v) for v in clusters.values())),
        "clients_with_multiple_accounts": int((dispositions.groupby("client_id").account_id.nunique() > 1).sum()),
        "accounts_with_multiple_clients": int((dispositions.groupby("account_id").client_id.nunique() > 1).sum()),
        "duplicate_account_client_links": int(dispositions.duplicated(["account_id", "client_id"]).sum()),
        "missing_account_or_client_links": 0,
    }
    return lookup, report


def load_source(raw_path: Path) -> dict[str, pd.DataFrame]:
    if file_sha256(raw_path) != SHA256 or raw_path.stat().st_size != BYTES:
        raise ValueError("Raw archive differs from frozen source")
    with zipfile.ZipFile(raw_path) as archive:
        return {name: pd.read_csv(archive.open(name + ".asc"), sep=";", dtype=str, keep_default_na=False) for name in ("trans", "account", "disp", "client")}


def prepare_frames(frames: dict[str, pd.DataFrame], policy: dict) -> tuple[dict[str, np.ndarray], dict]:
    if policy.get("frozen_before_training") is not True or tuple(policy[k] for k in ("context_days", "horizon_days", "origin_stride_days")) != (56, 14, 15):
        raise ValueError("Freeze the 56/14/15 preparation policy first")
    if policy["split_fractions"] != [.7, .15, .15]:
        raise ValueError("Unexpected split fractions")
    trans, accounts, disp, clients = [frames[n] for n in ("trans", "account", "disp", "client")]
    if len(trans) == 0 or trans.trans_id.duplicated().any():
        raise ValueError("Empty transaction source or duplicate transaction key")
    if set(trans.account_id) - set(accounts.account_id):
        raise ValueError("Transaction references an unknown account")
    lookup, graph_audit = components(accounts, disp, clients)
    days, cents, balances = parse_dates(trans.date), money_cents(trans.amount), money_cents(trans.balance)
    if (cents < 0).any():
        raise ValueError("Unexpected negative amount requires policy review")
    known_types = set(policy["debit_types"] + policy["credit_types"])
    if set(trans.type) - known_types:
        raise ValueError("Unknown transaction direction")
    debit = trans.type.isin(policy["debit_types"]).to_numpy()
    # VYBER is an undocumented direction token but its documented operation
    # explicitly identifies cash withdrawal. Refuse any other operation.
    if (trans.loc[trans.type.eq("VYBER"), "operation"] != "VYBER").any():
        raise ValueError("VYBER direction no longer exclusively means cash withdrawal")
    keep = debit & (cents > 0)
    start, end = int(days.min()), int(days.max())
    opening = dict(zip(accounts.account_id, parse_dates(accounts.date), strict=True))
    events = pd.DataFrame({"account": trans.account_id, "day": days, "cents": cents, "balance": balances, "type": trans.type})
    first = events.groupby("account").day.min().to_dict()
    if any(day < opening[account] for account, day in first.items()):
        raise ValueError("Transactions predate account opening")
    amounts = {account: np.zeros(end - start + 1, dtype=np.int64) for account in first}
    for account, block in events[keep].groupby("account", sort=False):
        np.add.at(amounts[account], block.day.to_numpy() - start, block.cents.to_numpy())

    # There is no intraday ordering. Only compare adjacent observed dates where
    # both dates contain exactly one transaction. Gaps do not add hidden rows.
    perday = events.groupby(["account", "day"]).agg(count=("cents", "size"), amount=("cents", "first"), balance=("balance", "first"), kind=("type", "first")).reset_index()
    perday["previous_count"] = perday.groupby("account")["count"].shift()
    perday["previous_balance"] = perday.groupby("account").balance.shift()
    check = perday[(perday["count"] == 1) & (perday.previous_count == 1)].copy()
    check["expected_change"] = np.where(check.kind.isin(policy["debit_types"]), -check.amount, check.amount)
    check["discrepancy"] = check.balance - check.previous_balance - check.expected_change
    balance_audit = {str(kind): {"unambiguous_comparisons": len(block), "exact_match": int(block.discrepancy.eq(0).sum()), "within_one_source_unit": int(block.discrepancy.abs().le(100).sum()), "maximum_absolute_discrepancy_native": float(block.discrepancy.abs().max() / 100)} for kind, block in check.groupby("kind")}

    arrays: dict[str, np.ndarray] = {}
    eligibility = {}
    component_splits = {group: group_split(group, policy["version"]) for group in set(lookup.values())}
    for split in SPLITS:
        histories, targets, groups, account_keys, origins = [], [], [], [], []
        counts = {"candidate_windows": 0, "outside_global_span": 0, "insufficient_prior_observation": 0}
        for account in sorted(amounts, key=int):
            group = lookup[account]
            if component_splits[group] != split:
                continue
            for year in policy["years"][split]:
                for origin in range(day_number(date(year, 1, 1)), day_number(date(year, 12, 31)) - 12, 15):
                    counts["candidate_windows"] += 1
                    if origin - 56 < start or origin + 13 > end:
                        counts["outside_global_span"] += 1
                        continue
                    if max(opening[account], first[account]) > origin - 56:
                        counts["insufficient_prior_observation"] += 1
                        continue
                    offset = origin - start
                    histories.append(amounts[account][offset - 56:offset].astype(np.float64) / 100)
                    targets.append(amounts[account][offset:offset + 14].astype(np.float64) / 100)
                    groups.append(group); account_keys.append(account); origins.append(origin)
        arrays.update({f"{split}_history": np.asarray(histories, dtype=np.float64).reshape(-1, 56), f"{split}_y": np.asarray(targets, dtype=np.float64).reshape(-1, 14), f"{split}_group": np.asarray(groups, dtype=str), f"{split}_account": np.asarray(account_keys, dtype=str), f"{split}_origin": np.asarray(origins, dtype=np.int64)})
        eligibility[split] = {**counts, "included_windows": len(origins)}
    # Legacy audit uses group+origin as record key. Preserve individual account
    # keys for that check and separately enforce component-level separation.
    record_arrays = dict(arrays)
    for split in SPLITS:
        record_arrays[f"{split}_group"] = arrays[f"{split}_account"]
    audit = audit_windows(record_arrays, "ibm")
    for split in SPLITS:
        audit["splits"][split]["accounts"] = len(set(arrays[f"{split}_account"]))
        audit["splits"][split]["groups"] = len(set(arrays[f"{split}_group"]))
        audit["splits"][split]["duplicate_account_origin_count"] = audit["splits"][split].pop("duplicate_group_origin_count", 0)
        zero_indices = np.flatnonzero(np.all(arrays[f"{split}_history"] == 0, axis=1))[:20]
        audit["splits"][split]["all_zero_history_examples"] = [f"{arrays[f'{split}_account'][i]}@{date_string(int(arrays[f'{split}_origin'][i]))}" for i in zero_indices]
        heads = audit["splits"][split].get("target_heads", [])
        count = len(arrays[f"{split}_origin"])
        if heads:
            zero_fractions = [head["zero_count"] / count for head in heads]
            audit["splits"][split]["daily_target_zero_fraction_range"] = [min(zero_fractions), max(zero_fractions)]
            if max(zero_fractions) >= .8:
                audit["warnings"].append(f"{split}: daily-head zero fractions {min(zero_fractions):.2%}–{max(zero_fractions):.2%}; sparse regression requires 14-day-total error and underprediction metrics, not zero-class accuracy")
    for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
        overlap = len(set(arrays[f"{a}_group"]) & set(arrays[f"{b}_group"]))
        comparison = audit["split_integrity"][f"{a}_vs_{b}"]
        comparison["shared_accounts"] = comparison.pop("shared_groups")
        comparison["shared_components"] = overlap
        comparison["identical_account_origin_records"] = comparison.pop("identical_group_origin_records")
        if overlap:
            audit["blocking_items"].append(f"{a}/{b}: {overlap} shared account-client components")
        if comparison["shared_history_content_hashes"]:
            audit["warnings"].append(f"{a}/{b}: {comparison['shared_history_content_hashes']} identical numeric history patterns across distinct accounts; recorded as content overlap, not silently counted as independent patterns")
    audit["group_overlap_policy"] = "No connected account-client component may cross splits; account+origin is record key and component is bootstrap cluster"
    audit.update({"source": "berka", "source_start": date_string(start), "source_end": date_string(end), "eligibility": eligibility,
        "raw": {"rows": len(trans), "columns": trans.columns.tolist(), "table_rows_loaded": {key: len(value) for key, value in frames.items()}, "type_counts": trans.type.value_counts().to_dict(), "positive_debit_rows": int(keep.sum()), "credit_rows_excluded": int((~debit).sum()), "zero_debits_excluded": int((debit & (cents == 0)).sum()), "negative_amount_rows": int((cents < 0).sum()), "exact_duplicate_rows": int(trans.duplicated().sum()), "duplicate_transaction_ids": int(trans.trans_id.duplicated().sum()), "missing_values_by_column": {c: int(trans[c].str.strip().eq("").sum()) for c in trans.columns}, "weekday_counts_monday_first": np.bincount((days + 3) % 7, minlength=7).tolist(), "positive_debit_amount_quantiles": np.quantile(cents[keep] / 100, [0, .5, .9, .95, .99, 1]).tolist(), "all_transaction_year_counts": pd.Series([date.fromisoformat(date_string(int(d))).year for d in days]).value_counts().sort_index().to_dict(), "graph": graph_audit, "component_assignment_counts": dict(Counter(component_splits.values())), "balance_reconciliation": balance_audit,
        "balance_note": "Diagnostic only. Adjacent observed days each containing exactly one transaction; no intraday-order assumption. Balance is never a training feature or eligibility filter.", "missing_day_policy": policy["observation_assumption"], "bill_exclusion": "none; gross posted outflow includes recurring obligations and transfers", "currency": policy["currency"], "currency_note": policy["currency_note"]}})
    if any(v["within_one_source_unit"] < .95 * v["unambiguous_comparisons"] for v in balance_audit.values()):
        audit["warnings"].append("Balance reconciliation has discrepancies; ledger balance is not sufficiently established for exact balance modeling and is not a predictor input.")
    audit["warnings"].extend(["Historical Czech banking data is not representative of contemporary US students.", "SOURCE_NATIVE blocks direct currency-dependent product integration.", "Observation completeness and account closure are unverified; absent dates become zeros under a disclosed assumption.", "Gross outflow is not residual spending: inserting it alongside separately scheduled bills double counts obligations."])
    audit["train_verdict"] = "do_not_train" if audit["blocking_items"] else "train_for_limited_retrospective_research_only"
    return arrays, audit


def prepare(raw_dir: Path = RAW, output_dir: Path = OUT) -> dict:
    started = time.perf_counter()
    policy_path = output_dir / "policy.json"
    if not policy_path.exists():
        raise ValueError("Create and freeze policy.json before preparing windows")
    policy_bytes = policy_path.read_bytes()
    policy = json.loads(policy_bytes)
    raw_path = raw_dir / "data_berka.zip"
    arrays, audit = prepare_frames(load_source(raw_path), policy)
    if policy_path.read_bytes() != policy_bytes:
        raise ValueError("Policy changed during preparation")
    policy_hash = hashlib.sha256(policy_bytes).hexdigest()
    metadata = {"schema_version": 1, "source": "berka", "target": policy["target"], "currency": policy["currency"], "synthetic": False, "experimental": True, "context_days": 56, "horizon_days": 14, "amount_units": "major source-native monetary units", "origin_units": "days since 1970-01-01; first forecast day", "source_sha256": SHA256, "evaluation_sha256": policy_hash, "observation_assumption": policy["observation_assumption"], "bill_exclusion": "none; gross posted outflow", "real_world_validated": False, "record_key": "account + origin", "group_key": "account-client connected component", "transfer_scope": policy["transfer_scope"]}
    audit["preprocessing_seconds"] = time.perf_counter() - started
    audit_path = output_dir / "berka_audit.json"
    save_json(audit_path, audit)
    if audit["blocking_items"]:
        raise ValueError(f"Numeric audit blocks training: {audit['blocking_items']}")
    arrays["metadata"] = np.asarray(json.dumps(metadata, sort_keys=True))
    data_path = output_dir / "berka_windows.npz"
    temporary_data = data_path.with_suffix(".npz.partial")
    with temporary_data.open("wb") as stream:
        np.savez_compressed(stream, **arrays)
    temporary_data.replace(data_path)
    manifest = {**metadata, "data_file": data_path.name, "data_sha256": file_sha256(data_path), "data_bytes": data_path.stat().st_size, "audit_file": audit_path.name, "audit_sha256": file_sha256(audit_path), "policy_file": policy_path.name, "window_counts": {s: len(arrays[f"{s}_origin"]) for s in SPLITS}, "preprocessing_seconds": time.perf_counter() - started}
    save_json(output_dir / "berka_manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("acquire", "freeze", "prepare"))
    parser.add_argument("--raw-dir", type=Path, default=RAW)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    if args.action == "acquire":
        result = acquire(args.raw_dir)
    elif args.action == "freeze":
        path = args.output_dir / "policy.json"
        if path.exists():
            raise ValueError("Frozen policy already exists; do not overwrite")
        result = default_policy()
        save_json(path, result)
    else:
        result = prepare(args.raw_dir, args.output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
