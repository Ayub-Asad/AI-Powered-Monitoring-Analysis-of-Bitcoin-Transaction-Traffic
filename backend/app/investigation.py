"""Read-only local investigation API; canonical graph and frozen inference only."""
import hashlib
import logging
import os
from pathlib import Path
from threading import Lock
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Query
from app.ingestion import ingest_file
from app.graph import build_graph, Limits, TransactionFilter, neighbourhood, timeline, trace_sequence
from app.graph.integration import score_with_artifact
from app.graph.serialization import response

ROOT = Path(__file__).resolve().parents[2]
router = APIRouter(prefix='/api')


class InvestigationStore:
    def __init__(self):
        self.graph = None
        self.status = 'not_loaded'
        self.lock = Lock()
        self.metadata = {}

    def load(self):
        with self.lock:
            if self.graph is not None:
                return self
            self.status = 'loading'
            started = perf_counter()
            try:
                dataset = Path(os.environ.get('BTI_DATASET', ROOT / 'data/v2/development.csv'))
                artifact = os.environ.get('BTI_ARTIFACT', str(ROOT / 'artifacts/ml/tuning/run-001/tuned-42'))
                canonical = ingest_file(dataset)
                if canonical.transactions.empty or canonical.report.to_dict()['summary']['rejected_rows']:
                    raise ValueError('dataset contains rejected rows or no transactions')
                scores = score_with_artifact(canonical.transactions, artifact) if artifact != 'none' else None
                self.graph = build_graph(canonical.transactions, scores)
                self.metadata = dict(dataset_identifier=dataset.name,
                    dataset_sha256=hashlib.sha256(dataset.read_bytes()).hexdigest(),
                    load_seconds=round(perf_counter()-started, 3), score_status='unavailable' if scores is None else 'ready')
                self.status = 'ready'
            except Exception:
                self.status = 'error'
                logging.exception('Investigation loading failed')
                raise HTTPException(503, 'Investigation load failed. Check local dataset/artifact configuration and server log.')
        return self


store = InvestigationStore()


def get_store():
    return store.load()


def resolve(graph, entity):
    candidates = [entity] if entity.startswith(('transaction:', 'address:')) else ['transaction:'+entity, 'address:'+entity]
    for candidate in candidates:
        if candidate in graph.nodes:
            return candidate
    raise HTTPException(404, 'Entity not found in the loaded dataset')


def filters(flagged_only: bool = False, min_score: float | None = Query(None, allow_inf_nan=False),
            min_amount_satoshis: int | None = Query(None, ge=0), start: str | None = None, end: str | None = None):
    try:
        return TransactionFilter(flagged_only, min_score, start, end, min_amount_satoshis)
    except (ValueError, TypeError):
        raise HTTPException(422, 'Invalid filter; times must be timezone-aware and start must precede end')


@router.get('/health')
def health():
    return dict(status='ok', graph_status=store.status, service='bitcoin-investigation')


@router.get('/overview')
def overview(state=Depends(get_store)):
    txs = [n for n in state.graph.nodes.values() if n['type'] == 'transaction']
    flagged = sum(n['flagged'] is True for n in txs)
    return dict(total_transactions=len(txs), total_addresses=len(state.graph.nodes)-len(txs),
                graph_edges=len(state.graph.edges), flagged_transactions=flagged,
                flagged_percentage=100*flagged/len(txs) if txs else 0,
                scored_transactions=sum(n['anomaly_score'] is not None for n in txs),
                model_identifiers=sorted({n['model_version'] for n in txs if n['model_version']}),
                graph_status=state.status, **state.metadata)


@router.get('/alerts')
def alerts(limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
           selection=Depends(filters), state=Depends(get_store)):
    graph = state.graph
    ids = sorted((k for k,n in graph.nodes.items() if n['type']=='transaction' and selection.matches(n)),
                 key=lambda k: (graph.nodes[k]['anomaly_score'] is None, -(graph.nodes[k]['anomaly_score'] or 0), k))
    result = response(graph, ids[offset:offset+limit], [])
    indexed = {n['id']: n for n in result['nodes']}
    result.update(items=[indexed[k] for k in ids[offset:offset+limit]], total_matches=len(ids),
                  next_offset=offset+limit if offset+limit<len(ids) else None, offset=offset)
    return result


@router.get('/transactions/{txid}')
def transaction(txid: str, state=Depends(get_store)):
    return neighbourhood(state.graph, resolve(state.graph, 'transaction:'+txid), limits=Limits(80,160))


@router.get('/addresses/{address}')
def address(address: str, state=Depends(get_store)):
    return neighbourhood(state.graph, resolve(state.graph, 'address:'+address), limits=Limits(80,160))


@router.get('/graph/{entity}')
def graph_view(entity: str, hops: int = Query(1, ge=1, le=3), max_nodes: int = Query(80, ge=1, le=250),
               max_edges: int = Query(160, ge=1, le=500), selection=Depends(filters), state=Depends(get_store)):
    return neighbourhood(state.graph, resolve(state.graph, entity), hops, Limits(max_nodes,max_edges), selection)


@router.get('/timeline/{entity}')
def timeline_view(entity: str, hops: int = Query(2, ge=1, le=3), max_nodes: int = Query(80, ge=1, le=250),
                  max_edges: int = Query(160, ge=1, le=500), selection=Depends(filters), state=Depends(get_store)):
    return timeline(state.graph, resolve(state.graph, entity), hops, Limits(max_nodes,max_edges), selection)


@router.get('/search')
def search(q: str = Query(..., min_length=2, max_length=150, pattern=r'^[A-Za-z0-9:_-]+$'),
           limit: int = Query(20, ge=1, le=50), state=Depends(get_store)):
    graph = state.graph
    exact = [k for k in graph.nodes if k == q or k.split(':',1)[1] == q]
    ids = exact or sorted(k for k in graph.nodes if q.lower() in k.split(':',1)[1].lower())
    return dict(items=response(graph, ids[:limit], [])['nodes'], total_matches=len(ids), truncated=len(ids)>limit)


@router.get('/trace')
def trace(source: str, target: str, max_hops: int = Query(12, ge=1, le=100), state=Depends(get_store)):
    return trace_sequence(state.graph, resolve(state.graph,source), resolve(state.graph,target),
                          max_hops=max_hops, limits=Limits(2000,4000,10000))
