"""Small source fixtures exercise leakage, posting semantics, and audit failures."""
import io
import json
from pathlib import Path
import tarfile

import numpy as np
import pandas as pd
import pytest

from forecasting.prepare import (DailyData, aggregate_ibm, aggregate_moneydata,
    audit_windows, build_windows, calendar_bounds, day_number, group_split,
    money_cents, prepare)


@pytest.fixture
def config():
    return json.loads((Path(__file__).parents[1] / "evaluation.json").read_text())


def test_money_parser_preserves_cents_and_rejects_silent_rounding():
    assert money_cents(pd.Series(["$12.10", "$-2.05", "$0", "$0.7"]), dollar_prefix=True).tolist() == [1210, -205, 0, 70]
    assert money_cents(pd.Series(["", "13"]), allow_blank=True).tolist() == [0, 1300]
    for malformed in ("1.001", "NaN", "inf", "1e3", "garbage"):
        with pytest.raises(ValueError, match="Malformed"):
            money_cents(pd.Series([malformed]))
    with pytest.raises(ValueError, match="supported bound"):
        money_cents(pd.Series(["9223372036854775808"]))


def test_ibm_aggregation_retains_repeats_and_positive_fraud_but_excludes_errors_and_refunds(tmp_path, config):
    header = "User,Card,Year,Month,Day,Amount,Errors?,Is Fraud?\n"
    rows = ["a,0,2015,1,1,$1.00,,No", "a,0,2016,1,1,$10.25,,Yes", "a,1,2016,1,1,$20.50,,No", "a,1,2016,1,1,$20.50,,No", "a,1,2016,1,1,$100.00,Insufficient Balance,No", "a,1,2016,1,1,$-7.00,,No", "a,1,2016,1,1,$0.00,,No", "b,0,2019,1,1,$1.00,,No"]
    path = tmp_path / "ibm.tgz"
    payload = (header + "\n".join(rows) + "\n").encode()
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo("nested/data.csv")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))
    daily = aggregate_ibm(path, config, chunksize=2)
    assert daily.amounts["a"][day_number("2016-01-01") - daily.start] == 5125
    assert daily.earliest["a"] == day_number("2015-01-01")
    assert daily.audit["raw_exact_duplicate_estimate"] == 1
    assert daily.audit["qualifying_rows"] == 5
    assert daily.audit["error_rows"] == 1
    assert daily.audit["negative_refund_rows"] == 1
    assert daily.audit["zero_amount_rows"] == 1
    assert daily.audit["positive_fraud_rows_kept"] == 1
    assert daily.source_end == day_number("2019-01-01")


def test_moneydata_dates_are_day_first_and_debits_are_not_netted(tmp_path, config):
    path = tmp_path / "money.csv"
    path.write_text("Transaction Number,Transaction Date,Debit Amount,Credit Amount\n1,12/07/2015,1,\n2,02/01/2016,15.50,\n3,02/01/2016,,20.00\n4,31/12/2021,2,\n")
    daily = aggregate_moneydata(path, config)
    assert daily.source_start == day_number("2015-07-12")
    assert daily.amounts["moneydata-person-1"][day_number("2016-01-02") - daily.start] == 1550
    assert daily.audit["credit_rows_excluded_from_outflow"] == 1
    assert daily.audit["qualifying_rows"] == 3


def make_daily(config, source, earliest_by_group):
    start, end = calendar_bounds(config, source)
    return DailyData(start, end, {group: np.arange(end - start + 1, dtype=np.int64) + 100 for group in earliest_by_group}, earliest_by_group, start - 100, end, {})


def test_customer_split_pools_cards_and_has_no_future_activity_eligibility(config):
    group_for_split = {split: next(str(i) for i in range(1000) if group_split(str(i)) == split) for split in ("train", "validation", "test")}
    daily = make_daily(config, "ibm", {group: day_number("2015-01-01") for group in group_for_split.values()})
    # An account with no recent or future activity remains eligible if it was
    # previously observed. Requiring a future final charge would leak labels.
    daily.amounts[group_for_split["test"]][:] = 0
    arrays, eligibility = build_windows(daily, config, "ibm")
    for split, group in group_for_split.items():
        assert set(arrays[f"{split}_group"]) == {group}
        assert eligibility[split]["included_windows"] == 24
        assert set((arrays[f"{split}_origin"] + 3) % 7) == set(range(7))
    assert np.all(arrays["test_history"] == 0)
    assert np.all(arrays["test_y"] == 0)
    first = arrays["train_origin"][0] - daily.start
    np.testing.assert_array_equal(arrays["train_history"][0], daily.amounts[group_for_split["train"]][first - 56:first] / 100)
    np.testing.assert_array_equal(arrays["train_y"][0], daily.amounts[group_for_split["train"]][first:first + 14] / 100)
    audit = audit_windows(arrays, "ibm")
    assert audit["train_verdict"] == "train_for_limited_research_only"
    assert all(pair["shared_groups"] == 0 for pair in audit["split_integrity"].values())


def test_eligibility_uses_only_history_available_at_origin(config):
    group = next(str(i) for i in range(1000) if group_split(str(i)) == "train")
    first_origin = day_number("2016-01-01")
    daily = make_daily(config, "ibm", {group: first_origin - 55})
    arrays, audit = build_windows(daily, config, "ibm")
    assert arrays["train_origin"][0] == first_origin + 15
    assert audit["train"]["first_qualifying_transaction_after_context_start"] == 1


def test_single_person_case_study_is_temporal_and_audit_catches_bad_amounts(config):
    daily = make_daily(config, "moneydata", {"one": day_number("2015-01-01")})
    arrays, _ = build_windows(daily, config, "moneydata")
    assert [len(arrays[f"{split}_origin"]) for split in ("train", "validation", "test")] == [96, 24, 24]
    audit = audit_windows(arrays, "moneydata")
    assert not audit["blocking_items"]
    assert audit["split_integrity"]["train_vs_test"]["shared_groups"] == 1
    arrays["train_y"][0, 0] = -1
    audit = audit_windows(arrays, "moneydata")
    assert audit["train_verdict"] == "do_not_train"
    assert audit["splits"]["train"]["negative"] == 1


def test_unfrozen_policy_and_changed_raw_payload_block_preparation(tmp_path, config):
    config_path = tmp_path / "evaluation.json"
    config["frozen_before_training"] = False
    config_path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="Freeze"):
        prepare("moneydata", config_path=config_path, raw_dir=tmp_path, output_dir=tmp_path / "out")
    config["frozen_before_training"] = True
    config_path.write_text(json.dumps(config))
    raw = tmp_path / "raw.csv"
    raw.write_text("not the acquired file")
    (tmp_path / "moneydata-source.json").write_text(json.dumps({"raw_relative_path": raw.name, "download": {"sha256": "0" * 64, "bytes": raw.stat().st_size}}))
    with pytest.raises(ValueError, match="checksum/size"):
        prepare("moneydata", config_path=config_path, raw_dir=tmp_path, output_dir=tmp_path / "out")
