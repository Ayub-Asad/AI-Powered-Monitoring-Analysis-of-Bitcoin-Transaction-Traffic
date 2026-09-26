import json
import numpy as np
import pytest
from app.ml.artifacts import save_artifact, load_artifact, freeze_run, verify_frozen
from app.ml.training import fit_model
from app.ml.scoring import risk_scores
from app.ml.thresholds import calibrate
from .test_ml_preprocessing import matrix, config


def saved(tmp_path):
    x = matrix()
    model = fit_model(x, config(), 42)
    threshold = calibrate(risk_scores(model, x), [0,1]*20, partition='validation')
    save_artifact(tmp_path/'model', model, threshold, {'model_version':'test'})
    return x, model


def test_roundtrip(tmp_path):
    x, model = saved(tmp_path)
    loaded, threshold, manifest = load_artifact(tmp_path/'model')
    np.testing.assert_array_equal(risk_scores(loaded, x), risk_scores(model, x))
    assert len(manifest['preprocessing']['medians']) == 10


@pytest.mark.parametrize('kind', ['binary','threshold','schema','environment'])
def test_tampering_rejected(tmp_path, kind):
    saved(tmp_path)
    directory = tmp_path/'model'
    if kind in ('binary', 'threshold'):
        p = directory/('pipeline.joblib' if kind == 'binary' else 'threshold.json')
        p.write_bytes(p.read_bytes()+b' ')
    else:
        p = directory/'manifest.json'
        m = json.loads(p.read_text())
        if kind == 'schema': m['features'] = m['features'][::-1]
        else: m['environment']['python'] = '0.0'
        p.write_text(json.dumps(m))
    with pytest.raises(ValueError): load_artifact(directory)


def test_frozen_inventory_detects_changes(tmp_path):
    saved(tmp_path)
    freeze_run(tmp_path, {}, {}, ['model'], {})
    assert verify_frozen(tmp_path)['status'] == 'frozen'
    (tmp_path/'model/threshold.json').write_text('{}')
    with pytest.raises(ValueError): verify_frozen(tmp_path)
