import copy
import pandas as pd
import pytest
from app.ml.splits import audit_partitions


def partitions():
    return {name: (pd.DataFrame([{"txid": name, "timestamp": f"2025-0{i+1}-01T00:00:00Z", "input_addresses": [name+'a'], "output_addresses": [name+'b']}]),
                   pd.DataFrame([{"txid": name, "corpus": name, "actor_id": name+':actor', "scenario_id": name+':'+name}]))
            for i, name in enumerate(('train', 'validation', 'test'))}


def test_disjoint():
    assert audit_partitions(partitions())["chronological"]


@pytest.mark.parametrize('kind', ['wallet', 'time', 'scope', 'scenario', 'coverage', 'labels'])
def test_overlap_and_metadata_rejected(kind):
    p = copy.deepcopy(partitions())
    tx, groups = p['test']
    if kind == 'wallet': tx.at[0, 'input_addresses'] = ['traina']
    if kind == 'time': tx.at[0, 'timestamp'] = '2025-01-01T00:00:00Z'
    if kind == 'scope': groups.at[0, 'actor_id'] = 'actor'
    if kind == 'scenario': groups.at[0, 'scenario_id'] = 'test:train'
    if kind == 'coverage': groups.at[0, 'txid'] = 'other'
    if kind == 'labels': groups['label'] = 'normal'
    with pytest.raises(ValueError): audit_partitions(p)
