"""Graph correctness fixtures are handwritten; no reserved corpus seeds or fitting."""
import json
import pandas as pd
import pytest
from app.graph import (build_graph, node_id, Limits, TransactionFilter, dumps, neighbourhood,
                       transaction_lookup, address_lookup, find_path, timeline,
                       suspicious_neighbourhood, search_transactions, trace_sequence)
from app.graph.serialization import response


def row(txid, inputs, outputs, ins, outs, second=0):
    return dict(txid=txid, timestamp=pd.Timestamp('2025-01-01T00:00:00Z')+pd.Timedelta(seconds=second),
                input_addresses=inputs, output_addresses=outputs, input_amounts=ins, output_amounts=outs,
                num_inputs=len(inputs), num_outputs=len(outputs), amount_btc=sum(outs),
                fee_btc=round(sum(ins)-sum(outs), 8), fee_rate_sat_vb=float('nan'), source_row=second+1)


@pytest.fixture
def frame():
    return pd.DataFrame([
        row('a', ['origin', 'origin', 'other'], ['bridge', 'peel'], [2., 1., 2.], [4., .9]),
        row('b', ['bridge'], ['next', 'bridge'], [4.], [3., .9], 10),
        row('c', ['next'], ['end'], [3.], [2.9], 20),
        row('early', ['next'], ['past'], [1.], [.9], 5),
        row('isolated', ['remote'], ['island'], [1.], [.9], 30)])


@pytest.fixture
def scores():
    return pd.DataFrame([dict(txid='b', anomaly_score=.7, threshold=.7, flagged=True, model_version='frozen-42'),
                         dict(txid='c', anomaly_score=.2, threshold=.7, flagged=False, model_version='frozen-42')])


def full(graph):
    return dumps(response(graph, graph.nodes, graph.edges))


def test_deterministic(frame, scores):
    assert full(build_graph(frame, scores)) == full(build_graph(frame.iloc[::-1], scores.iloc[::-1]))


def test_bipartite_amounts_repeated_and_degree(frame):
    graph = build_graph(frame)
    assert len(graph.nodes) == 14
    assert len(graph.edges) == 13
    for edge in graph.edges.values():
        assert graph.nodes[edge['source']]['type'] == ('address' if edge['type'] == 'input' else 'transaction')
        assert graph.nodes[edge['target']]['type'] == ('transaction' if edge['type'] == 'input' else 'address')
    origin = graph.nodes['address:origin']['attributes']
    assert origin['transaction_count'] == 1
    assert origin['total_outgoing_satoshis'] == 300000000
    assert origin['repeated_allocation_count'] == 1
    bridge = graph.nodes['address:bridge']['attributes']
    assert bridge['transaction_count'] == 2  # input and change output counted once
    assert bridge['degree'] == 3
    assert bridge['total_incoming_satoshis'] == 490000000
    assert bridge['total_outgoing_satoshis'] == 400000000
    attrs = graph.nodes['transaction:a']['attributes']
    assert attrs['num_inputs'] == 3 and attrs['unique_input_addresses'] == 2
    assert attrs['unique_output_addresses'] == 2
    assert attrs['component_size'] == 11


@pytest.mark.parametrize('hops,expected', [(1, 5), (2, 6), (3, 7)])
def test_hops(frame, hops, expected):
    result = neighbourhood(build_graph(frame), 'transaction:a', hops)
    assert result['summary']['node_count'] == expected
    assert not result['truncated']


def test_lookups_timeline_and_summary(frame, scores):
    graph = build_graph(frame, scores)
    assert transaction_lookup(graph, 'a')['summary']['edge_count'] == 4
    result = address_lookup(graph, 'bridge')
    assert result['summary']['transaction_count'] == 2
    assert graph.nodes['address:bridge']['attributes']['flagged_transaction_count'] == 1
    assert [n['attributes']['txid'] for n in timeline(graph, 'address:next')['timeline']] == ['early', 'b', 'c']
    with pytest.raises(KeyError):
        transaction_lookup(graph, 'missing')


@pytest.mark.parametrize('limits,reason', [(Limits(max_nodes=2), 'max_nodes'),
                                         (Limits(max_edges=1), 'max_edges'),
                                         (Limits(max_expansions=1), 'max_expansions')])
def test_explosion(frame, limits, reason):
    result = neighbourhood(build_graph(frame), 'transaction:a', 3, limits)
    assert result['truncated'] and result['truncation_reason'] == reason
    assert len(result['nodes']) <= limits.max_nodes and len(result['edges']) <= limits.max_edges
    ids = {n['id'] for n in result['nodes']}
    assert all(e['source'] in ids and e['target'] in ids for e in result['edges'])


def test_path_and_controlled_peeling_layering_sequence(frame, scores):
    graph = build_graph(frame, scores)
    result = trace_sequence(graph, 'transaction:a', 'transaction:c')
    assert result['ordered_node_ids'] == ['transaction:a', 'address:bridge', 'transaction:b', 'address:next', 'transaction:c']
    assert result['sequence_summary']['elapsed_seconds'] == 20
    assert [t['anomaly_score'] for t in result['sequence']] == [None, .7, .2]
    assert all(n['visual']['path_highlight'] for n in result['nodes'])
    assert not find_path(graph, 'transaction:a', 'transaction:early')['found']
    assert find_path(graph, 'transaction:a', 'transaction:early', chronological=False)['found']
    assert not find_path(graph, 'transaction:c', 'transaction:a')['found']
    assert find_path(graph, 'transaction:c', 'transaction:a', chronological=False, directed=False)['found']
    assert not find_path(graph, 'transaction:a', 'transaction:isolated')['found']
    assert find_path(graph, 'transaction:a', 'transaction:a')['ordered_node_ids'] == ['transaction:a']
    assert not find_path(graph, 'transaction:a', 'transaction:c', max_hops=3)['found']
    assert find_path(graph, 'transaction:a', 'transaction:c', limits=Limits(max_nodes=2))['truncated']


