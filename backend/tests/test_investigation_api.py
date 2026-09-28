"""HTTP integration with handwritten graph fixtures; no production fitting."""
import json
from types import SimpleNamespace
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.investigation import get_store, InvestigationStore
from app.graph import build_graph
from .test_graph import row


@pytest.fixture
def client():
    frame = pd.DataFrame([row('a',['origin'],['bridge'],[2.],[1.9]),
                          row('b',['bridge'],['end'],[1.9],[1.8],10)])
    scores = pd.DataFrame([dict(txid='b',anomaly_score=.8,threshold=.6,flagged=True,model_version='frozen'),
                           dict(txid='a',anomaly_score=.2,threshold=.6,flagged=False,model_version='frozen')])
    state = SimpleNamespace(graph=build_graph(frame,scores),status='ready',metadata={'dataset_identifier':'fixture'})
    app.dependency_overrides[get_store] = lambda: state
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health_overview(client):
    assert client.get('/api/health').json()['status']=='ok'
    d=client.get('/api/overview').json()
    assert (d['total_transactions'],d['total_addresses'],d['graph_edges'])==(2,3,4)
    assert d['flagged_percentage']==50 and d['model_identifiers']==['frozen']


def test_rank_pagination_filters(client):
    d=client.get('/api/alerts?limit=1').json()
    assert d['items'][0]['id']=='transaction:b' and d['next_offset']==1
    assert client.get('/api/alerts?offset=1').json()['items'][0]['id']=='transaction:a'
    assert client.get('/api/alerts?flagged_only=true').json()['total_matches']==1
    assert client.get('/api/alerts?min_score=0.9').json()['items']==[]
    assert client.get('/api/alerts?min_amount_satoshis=200000000').json()['items']==[]
    assert client.get('/api/alerts?start=2025-01-01T00:00:05Z').json()['total_matches']==1


@pytest.mark.parametrize('path', ['/api/transactions/a','/api/addresses/bridge','/api/graph/a?hops=3','/api/timeline/bridge'])
def test_serialization_contract(client,path):
    r=client.get(path);assert r.status_code==200
    d=r.json();assert d['schema_version']=='bitcoin-investigation-v1'
    ids={n['id'] for n in d['nodes']}
    assert all(e['source'] in ids and e['target'] in ids for e in d['edges'])
    json.dumps(d,allow_nan=False)
    assert not any(k in r.text for k in ['anomaly_type','scenario_id','actor_id'])


def test_timeline_trace_search(client):
    assert [n['id'] for n in client.get('/api/timeline/bridge').json()['timeline']]==['transaction:a','transaction:b']
    d=client.get('/api/trace?source=a&target=b').json()
    assert d['found'] and d['ordered_node_ids']==['transaction:a','address:bridge','transaction:b']
    assert not client.get('/api/trace?source=b&target=a').json()['found']
    assert client.get('/api/search?q=bridge').json()['items'][0]['id']=='address:bridge'
    assert client.get('/api/search?q=ri').json()['total_matches']==2
    assert client.get('/api/search?q=missing').json()['items']==[]


def test_truncation(client):
    d=client.get('/api/graph/a?hops=3&max_nodes=2').json()
    assert d['truncated'] and len(d['nodes'])==2
    assert d['truncation_reason']=='max_nodes'


@pytest.mark.parametrize('path', ['/api/graph/missing','/api/transactions/missing','/api/addresses/missing','/api/timeline/missing','/api/trace?source=a&target=missing'])
def test_missing(client,path):
    assert client.get(path).status_code==404


@pytest.mark.parametrize('path', ['/api/graph/a?hops=4','/api/graph/a?max_nodes=251','/api/graph/a?max_edges=0',
    '/api/alerts?limit=101','/api/alerts?offset=-1','/api/alerts?min_score=nan','/api/alerts?start=nonsense',
    '/api/alerts?start=2025-02-01T00:00:00Z&end=2025-01-01T00:00:00Z','/api/search?q=x','/api/search?q=%3Cscript%3E','/api/trace?source=a&target=b&max_hops=101'])
def test_invalid(client,path):
    assert client.get(path).status_code==422


def test_unscored(client):
    state=SimpleNamespace(graph=build_graph(pd.DataFrame([row('a',['in'],['out'],[1.],[.9])])),status='ready',metadata={})
    app.dependency_overrides[get_store]=lambda:state
    d=client.get('/api/alerts').json()['items'][0]
    assert d['flagged'] is None and d['anomaly_score'] is None


def test_load_failure(monkeypatch):
    monkeypatch.setenv('BTI_DATASET','does-not-exist.csv')
    state=InvestigationStore()
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc: state.load()
    assert exc.value.status_code==503 and state.status=='error'


def test_static_dashboard(client):
    import runpy
    from app.investigation import ROOT
    runpy.run_path(str(ROOT / 'scripts/build_dashboard.py'))['build']()
    assert client.get('/').status_code==200
    assert 'Bitcoin Transaction Intelligence Platform' in client.get('/').text
    assert client.get('/assets/app.js').status_code==200
    assert client.get('/docs').json()['info']['title']=='Bitcoin Transaction Intelligence Platform'
    assert client.get('/redoc').json()['openapi']
