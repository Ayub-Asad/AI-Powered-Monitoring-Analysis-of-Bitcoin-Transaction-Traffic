"""Deterministic JSON-native dashboard contract and centralized display semantics."""
from copy import deepcopy
import json
from .schema import VERSION


def response(graph, nodes, edges, *, truncated=False, reason=None, selected=(), path=(), **metadata):
    selected, path = set(selected), set(path)
    result_nodes = []
    for nid in sorted(nodes):
        node = deepcopy(graph.nodes[nid])
        category = 'address'
        reasons = []
        if node['type'] == 'transaction':
            category = 'transaction_unscored' if node['flagged'] is None else 'transaction_flagged' if node['flagged'] else 'transaction_normal'
            reasons.append(f"{node['attributes']['unique_output_addresses']} unique output addresses observed")
            if node['flagged']:
                reasons.append('ML flagged transaction: anomaly score meets or exceeds frozen threshold')
        else:
            reasons.append(f"Connected to {node['attributes']['transaction_count']} transactions in the full graph")
        node['visual'] = dict(category=category, selected=nid in selected, path_highlight=nid in path)
        node['reasons'] = reasons
        result_nodes.append(node)
    result_edges = [deepcopy(graph.edges[e]) for e in sorted(edges)]
    for edge in result_edges:
        edge['visual'] = {'category': edge['type'], 'path_highlight': edge['source'] in path and edge['target'] in path}
    txs = [n for n in result_nodes if n['type'] == 'transaction']
    result = dict(schema_version=VERSION, nodes=result_nodes, edges=result_edges,
                  summary=dict(node_count=len(result_nodes), edge_count=len(result_edges), transaction_count=len(txs),
                               address_count=len(result_nodes)-len(txs), flagged_transaction_count=sum(n['flagged'] is True for n in txs),
                               scored_transaction_count=sum(n['anomaly_score'] is not None for n in txs)),
                  truncated=truncated, truncation_reason=reason, **metadata)
    return result


def dumps(result):
    return json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':'))