def test_scores_filters_and_absence(frame, scores):
    graph = build_graph(frame, scores)
    assert graph.nodes['transaction:a']['flagged'] is None
    result = suspicious_neighbourhood(graph, 'b')
    assert result['summary']['flagged_transaction_count'] == 1
    with pytest.raises(ValueError):
        suspicious_neighbourhood(graph, 'a')
    assert suspicious_neighbourhood(graph, 'c', min_score=.1)
    filters = TransactionFilter(flagged_only=True, min_anomaly_score=.5, start='2025-01-01T00:00:09Z',
                                end='2025-01-01T00:00:11Z', min_amount_satoshis=390000000)
    assert [n['id'] for n in search_transactions(graph, filters)['nodes']] == ['transaction:b']
    assert search_transactions(graph, limit=1)['next_offset'] == 1
    assert not search_transactions(graph, TransactionFilter(min_anomaly_score=.9))['nodes']
    unscored = build_graph(frame)
    assert all(n['flagged'] is None for n in unscored.nodes.values())
    assert transaction_lookup(unscored, 'a')['nodes'][-1]['visual']['category'] == 'transaction_unscored'


def test_legacy_unknown_and_network(frame):
    frame['input_amounts'] = None
    frame['output_amounts'] = None
    frame['country'] = pd.NA
    frame['src_ip'] = '8.8.8.8'
    frame['asn'] = pd.NA
    frame.loc[0, 'num_inputs'] = 90  # preserved legacy warning-only count
    graph = build_graph(frame)
    assert all(e['amount_satoshis'] is None for e in graph.edges.values())
    attrs = graph.nodes['address:origin']['attributes']
    assert attrs['total_outgoing_satoshis'] is None and not attrs['outgoing_value_complete']
    context = graph.nodes['transaction:a']['attributes']['network_context']
    assert context['src_ip'] == '8.8.8.8' and context['country'] is None
    assert context['dst_ip'] is None
    assert json.loads(full(graph))['schema_version'] == 'bitcoin-investigation-v1'


@pytest.mark.parametrize('column', ['label', 'anomaly_type', 'actor_id', 'scenario_id', 'ground_truth'])
def test_ground_truth_rejected(frame, column):
    frame[column] = 'secret'
    with pytest.raises(ValueError, match='metadata'):
        build_graph(frame)


@pytest.mark.parametrize('change', ['duplicate', 'unknown', 'nonfinite', 'wrong_flag', 'string_flag'])
def test_bad_scores_rejected(frame, scores, change):
    if change == 'duplicate':
        scores = pd.concat([scores, scores])
    elif change == 'unknown':
        scores.loc[0, 'txid'] = 'unknown'
    elif change == 'nonfinite':
        scores.loc[0, 'anomaly_score'] = float('nan')
    elif change == 'wrong_flag':
        scores.loc[0, 'flagged'] = False
    else:
        scores['flagged'] = 'False'
    with pytest.raises(ValueError):
        build_graph(frame, scores)


def test_duplicate_and_bad_allocations(frame):
    with pytest.raises(ValueError):
        build_graph(pd.concat([frame, frame]))
    frame.at[0, 'input_amounts'] = None
    with pytest.raises(ValueError):
        build_graph(frame)


def test_fractional_time_and_ties(frame):
    frame['timestamp'] = frame.timestamp.astype('datetime64[ns, UTC]')
    frame.loc[1, 'timestamp'] = frame.loc[0, 'timestamp']
    assert not trace_sequence(build_graph(frame), 'transaction:a', 'transaction:b')['found']
    frame.loc[1, 'timestamp'] += pd.Timedelta(nanoseconds=1)
    assert trace_sequence(build_graph(frame), 'transaction:a', 'transaction:b')['found']


@pytest.mark.parametrize('hops', [0, 4, True])
def test_invalid_hops(frame, hops):
    with pytest.raises(ValueError):
        neighbourhood(build_graph(frame), 'transaction:a', hops)


def test_response_is_detached(frame):
    graph = build_graph(frame)
    result = transaction_lookup(graph, 'a')
    result['nodes'][-1]['attributes']['txid'] = 'changed'
    assert graph.nodes['transaction:a']['attributes']['txid'] == 'a'


def test_scoring_adapter_uses_existing_interface(frame, monkeypatch):
    from app.graph import integration
    from app.ml.schema import FEATURES
    class FrozenModel:
        def score_samples(self, matrix):
            assert list(matrix.columns) == FEATURES
            assert matrix.fee_rate_sat_vb.isna().all()
            import numpy as np
            return np.full(len(matrix), -.7)
    monkeypatch.setattr(integration, 'load_artifact', lambda _: (FrozenModel(), {'threshold': .7}, {}))
    monkeypatch.setattr(integration, 'digest', lambda _: 'checksum')
    scores = integration.score_with_artifact(frame.iloc[::-1], 'frozen')
    graph = build_graph(frame, scores)
    assert all(n['flagged'] for n in graph.nodes.values() if n['type'] == 'transaction')
    assert graph.nodes['transaction:a']['model_version'] == 'frozen:checksum'
