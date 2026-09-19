"""Regression against accidentally reshuffling the original held-out people."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from forecasting.prepare import DailyData, audit_windows, build_windows, calendar_bounds, day_number, group_split
from forecasting.prepare_v2 import preparation_policy


def policy():
    return json.loads((Path(__file__).parents[1] / 'evaluation-v2.json').read_text())


def test_experiment_version_does_not_change_original_customer_holdouts():
    p = policy()
    frozen = copy.deepcopy(p)
    config = preparation_policy(p)
    assert p == frozen and config['version'] == 'forecast-v1'
    # Explicitly choose a person whose membership would change with the new salt.
    changed = next(str(i) for i in range(100) if group_split(str(i), 'forecast-v1') != group_split(str(i), 'forecast-v2'))
    groups = {s: next(str(i) for i in range(100) if group_split(str(i)) == s) for s in ('train', 'validation', 'test')}
    groups['changed'] = changed
    start, end = calendar_bounds(config, 'ibm')
    ids = set(groups.values())
    daily = DailyData(start, end, {g: np.ones(end-start+1, dtype=np.int64) * 100 for g in ids},
                      {g: day_number('2010-01-01') for g in ids}, day_number('1991-01-01'), day_number('2020-02-28'), {})
    arrays, _ = build_windows(daily, config, 'ibm')
    for split in ('train', 'validation', 'test'):
        assert all(group_split(str(g)) == split for g in arrays[f'{split}_group'])
        years = (arrays[f'{split}_origin'].astype('datetime64[D]').astype('datetime64[Y]').astype(int) + 1970)
        assert set(years) == set(p['ibm']['years'][split])
        assert all(str(np.datetime64(int(o)+13, 'D'))[:4] == str(np.datetime64(int(o), 'D'))[:4]
                   for o in arrays[f'{split}_origin'])
    assert changed in arrays[f'{group_split(changed)}_group']
    assert audit_windows(arrays, 'ibm')['blocking_items'] == []


def test_policy_rejects_customer_reshuffle_and_old_test_period():
    p = policy()
    p['ibm']['group_split_version'] = 'forecast-v2'
    with pytest.raises(ValueError, match='original IBM'):
        preparation_policy(p)
    p = policy()
    p['ibm']['years']['test'] = [2018]
    with pytest.raises(ValueError, match='target years'):
        preparation_policy(p)
