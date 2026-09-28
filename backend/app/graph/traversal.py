"""Bounded structural investigation and chronological address-linked paths.

Hops count bipartite edges (transaction -> address -> transaction is two).
Chronological paths are possible activity chains, not verified UTXO spends.
"""
from collections import deque
from .schema import Limits, TransactionFilter, node_id
from .serialization import response


def neighbourhood(graph, entity, hops=1, limits=None, filters=None):
    graph.require(entity)
    if type(hops) is not int or not 1 <= hops <= 3:
        raise ValueError('hops must be 1, 2 or 3')
    limits, filters = limits or Limits(), filters or TransactionFilter()
    nodes, edges, queue = {entity}, set(), deque([(entity, 0)])
    scanned, reason = 0, None
    while queue and reason is None:
        current, depth = queue.popleft()
        if depth == hops:
            continue
        for eid in graph.adjacent[current]:
            if scanned >= limits.max_expansions:
                reason = 'max_expansions'
                break
            scanned += 1
            edge = graph.edges[eid]
            other = edge['target'] if edge['source'] == current else edge['source']
            if not filters.matches(graph.nodes[other]) and other != entity:
                continue
            if eid in edges:
                continue
            if len(edges) >= limits.max_edges:
                reason = 'max_edges'
                break
            if other not in nodes:
                if len(nodes) >= limits.max_nodes:
                    reason = 'max_nodes'
                    break
                nodes.add(other)
                queue.append((other, depth+1))
            edges.add(eid)
    return response(graph, nodes, edges, truncated=reason is not None, reason=reason,
                    selected=[entity], hops=hops, scanned_relationships=scanned,
                    semantics='undirected_connectivity; seed retained regardless of filters')


def transaction_lookup(graph, txid, **kwargs):
    return neighbourhood(graph, node_id('transaction', txid), hops=1, **kwargs)


def address_lookup(graph, address, **kwargs):
    return neighbourhood(graph, node_id('address', address), hops=1, **kwargs)


def suspicious_neighbourhood(graph, txid, min_score=None, **kwargs):
    entity = graph.require(node_id('transaction', txid))
    seed = graph.nodes[entity]
    if min_score is not None:
        threshold_filter = TransactionFilter(min_anomaly_score=min_score)
        accepted = seed['anomaly_score'] is not None and threshold_filter.matches(seed)
    else:
        accepted = seed['flagged'] is True
    if not accepted:
        raise ValueError('seed must be flagged or meet the supplied minimum score')
    kwargs.setdefault('hops', 2)
    return neighbourhood(graph, entity, **kwargs)


def timeline(graph, entity, hops=1, limits=None, filters=None):
    result = neighbourhood(graph, entity, hops, limits, filters)
    result['timeline'] = sorted((n for n in result['nodes'] if n['type'] == 'transaction'),
                                key=lambda n: (n['timestamp'], n['id']))
    return result


def search_transactions(graph, filters=None, limit=100, offset=0):
    if type(limit) is not int or not 1 <= limit <= 10000 or type(offset) is not int or offset < 0:
        raise ValueError('limit must be 1..10000 and offset nonnegative')
    filters = filters or TransactionFilter()
    ids = sorted((nid for nid, node in graph.nodes.items() if node['type'] == 'transaction' and filters.matches(node)),
                 key=lambda nid: (graph.nodes[nid]['timestamp'], nid))
    return response(graph, ids[offset:offset+limit], [], truncated=offset+limit < len(ids),
                    reason='page_limit' if offset+limit < len(ids) else None,
                    total_matches=len(ids), offset=offset, next_offset=offset+limit if offset+limit < len(ids) else None)


def find_path(graph, source, target, *, max_hops=12, limits=None, chronological=True, directed=True):
    """Shortest bounded path; chronological mode requires directed edges and strict time increase.

    Search state includes previous transaction time: revisiting a shared address
    after an earlier transaction can unlock a valid path. Search budget includes
    states and edge inspections, not just returned path size.
    """
    graph.require(source)
    graph.require(target)
    if type(max_hops) is not int or not 0 <= max_hops <= 100:
        raise ValueError('max_hops must be 0..100')
    if chronological and not directed:
        raise ValueError('chronological paths must be directed')
    limits = limits or Limits()
    last = graph.nodes[source]['timestamp'] if graph.nodes[source]['type'] == 'transaction' else None
    initial = (source, last)
    queue, parents = deque([(initial, 0)]), {initial: None}
    scanned, found, reason = 0, None, None
    while queue and reason is None:
        state, depth = queue.popleft()
        current, last = state
        if current == target:
            found = state
            break
        candidate_edges = graph.outgoing[current] if directed else graph.adjacent[current]
        if depth == max_hops:
            continue
        for eid in candidate_edges:
            if scanned >= limits.max_expansions:
                reason = 'max_expansions'
                break
            scanned += 1
            edge = graph.edges[eid]
            other = edge['target'] if edge['source'] == current else edge['source']
            next_time = graph.nodes[other]['timestamp'] if graph.nodes[other]['type'] == 'transaction' else last
            if chronological and graph.nodes[other]['type'] == 'transaction' and last is not None and next_time <= last:
                continue
            next_state = (other, next_time if chronological else None)
            if next_state in parents:
                continue
            if len(parents) >= limits.max_nodes or len(parents)-1 >= limits.max_edges:
                reason = 'search_state_limit'
                break
            parents[next_state] = (state, eid)
            queue.append((next_state, depth+1))
    ordered_nodes, ordered_edges = [], []
    cursor = found
    while cursor is not None:
        ordered_nodes.append(cursor[0])
        parent = parents[cursor]
        if parent is None:
            break
        cursor, eid = parent
        ordered_edges.append(eid)
    ordered_nodes.reverse()
    ordered_edges.reverse()
    return response(graph, set(ordered_nodes), set(ordered_edges), truncated=reason is not None, reason=reason,
                    path=ordered_nodes, selected=[source, target], found=found is not None,
                    ordered_node_ids=ordered_nodes, ordered_edge_ids=ordered_edges,
                    scanned_relationships=scanned, max_hops=max_hops,
                    semantics='chronological_address_linkage_not_verified_spends' if chronological else 'structural_connectivity')


def trace_sequence(graph, source, target, **kwargs):
    """Expose transaction -> address -> transaction steps without scenario metadata."""
    kwargs['chronological'], kwargs['directed'] = True, True
    result = find_path(graph, source, target, **kwargs)
    txs = [graph.nodes[n] for n in result['ordered_node_ids'] if graph.nodes[n]['type'] == 'transaction']
    result['sequence'] = [dict(txid=n['attributes']['txid'], timestamp=n['timestamp'],
                               amount_satoshis=n['attributes']['amount_satoshis'],
                               anomaly_score=n['anomaly_score'], flagged=n['flagged']) for n in txs]
    if len(txs) > 1:
        from pandas import Timestamp
        seconds = (Timestamp(txs[-1]['timestamp'])-Timestamp(txs[0]['timestamp'])).total_seconds()
        result['sequence_summary'] = dict(transaction_count=len(txs), elapsed_seconds=seconds,
                                          reason=f'{len(txs)} address-linked transactions within {seconds:g} seconds')
    else:
        result['sequence_summary'] = dict(transaction_count=len(txs), elapsed_seconds=0)
    return result
