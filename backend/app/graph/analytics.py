"""Linear-time descriptive statistics; never ownership or risk inference."""


def annotate(graph):
    unseen = set(graph.nodes)
    while unseen:
        root = unseen.pop()
        stack, component = [root], {root}
        while stack:
            current = stack.pop()
            for eid in graph.adjacent[current]:
                edge = graph.edges[eid]
                other = edge['target'] if edge['source'] == current else edge['source']
                if other in unseen:
                    unseen.remove(other)
                    component.add(other)
                    stack.append(other)
        for node in component:
            graph.component_sizes[node] = len(component)
    for nid, node in graph.nodes.items():
        edges = [graph.edges[e] for e in graph.adjacent[nid]]
        incoming = [e for e in edges if e['target'] == nid]
        outgoing = [e for e in edges if e['source'] == nid]
        attrs = node['attributes']
        attrs.update(degree=len(edges), incoming_relationship_count=len(incoming),
                     outgoing_relationship_count=len(outgoing), component_size=graph.component_sizes[nid])
        if node['type'] == 'transaction':
            attrs.update(unique_input_addresses=len(incoming), unique_output_addresses=len(outgoing))
            continue
        tids = {e['target'] if e['source'] == nid else e['source'] for e in edges}
        txs = [graph.nodes[t] for t in tids]
        scores = [t['anomaly_score'] for t in txs if t['anomaly_score'] is not None]
        attrs.update(transaction_count=len(tids), scored_transaction_count=len(scores),
                     flagged_transaction_count=sum(t['flagged'] is True for t in txs),
                     max_anomaly_score=max(scores, default=None),
                     first_seen=min(t['timestamp'] for t in txs), last_seen=max(t['timestamp'] for t in txs),
                     repeated_allocation_count=sum(e['attributes']['allocation_count']-1 for e in edges))
        for name, group in (('incoming', incoming), ('outgoing', outgoing)):
            known = [e['amount_satoshis'] for e in group if e['amount_satoshis'] is not None]
            attrs[f'known_{name}_satoshis'] = sum(known)
            attrs[f'{name}_value_complete'] = len(known) == len(group)
            attrs[f'total_{name}_satoshis'] = sum(known) if len(known) == len(group) else None
