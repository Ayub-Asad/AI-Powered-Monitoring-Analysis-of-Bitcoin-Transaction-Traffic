import copy
import json
import sys
import numpy as np
import pandas as pd
import pytest
from app.ml.schema import ROOT, from_transactions, digest
from app.ml import workflow
from app.ml.artifacts import load_artifact
from app.ml.scoring import risk_scores
from .test_ml_preprocessing import config
from .test_features import canonical, records

sys.path.insert(0, str(ROOT))
from scripts.prepare_ml_datasets import prepare


def small_config():
    c = config()
    c['data_dir'] = 'data'
    c['run_dir'] = 'run'
    c['report_dir'] = 'reports'
    for name, spec in c['corpora'].items():
        spec['normal'] = 60
        spec['anomalous'] = 0 if name == 'train' else 20
    return c


def test_future_rows_and_labels_do_not_change_transaction_features():
    tx = canonical(records())
    ids, early = from_transactions(tx.iloc[:1])
    all_ids, all_features = from_transactions(tx)
    pd.testing.assert_frame_equal(early, all_features.loc[all_ids.isin(ids)].reset_index(drop=True))
    for field in ['label','anomaly_type','actor_id','scenario_id','ground_truth']:
        with pytest.raises(ValueError): from_transactions(tx.assign(**{field:'secret'}))
    _, without_context = from_transactions(tx.assign(src_ip='other', country='ZZ', asn=999))
    pd.testing.assert_frame_equal(all_features, without_context)
    shuffled_ids, shuffled = from_transactions(tx.sample(frac=1, random_state=3))
    pd.testing.assert_frame_equal(all_features, shuffled)


def test_complete_offline_lifecycle_and_label_access(tmp_path, monkeypatch):
    c = small_config()
    manifest = prepare(c, tmp_path)
    # Raw transaction files never contain ground truth, including train.
    assert 'label' not in pd.read_json(tmp_path/'data/train.transactions.jsonl', lines=True)
    read = workflow.read_verified
    seen = []
    def guard(data, name, suffix, manifest):
        if suffix == 'labels':
            seen.append(name)
            assert name == 'validation', 'test/train labels opened during training'
        return read(data, name, suffix, manifest)
    monkeypatch.setattr(workflow, 'read_verified', guard)
    frozen = workflow.training_run(c, tmp_path)
    assert seen == ['validation']
    assert frozen['feature_shapes']['train'] == [60,10]
    monkeypatch.setattr(workflow, 'read_verified', read)
    before = digest(tmp_path/'run/frozen.json')
    result = workflow.evaluate_run(tmp_path/'run', tmp_path, plots=False)
    assert digest(tmp_path/'run/frozen.json') == before
    assert result['models']['iforest-42']['records'] == 80
    assert result['models']['iforest-42']['alert_budgets']['10%']['alerts'] == 8
    output = tmp_path/'scores.csv'
    assert workflow.score_file(tmp_path/'run', tmp_path/'data/test.transactions.jsonl', output)['rows'] == 80
    assert 'label' not in pd.read_csv(output)
    with pytest.raises(ValueError): workflow.training_run(c, tmp_path)


def test_preparation_reproducibility_and_training_determinism(tmp_path):
    c = small_config()
    a = prepare(c, tmp_path)
    b = prepare(c, tmp_path)
    assert a['split_audit'] == b['split_audit']
    for name in c['corpora']:
        assert a['corpora'][name]['files'] == b['corpora'][name]['files']
    workflow.training_run(c, tmp_path)
    c['run_dir'] = 'run-again'
    workflow.training_run(c, tmp_path)
    tx = workflow.read_verified(tmp_path/'data', 'validation', 'transactions', a)
    _, x = from_transactions(tx)
    for seed in c['model_seeds']:
        first, t1, _ = load_artifact(tmp_path/f'run/iforest-{seed}')
        second, t2, _ = load_artifact(tmp_path/f'run-again/iforest-{seed}')
        np.testing.assert_array_equal(risk_scores(first, x), risk_scores(second, x))
        assert t1 == t2


def test_test_labels_not_needed_for_training_and_tamper_fails_before_read(tmp_path, monkeypatch):
    c = small_config()
    prepare(c, tmp_path)
    # Deliberately corrupt withheld truth: training must not read/hash it.
    (tmp_path/'data/test.labels.jsonl').write_text('not valid labels')
    workflow.training_run(c, tmp_path)
    with pytest.raises(ValueError, match='checksum'): workflow.evaluate_run(tmp_path/'run', tmp_path, plots=False)
    (tmp_path/'run/iforest-42/threshold.json').write_text('{}')
    def never_read(*args):
        raise AssertionError('data read before freeze verification')
    monkeypatch.setattr(workflow, 'read_verified', never_read)
    with pytest.raises(ValueError, match='frozen'): workflow.evaluate_run(tmp_path/'run', tmp_path, plots=False)
