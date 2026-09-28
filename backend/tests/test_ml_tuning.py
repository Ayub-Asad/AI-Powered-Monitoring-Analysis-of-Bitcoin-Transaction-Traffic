"""Tuning regression tests use isolated, deliberately small synthetic fixtures."""
import copy
import json
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import pytest
from app.ml import tuning
from app.ml import tuning_analysis as analysis
from app.ml.artifacts import load_artifact
from app.ml.schema import ROOT, FEATURES, digest, write_json, from_transactions
from app.ml.scoring import risk_scores
from app.ml.workflow import training_run
from .test_ml_training import small_config
from scripts.prepare_ml_datasets import prepare


def config():
    return tuning.read_json(ROOT/'configs/ml_tuning.json')


def test_approved_protocol_and_sampling():
    c = config(); tuning.validate_tuning(c)
    assert c['final_test'] == {'seed': 404, 'start_time': '2025-04-01T00:00:00+00:00', 'normal': 15300, 'anomalous': 2700}
    a = tuning.sample_candidates(c, 15300)
    assert a == tuning.sample_candidates(c, 15300)
    assert len(a) == len({tuning.canonical(p) for p in a}) == 12
    assert all(p['max_samples'] <= 300 for p in tuning.sample_candidates(c, 300))
    with pytest.raises(ValueError): tuning.sample_candidates(c, 200)
    c['search_seed'] += 1
    assert tuning.sample_candidates(c, 15300) != a


@pytest.mark.parametrize('field,value', [('model_seeds',[42]), ('search_budget',13), ('ensemble',True),
    ('alert_budgets',[.01]), ('threshold_policy','test_f1'), ('activity_window_seconds',0)])
def test_protocol_rejects_unapproved_policy(field, value):
    c = config(); c[field] = value
    with pytest.raises(ValueError): tuning.validate_tuning(c)


def candidate(p, precision=.3, recall=.02, f1=.2):
    return {'parameters': {'n_estimators': p}, 'mean_top_1_precision': precision,
            'mean_top_1_recall': recall, 'mean_f1': f1}


def test_selection_primary_feasibility_ties_and_partition():
    a, b = candidate(100), candidate(200, f1=.4)
    assert tuning.select_candidate([a,b],partition='validation') == b
    assert tuning.select_candidate([a,candidate(200)],partition='validation') == a
    assert tuning.select_candidate([a,candidate(200,precision=.9,recall=.009)],partition='validation') == a
    with pytest.raises(ValueError): tuning.select_candidate([candidate(100,recall=0)],partition='validation')
    with pytest.raises(ValueError): tuning.select_candidate([a],partition='test')
    assert tuning.select_candidate([candidate(100,precision=.5,f1=.1),b],partition='validation')['parameters']['n_estimators'] == 100


def test_threshold_ties_are_distinct_from_exact_ranking():
    scores = np.array([.9,.9,.9,.1]); ids = ['c','a','b','d']; y = [0,1,0,0]
    cuts = analysis.budget_thresholds(scores,ids,[.25],partition='validation')
    result = analysis.operating_metrics(scores,y,['','dust_attack','',''],ids,.9,cuts,[.25])
    assert result['threshold_operating_points']['validation_top_25%']['alerts'] == 3
    assert result['exact_review_budgets']['25%']['alerts'] == 1
    assert result['exact_review_budgets']['25%']['true_alerts'] == 1
    assert result['exact_review_budgets']['25%']['recall'] == 1
    with pytest.raises(ValueError): analysis.budget_thresholds(scores,ids,[.25],partition='test')
    with pytest.raises(ValueError): analysis.rank_order(scores,['a']*4)


def test_budget_rounding_orientation_and_zero_denominators():
    for labels in ([], [0,0], [1,1]):
        metrics = analysis.decision_metrics([False]*len(labels),labels)
        assert metrics['precision'] is None
        if not any(labels): assert metrics['recall'] is None
        if all(labels): assert metrics['false_positive_rate'] is None
    m = analysis.operating_metrics([.1,.8,.5],[0,1,0],['','dust_attack',''],['a','b','c'],.7,{},[.01,.02,.05,.1])
    assert all(v['alerts'] == 1 and v['true_alerts'] == 1 for v in m['exact_review_budgets'].values())
    assert analysis.decision_metrics([True,False],[0,0])['false_alerts_per_1000_normal'] == 500


def test_intensity_strict_ties_boundary_and_future_invariance():
    tx = pd.DataFrame({'txid':['a','b','c','d','e'], 'timestamp':pd.to_datetime([
        '2025-01-01T00:00:00Z','2025-01-01T00:00:30Z','2025-01-01T00:01:00Z',
        '2025-01-01T00:01:00Z','2025-01-01T00:01:01Z'])})
    expected = [0,1,2,2,3]
    np.testing.assert_array_equal(analysis.historical_intensity(tx,tx.txid),expected)
    np.testing.assert_array_equal(analysis.historical_intensity(tx.iloc[:4],tx.txid[:4]),expected[:4])
    np.testing.assert_array_equal(analysis.historical_intensity(tx.sample(frac=1,random_state=4),tx.txid),expected)


