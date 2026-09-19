import numpy as np
import pandas as pd
import pytest

from forecasting.berka import components, default_policy, load_source, parse_dates, prepare_frames
from forecasting.prepare import day_number, group_split


def frames():
    # Use enough distinct components to exercise each fixed hash partition.
    ids = [str(i) for i in range(1, 31)]
    accounts = pd.DataFrame({"account_id": ids, "date": ["930101"] * len(ids)})
    clients = pd.DataFrame({"client_id": ids})
    dispositions = pd.DataFrame({"disp_id": ids, "client_id": ids, "account_id": ids})
    records = []
    for account in ids:
        for day, kind, amount, operation in [("930101", "PRIJEM", "1000.00", "VKLAD"), ("960101", "VYDAJ", "1.23", "VYBER"), ("960101", "VYBER", "2.34", "VYBER"), ("960101", "PRIJEM", "8.90", "VKLAD"), ("981231", "VYDAJ", "0.00", "VYBER")]:
            records.append({"trans_id": str(len(records) + 1), "account_id": account, "date": day, "type": kind, "operation": operation, "amount": amount, "balance": "1000.00"})
    return {"trans": pd.DataFrame(records), "account": accounts, "disp": dispositions, "client": clients}


def test_dates_are_explicit_1990s_and_fail_malformed():
    assert parse_dates(pd.Series(["930101", "981231"])).tolist() == [day_number("1993-01-01"), day_number("1998-12-31")]
    for value in ["000101", "990230", "19930101", "931301"]:
        with pytest.raises(ValueError):
            parse_dates(pd.Series([value]))


def test_connected_components_prevent_shared_clients_crossing_holdouts():
    data = frames()
    extra = pd.DataFrame([{"disp_id": "100", "client_id": "1", "account_id": "2"}, {"disp_id": "101", "client_id": "2", "account_id": "3"}])
    data["disp"] = pd.concat([data["disp"], extra], ignore_index=True)
    lookup, audit = components(data["account"], data["disp"], data["client"])
    assert lookup["1"] == lookup["2"] == lookup["3"] == "berka-component-1"
    assert audit["components"] == 28
    arrays, audit = prepare_frames(data, default_policy())
    assert not audit["blocking_items"]
    assert all(v["shared_components"] == 0 for v in audit["split_integrity"].values())
    split = group_split("berka-component-1", "berka-forecast-v2")
    assert {"1", "2", "3"} <= set(arrays[f"{split}_account"])
    assert audit["splits"][split]["duplicate_account_origin_count"] == 0


def test_exact_positive_debits_and_no_credit_netting():
    arrays, audit = prepare_frames(frames(), default_policy())
    account = next(str(i) for i in range(1, 31) if group_split(f"berka-component-{i}", "berka-forecast-v2") == "train")
    mask = (arrays["train_account"] == account) & (arrays["train_origin"] == day_number("1996-01-01"))
    assert mask.sum() == 1
    assert arrays["train_y"][mask][0, 0] == 3.57
    assert audit["raw"]["positive_debit_rows"] == 60
    assert audit["raw"]["zero_debits_excluded"] == 30
    assert audit["raw"]["credit_rows_excluded"] == 60
    assert not audit["blocking_items"]
    for split in ("train", "validation", "test"):
        assert arrays[f"{split}_history"].shape[1] == 56
        assert arrays[f"{split}_y"].shape[1] == 14
        assert len(set((arrays[f"{split}_origin"] + 3) % 7)) == 7
    assert audit["splits"]["validation"]["all_zero_histories"] > 0


def test_future_transactions_do_not_control_prior_window_eligibility():
    data = frames()
    earlier, _ = prepare_frames(data, default_policy())
    # Keep one source-end row, remove every other account's future activity.
    data["trans"] = data["trans"][~(data["trans"].date.eq("981231") & data["trans"].account_id.ne("1"))]
    later, _ = prepare_frames(data, default_policy())
    for split in ("train", "validation", "test"):
        for kind in ("history", "y", "origin", "account", "group"):
            np.testing.assert_array_equal(earlier[f"{split}_{kind}"], later[f"{split}_{kind}"])


@pytest.mark.parametrize("corruption", ["duplicate", "unknown_type", "negative", "unknown_account", "vyber_operation"])
def test_malformed_sources_fail_closed(corruption):
    data = frames()
    if corruption == "duplicate":
        data["trans"] = pd.concat([data["trans"], data["trans"].iloc[:1]])
    elif corruption == "unknown_type":
        data["trans"].loc[0, "type"] = "UNKNOWN"
    elif corruption == "negative":
        data["trans"].loc[0, "amount"] = "-1.00"
    elif corruption == "unknown_account":
        data["trans"].loc[0, "account_id"] = "9000"
    else:
        data["trans"].loc[2, "operation"] = "VKLAD"
    with pytest.raises(ValueError):
        prepare_frames(data, default_policy())


def test_policy_freeze_required_and_raw_checksum_enforced(tmp_path):
    policy = default_policy()
    policy["frozen_before_training"] = False
    with pytest.raises(ValueError, match="Freeze"):
        prepare_frames(frames(), policy)
    path = tmp_path / "bad.zip"
    path.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="frozen source"):
        load_source(path)
