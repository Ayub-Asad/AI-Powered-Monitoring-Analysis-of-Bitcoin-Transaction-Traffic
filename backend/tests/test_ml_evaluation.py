import numpy as np
import pandas as pd
import pytest
from app.ml.evaluation import alert_metrics, evaluate, align_truth
from app.ml.baselines import RobustDeviation
from .test_ml_preprocessing import matrix, prep
from app.ml.schema import FEATURES


def test_alert_budgets_ceil_and_tie_break():
    scores = np.ones(20)
    ids = [f'{i:02}' for i in range(20)]
    y = [1,0] + [0]*18
    result = alert_metrics(scores, y, ids, [.01,.05,.10])
    assert [r['alerts'] for r in result.values()] == [1,1,2]
    assert result['10%']['precision'] == .5
    assert alert_metrics(scores[::-1], y[::-1], ids[::-1], [.1]) == {'10%': result['10%']}


def test_metrics_known_confusion_and_absent_category():
    out = evaluate([.9,.8,.2,.1], [1,0,1,0], ['dust_attack','','dust_attack',''], ['a','b','c','d'], .5, [.5], ['s','t','s','u'])
    assert out['confusion_matrix'] == {'tp':1,'fp':1,'fn':1,'tn':1}
    assert out['precision'] == out['recall'] == out['f1'] == out['false_positive_rate'] == .5
    assert out['roc_auc'] == .75
    assert out['per_category']['dust_attack']['scenarios'] == 1
    assert out['per_category']['fee_anomaly']['recall'] is None


def test_single_class_and_no_alerts():
    out = evaluate([.1,.2], [0,0], ['',''], ['a','b'], .5, [.1])
    assert out['roc_auc'] is None and out['average_precision'] is None
    assert out['precision'] is None and out['recall'] is None


def test_truth_alignment_and_missing_rejected():
    truth = pd.DataFrame({'txid':['a','b'], 'label':['normal','anomalous'], 'anomaly_type':['','dust_attack']})
    y, cats = align_truth(['b','a'], truth)
    assert y.tolist() == [True, False]
    with pytest.raises(ValueError): align_truth(['a','c'], truth)


def test_heuristic_constant_scale_and_no_refit():
    x = matrix()
    p = prep().fit(x)
    model = RobustDeviation(p, FEATURES[:7]).fit(x)
    assert np.isfinite(model.score_samples(x)).all()
    center = model.center_.copy()
    model.score_samples(matrix(4))
    np.testing.assert_array_equal(center, model.center_)