@pytest.fixture(scope='module')
def experiment(tmp_path_factory):
    root = tmp_path_factory.mktemp('tuning')
    b = small_config(); b['data_dir']='data/base'; b['run_dir']='artifacts/base'; b['report_dir']='reports/base'
    for name,spec in b['corpora'].items():
        spec['normal']=60; spec['anomalous']=0 if name == 'train' else 20
    prepare(b,root); training_run(b,root)
    write_json(root/'configs/baseline.json',b)
    c=config(); c.update(baseline_config='configs/baseline.json',baseline_run='artifacts/base',
                        run_dir='artifacts/tuning',report_dir='reports/tuning',final_data_dir='data/final')
    c['grid']={'n_estimators':[2,3,4], 'max_samples':[16,32], 'max_features':[.6,1.0], 'bootstrap':[False,True]}
    c['final_test']['normal']=60; c['final_test']['anomalous']=20
    # Protected bytes also include representative existing v1/v2 files.
    (root/'data/v2').mkdir(); (root/'data/v2/development.csv').write_bytes(b'preserve v2')
    (root/'data/btc_synthetic_dataset.csv').write_bytes(b'preserve v1')
    before={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*') if p.is_file()}
    reads=[]; fits=[]
    original_read=tuning.read_verified; original_fit=tuning.fit_model
    def guard(data,name,suffix,manifest):
        if suffix=='labels':
            reads.append(name); assert name=='validation'
        assert not (root/c['final_data_dir']).exists()
        return original_read(data,name,suffix,manifest)
    def fit_guard(matrix,model_config,seed):
        assert list(matrix.columns)==FEATURES and len(matrix)==60
        fits.append((copy.deepcopy(model_config['model']),seed))
        return original_fit(matrix,model_config,seed)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tuning,'read_verified',guard); mp.setattr(tuning,'fit_model',fit_guard)
        result=tuning.tune(c,root)
    assert len(fits)==36 and set(s for _,s in fits)=={42,43,44} and reads==['validation']
    assert result['fits']==36
    assert all(digest(root/p)==h for p,h in before.items())
    return root,c,b,before


def clone(experiment,tmp_path):
    source,c,b,before=experiment
    root=tmp_path/'copy'; shutil.copytree(source,root)
    return root,copy.deepcopy(c),b,before


def test_artifact_parameters_preprocessing_and_diagnostics(experiment):
    root,c,b,_=experiment; frozen=tuning.verify_tuning(root/c['run_dir'],root)
    original=load_artifact(root/b['run_dir']/'iforest-42')[0].named_steps['preprocessing'].medians_
    for seed in c['model_seeds']:
        model,threshold,metadata=load_artifact(root/c['run_dir']/f'tuned-{seed}')
        assert all(model.named_steps['forest'].get_params()[k]==v for k,v in frozen['selected_parameters'].items())
        assert all(metadata['hyperparameters'][k]==v for k,v in frozen['selected_parameters'].items())
        np.testing.assert_array_equal(model.named_steps['preprocessing'].medians_,original)
        assert threshold['partition']=='validation'
    fp=tuning.read_json(root/c['report_dir']/'false_positives.json')
    assert all(v['partition']=='validation' for v in fp.values())
    for model in fp.values():
        for point in model['operating_points'].values():
            for bins in point['groups'].values():
                assert sum(b['normal'] for b in bins)==60
                assert sum(b['false_positives'] for b in bins)==point['false_alerts']


def test_refuse_overwrites_and_escape_paths(experiment,tmp_path):
    root,c,b,_=clone(experiment,tmp_path)
    with pytest.raises(FileExistsError): tuning.tune(c,root)
    path=root/'exclusive.json'; tuning.exclusive_json(path,{'a':1})
    with pytest.raises(FileExistsError): tuning.exclusive_json(path,{'a':2})
    for value in ('../escape','data/v2/new','artifacts/base/new','data'):
        bad=copy.deepcopy(c); bad['run_dir']=value
        with pytest.raises(ValueError): tuning.checked_paths(bad,root,b)


@pytest.mark.parametrize('target',['model','report','freeze'])
def test_integrity_blocks_final_before_generation(experiment,tmp_path,monkeypatch,target):
    root,c,_,_=clone(experiment,tmp_path); run=root/c['run_dir']
    path={'model':run/'tuned-42/pipeline.joblib', 'report':root/c['report_dir']/'selection.json', 'freeze':run/'frozen.json'}[target]
    path.write_bytes(path.read_bytes()+b' ')
    monkeypatch.setattr(tuning,'generate_final',lambda *a: pytest.fail('generation before verification'))
    with pytest.raises(ValueError): tuning.finalize(c,root)
    assert not (root/c['final_data_dir']).exists()


