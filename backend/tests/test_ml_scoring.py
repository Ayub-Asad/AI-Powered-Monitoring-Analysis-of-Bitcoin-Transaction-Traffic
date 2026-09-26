import numpy as np
import pytest
from app.ml.thresholds import calibrate, flags
from app.ml.scoring import score_transactions
from .test_ml_preprocessing import matrix, config
from app.ml.training import fit_model


def test_threshold_matches_exhaustive_and_includes_ties():
    scores = np.array([.1, .2, .2, .5, .6, .9])
    y = np.array([0, 1, 0, 1, 0, 1])
    candidates = []
    for t in np.unique(scores):
        pred = scores >= t
        tp, fp, fn = sum(pred & (y==1)), sum(pred & (y==0)), sum(~pred & (y==1))
        candidates.append((2*tp/(2*tp+fp+fn), -fp/sum(y==0), t))
    assert calibrate(scores, y, partition='validation')['threshold'] == max(candidates)[2]
    assert flags([.2, .3, .4], .3).tolist() == [False, True, True]


@pytest.mark.parametrize('partition', ['train', 'test'])
def test_nonvalidation_calibration_rejected(partition):
    with pytest.raises(ValueError): calibrate([.1,.9], [0,1], partition=partition)


def test_calibration_degenerate_and_nonfinite():
    for scores, y in [([], []), ([.1,.2], [0,0]), ([np.inf,.2], [0,1])]:
        with pytest.raises(ValueError): calibrate(scores, y, partition='validation')


def test_scoring_contract_and_empty():
    x = matrix()
    model = fit_model(x, config(), 42)
    out = score_transactions(model, x, [str(i) for i in range(len(x))], .5, 'test')
    assert len(out) == len(x)
    assert out.flagged.equals(out.anomaly_score >= .5)
    assert len(score_transactions(model, x.iloc[:0], [], .5, 'test')) == 0
    with pytest.raises(ValueError): score_transactions(model, x, ['same']*len(x), .5, 'test')
