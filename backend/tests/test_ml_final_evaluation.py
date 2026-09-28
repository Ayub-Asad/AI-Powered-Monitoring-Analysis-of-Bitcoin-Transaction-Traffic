"""Amendment tests never instantiate the generator with reserved seed 405."""
import copy
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from app.ml import final_evaluation as final
from app.ml.schema import ROOT
from app.ml.tuning import read_json, exclusive_json


def configuration(root):
    c=read_json(ROOT/'configs/ml_final_405.json')
    frozen={'config':{'run_dir':c['run_dir'],'report_dir':c['report_dir'],
                     'final_data_dir':'data/ml/tuning/final-404','final_test':{**final.FINAL_SPEC,'seed':404}}}
    return c,frozen


@pytest.mark.parametrize('change',['seed','count','period','model_policy','path'])
def test_only_approved_amendment(change,tmp_path):
    c,f=configuration(tmp_path);final.validate_amendment(c,f,tmp_path)
    if change=='seed': c['final_test']['seed']=406
    if change=='count': c['final_test']['normal']=60
    if change=='period': c['final_test']['start_time']='2025-05-01T00:00:00+00:00'
    if change=='model_policy': c['selection']='new'
    if change=='path': c['final_data_dir']='../escape'
    with pytest.raises(ValueError): final.validate_amendment(c,f,tmp_path)


def data(scope,month='04'):
    tx=pd.DataFrame({'txid':['1'*64,'2'*64],'timestamp':pd.to_datetime([f'2025-{month}-02T00:00:00Z',f'2025-{month}-02T00:01:00Z']),
                     'input_addresses':[['one'],['two']],'output_addresses':[['three'],['four']]})
    g=pd.DataFrame({'txid':tx.txid,'corpus':scope,'actor_id':[scope+':actor-a',scope+':actor-b'],
                    'scenario_id':[scope+':scenario-a',scope+':scenario-b']})
    return tx,g


def inventory():
    tx,g=data('reference','03');tx.txid=['3'*64,'4'*64];g.txid=tx.txid
    tx.input_addresses=[['old-one'],['old-two']];tx.output_addresses=[['old-three'],['old-four']]
    g.scenario_id=['reference:old-a','reference:old-b']
    return {'entries':[{'name':'reference','must_precede_final':True,**final.identity_bundle(tx,g,'reference')}]}


@pytest.mark.parametrize('kind',['txid','wallet','scoped_actor','scoped_scenario','raw_scenario','time','scope'])
def test_identity_and_chronological_overlap_stop(kind):
    tx,g=data('final-405');inv=inventory()
    assert final.audit_identities(tx,g,inv)['passed']
    if kind in inv['entries'][0]['identities']:
        bundle=final.identity_bundle(tx,g,'final-405')
        inv['entries'][0]['identities'][kind]=bundle['identities'][kind][:1]
    elif kind=='time': inv['entries'][0]['end']='2025-04-03T00:00:00+00:00'
    else: g.corpus='wrong'
    with pytest.raises(ValueError): final.audit_identities(tx,g,inv)


def test_independent_fixture_time_overlap_disclosed():
    tx,g=data('final-405');inv=inventory();e=inv['entries'][0]
    e.update(must_precede_final=False,start='2025-04-01T00:00:00+00:00',end='2025-04-14T00:00:00+00:00')
    result=final.audit_identities(tx,g,inv)
    assert result['comparisons'][0]['time_overlap'] is True
    assert result['comparisons'][0]['must_precede_final'] is False


def test_identity_group_coverage_and_legacy():
    tx,g=data('final-405')
    with pytest.raises(ValueError): final.identity_bundle(tx,g.iloc[:1],'final-405')
    legacy=final.identity_bundle(tx)
    assert legacy['grouping_available'] is False and not legacy['identities']['scoped_actor']