def test_complete_final_lifecycle_and_one_shot(experiment,tmp_path,monkeypatch):
    root,c,b,before=clone(experiment,tmp_path); reads=[]; scored=[]
    original_read=tuning.read_verified; original_score=tuning.risk_scores
    original_generate=tuning.generate_final
    def fixture_generate(protocol,directory):
        # Never consume the reserved production seed in regression fixtures.
        fixture_protocol=copy.deepcopy(protocol)
        fixture_protocol['final_test']['seed']=9404
        return original_generate(fixture_protocol,directory)
    monkeypatch.setattr(tuning,'generate_final',fixture_generate)
    def guarded(data,name,suffix,manifest):
        if suffix=='labels':
            reads.append(name); assert name=='final'; assert len(scored)==7
            assert (root/c['report_dir']/'final_manifest.json').exists()
            tuning.verify_tuning(root/c['run_dir'],root)
        return original_read(data,name,suffix,manifest)
    def score(model,matrix):
        scored.append(True); return original_score(model,matrix)
    monkeypatch.setattr(tuning,'read_verified',guarded); monkeypatch.setattr(tuning,'risk_scores',score)
    tuning.finalize(c,root)
    assert reads==['final']
    assert tuning.read_json(root/c['final_data_dir']/'manifest.json')['corpora']['final']['generation']['seed']==9404
    report=tuning.read_json(root/c['report_dir']/'final_evaluation.json')
    assert report['final_feature_shape']==[80,10] and len(report['models'])==7
    assert all(digest(root/p)==h for p,h in before.items())
    with pytest.raises(FileExistsError): tuning.finalize(c,root)
    scores=pd.read_csv(root/c['run_dir']/'final_scores.csv')
    assert len(scores)==80


def test_final_protocol_change_rejected(experiment,tmp_path):
    root,c,_,_=clone(experiment,tmp_path); c['final_test']['normal']+=1
    with pytest.raises(ValueError,match='configuration differs'): tuning.finalize(c,root)
    assert not (root/c['final_data_dir']).exists()


def test_fp_partition_and_empty_normal_groups(experiment):
    root,c,b,_=experiment
    manifest=tuning.read_json(root/b['data_dir']/'manifest.json')
    tx=tuning.read_verified(root/b['data_dir'],'validation','transactions',manifest); ids,x=from_transactions(tx)
    scores=np.ones(len(x))
    with pytest.raises(ValueError): analysis.false_positive_summary(x,tx,ids,scores,np.ones(len(x)),1,[.01],partition='test')
    result=analysis.false_positive_summary(x,tx,ids,scores,np.ones(len(x)),1,[.01],partition='validation')
    assert result['operating_points']['f1_threshold']['feature_distributions']['amount_btc']['false_positive']['quantiles'] is None
    assert result['operating_points']['f1_threshold']['examples']==[]


def test_operating_seed_summary():
    m=analysis.operating_metrics([.1,.8,.5],[0,1,0],['','dust_attack',''],['a','b','c'],.7,{},[.01])
    summary=analysis.operating_seed_summary([m,m,m])
    assert summary['exact_review_budgets']['1%']['precision']=={'mean':1.0,'std_population':0.0,'seeds_available':3}


def test_final_audit_rejects_overlap_and_time(experiment):
    root,c,b,_=experiment
    manifest=tuning.read_json(root/b['data_dir']/'manifest.json')
    parts={name:(tuning.read_verified(root/b['data_dir'],name,'transactions',manifest),
                  tuning.read_verified(root/b['data_dir'],name,'groups',manifest)) for name in ('train','validation','test')}
    tx,groups=parts['test']
    with pytest.raises(ValueError): tuning.audit_final(parts,tx,groups)
    future=tx.copy(); future['timestamp']+=pd.Timedelta(days=31)
    with pytest.raises(ValueError): tuning.audit_final(parts,future,groups)


def test_reservation_and_changed_code_block_final(experiment,tmp_path,monkeypatch):
    root,c,_,_=clone(experiment,tmp_path); run=root/c['run_dir']
    tuning.exclusive_json(run/'final_started.json',{'interrupted':True})
    with pytest.raises(FileExistsError): tuning.finalize(c,root)
    assert not (root/c['final_data_dir']).exists()
    original=tuning.digest
    def changed_source(path):
        if Path(path)==ROOT/'backend/app/ml/tuning.py': return 'changed'
        return original(path)
    monkeypatch.setattr(tuning,'digest',changed_source)
    with pytest.raises(ValueError,match='source changed'): tuning.verify_tuning(run,root)
