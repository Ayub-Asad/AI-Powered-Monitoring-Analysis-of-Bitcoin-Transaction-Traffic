import json
import numpy as np
import pandas as pd
import pytest
from app.ml.schema import ROOT, FEATURES, load_config
from app.ml.preprocessing import TransactionPreprocessor
from app.ml.training import fit_model
from app.ml.scoring import risk_scores


def matrix(n=40):
    rng = np.random.default_rng(10)
    frame = pd.DataFrame({name: rng.uniform(.01, 2, n) for name in FEATURES})
    frame['num_inputs'] = 1
    frame['num_outputs'] = 2
    frame['hour_of_day_utc'] = 12
    frame['day_of_week_utc'] = 2
    frame['is_night_utc'] = 0
    return frame


def config():
    c = load_config(ROOT / 'configs/ml_baseline.json')
    c['model']['n_estimators'] = 20
    c['model']['max_samples'] = 32
    return c


def prep():
    c = config()['preprocessing']
    return TransactionPreprocessor(c['log1p'], c['btc_multiplier'])


def test_imputation_is_train_only_and_logs():
    x = matrix()
    p = prep().fit(x)
    median = p.medians_.copy()
    v = matrix(3)
    v.loc[0, 'fee_rate_sat_vb'] = np.nan
    transformed = p.transform(v)
    assert transformed.loc[0, 'fee_rate_sat_vb'] == np.log1p(median[2])
    assert transformed.loc[0, 'amount_btc'] == np.log1p(v.loc[0, 'amount_btc'] * 1e8)
    v['amount_btc'] = 1e10
    p.transform(v)
    np.testing.assert_array_equal(p.medians_, median)
    with pytest.raises(ValueError): prep().fit(x, np.zeros(len(x)))


@pytest.mark.parametrize('kind', ['label', 'txid', 'reorder', 'missing', 'string', 'bool', 'inf', 'negative', 'fraction', 'hour', 'night', 'all_missing', 'required_nan', 'overflow'])
def test_invalid_features(kind):
    x = matrix()
    if kind in {'label', 'txid'}: x[kind] = 'bad'
    if kind == 'reorder': x = x[x.columns[::-1]]
    if kind == 'missing': x = x.drop(columns='fee_btc')
    if kind == 'string': x['fee_btc'] = '1'
    if kind == 'bool': x['is_night_utc'] = False
    if kind == 'inf': x.loc[0, 'fee_btc'] = np.inf
    if kind == 'negative': x.loc[0, 'fee_btc'] = -1
    if kind == 'fraction': x['num_inputs'] = 1.5
    if kind == 'hour': x['hour_of_day_utc'] = 24
    if kind == 'night': x['is_night_utc'] = 1
    if kind == 'all_missing': x['fee_rate_sat_vb'] = np.nan
    if kind == 'required_nan': x.loc[0, 'amount_btc'] = np.nan
    if kind == 'overflow': x['amount_btc'] = 1e308
    with pytest.raises(ValueError): prep().fit_transform(x)


def test_deterministic_fit_and_orientation():
    x = matrix()
    a, b = fit_model(x, config(), 42), fit_model(x, config(), 42)
    np.testing.assert_array_equal(risk_scores(a, x), risk_scores(b, x))
    np.testing.assert_array_equal(risk_scores(a, x), -a.score_samples(x))


@pytest.mark.parametrize('field', ['label','anomaly_type','actor_id','scenario_id','txid','wallet_address','src_ip','dst_ip','country','asn','src_port','source_row'])
def test_metadata_never_enters_fit(field):
    with pytest.raises(ValueError): fit_model(matrix().assign(**{field: 1}), config(), 42)