def mocked_lifecycle(tmp_path,monkeypatch,overlap=False):
    # Mock generation with explicit literal identities. Never generate seed 405.
    c,_=configuration(tmp_path);c['final_test']={**c['final_test'],'normal':1,'anomalous':1}
    run=tmp_path/c['run_dir'];report=tmp_path/c['report_dir'];run.mkdir(parents=True);report.mkdir(parents=True)
    exclusive_json(run/'final_405_reservation.json',{})
    exclusive_json(tmp_path/c['fixture_inventory'],inventory())
    tx,g=data('final-405')
    names=['tuned-42','tuned-43','tuned-44','baseline-iforest-42','baseline-iforest-43','baseline-iforest-44','baseline-heuristic']
    frozen={'models':{n:{'path':n,'budget_cutoffs':{'1%':.7,'2%':.7,'5%':.7,'10%':.7}} for n in names},
            'config':{'alert_budgets':[.01,.02,.05,.1]},'selected_parameters':{'n_estimators':200}}
    reservation={'original_frozen_sha256':'original'}
    monkeypatch.setattr(final,'verify_reservation',lambda *a:(frozen,reservation))
    monkeypatch.setattr(final,'load_artifact',lambda *a:(SimpleNamespace(),{'threshold':.5},{}))
    def generate(spec,directory,scope):
        Path(directory).mkdir(parents=True)
        return {'corpora':{'final':{'generation':spec,'records':2}}}
    monkeypatch.setattr(final,'generate_corpus',generate)
    events=[]
    def read(directory,name,suffix,manifest):
        events.append(suffix)
        if suffix=='transactions': return tx
        if suffix=='groups': return g
        assert events.count('score')==7
        assert (report/'final_manifest.json').exists()
        return pd.DataFrame({'txid':tx.txid,'label':['normal','anomalous'],'anomaly_type':['','dust_attack']})
    monkeypatch.setattr(final,'read_verified',read)
    monkeypatch.setattr(final,'from_transactions',lambda tx:(tx.txid,pd.DataFrame(np.ones((2,10)))))
    def score(*args): events.append('score');return np.array([.2,.8])
    monkeypatch.setattr(final,'risk_scores',score)
    if overlap:
        inv=read_json(tmp_path/c['fixture_inventory']);inv['entries'][0]['identities']['txid']=[tx.txid.iloc[0]]
        (tmp_path/c['fixture_inventory']).write_text(__import__('json').dumps(inv))
    return c,events,run,report


def test_one_shot_all_models_scored_before_labels(tmp_path,monkeypatch):
    c,events,run,report=mocked_lifecycle(tmp_path,monkeypatch)
    final.evaluate_final(c,tmp_path)
    assert events.count('labels')==1 and events.count('score')==7
    assert (run/'final_completed.json').exists()
    r=read_json(report/'final_evaluation.json')
    assert len(r['models'])==7 and r['models']['tuned-42']['precision']==1
    with pytest.raises(FileExistsError): final.evaluate_final(c,tmp_path)


def test_failed_audit_never_scores_or_reads_labels(tmp_path,monkeypatch):
    c,events,run,report=mocked_lifecycle(tmp_path,monkeypatch,overlap=True)
    with pytest.raises(ValueError,match='audit failed'): final.evaluate_final(c,tmp_path)
    assert 'score' not in events and 'labels' not in events
    assert (run/'final_failed.json').exists() and not (report/'final_evaluation.json').exists()
    with pytest.raises(FileExistsError): final.evaluate_final(c,tmp_path)


def test_reservation_tampering_blocks_generation(tmp_path,monkeypatch):
    c,f=configuration(tmp_path);run=tmp_path/c['run_dir'];report=tmp_path/c['report_dir'];run.mkdir(parents=True);report.mkdir(parents=True)
    f['models']={};f['selected_parameters']={};f['config']['alert_budgets']=[.01,.02,.05,.1]
    exclusive_json(run/'frozen.json',f);exclusive_json(tmp_path/c['fixture_inventory'],inventory())
    exclusive_json(report/'fixture_manifest.json',{'inventory_sha256':final.digest(tmp_path/c['fixture_inventory'])})
    monkeypatch.setattr(final,'verify_tuning',lambda *a:f)
    final.reserve(c,tmp_path)
    assert final.verify_reservation(c,tmp_path)[0]==f
    with pytest.raises(FileExistsError): final.reserve(c,tmp_path)
    with (tmp_path/c['fixture_inventory']).open('a') as stream: stream.write(' ')
    monkeypatch.setattr(final,'generate_corpus',lambda *a:pytest.fail('generation before checks'))
    with pytest.raises(ValueError,match='inventory changed'): final.evaluate_final(c,tmp_path)
    assert not (tmp_path/c['final_data_dir']).exists()
