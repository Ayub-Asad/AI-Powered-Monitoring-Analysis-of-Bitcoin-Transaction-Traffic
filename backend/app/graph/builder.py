"""Build only from canonical transactions. No ground truth or scenario access."""
from collections import defaultdict
import json
import math
import pandas as pd
from app.money import to_satoshis, from_satoshis
from app.features.schema import FORBIDDEN_FIELDS
from .schema import InvestigationGraph, node_id, utc


def scalar(value):
    if value is None or pd.isna(value):
        return None
    return value.item() if hasattr(value, 'item') else value


def score_index(scores, txids):
    if scores is None:
        return {}
    required = {'txid', 'anomaly_score', 'threshold', 'flagged', 'model_version'}
    if not required.issubset(scores.columns) or scores.txid.isna().any() or scores.txid.duplicated().any():
        raise ValueError('scores require unique TXIDs and the existing scoring contract')
    if not set(scores.txid).issubset(txids):
        raise ValueError('score TXIDs do not belong to this graph')
    result = {}
    for row in scores.to_dict('records'):
        score, threshold = float(row['anomaly_score']), float(row['threshold'])
        flag = scalar(row['flagged'])
        if not math.isfinite(score) or not math.isfinite(threshold) or type(flag) is not bool or flag != (score >= threshold):
            raise ValueError('invalid score, threshold or inconsistent flag')
        if not isinstance(row['model_version'], str) or not row['model_version']:
            raise ValueError('model_version must be a nonempty string')
        result[row['txid']] = dict(anomaly_score=score, threshold=threshold, flagged=flag,
                                  model_version=row['model_version'])
    return result


def build_graph(transactions, scores=None):
    if not isinstance(transactions, pd.DataFrame):
        raise TypeError('pass IngestionResult.transactions')
    if FORBIDDEN_FIELDS.intersection(transactions.columns):
        raise ValueError('evaluation/actor/scenario metadata is not graph input')
    if transactions.txid.isna().any() or transactions.txid.duplicated().any():
        raise ValueError('canonical TXIDs must be present and unique')
    scored = score_index(scores, set(transactions.txid))
    graph = InvestigationGraph()
    adjacent, outgoing = defaultdict(list), defaultdict(list)
    network_fields = ('src_ip', 'dst_ip', 'src_port', 'dst_port', 'country', 'asn', 'asn_org')
    for row in transactions.sort_values('txid').to_dict('records'):
        tid, stamp = node_id('transaction', row['txid']), utc(row['timestamp'])
        amounts = [row.get(f'{side}_amounts') for side in ('input', 'output')]
        available = [isinstance(value, list) for value in amounts]
        if available[0] != available[1]:
            raise ValueError('allocation arrays must be paired')
        attrs = {key: scalar(row.get(key)) for key in ('num_inputs', 'num_outputs', 'fee_rate_sat_vb', 'source_row')}
        attrs.update(txid=row['txid'], amount_satoshis=to_satoshis(row['amount_btc']),
                     fee_satoshis=to_satoshis(row['fee_btc']), amount_btc=row['amount_btc'], fee_btc=row['fee_btc'],
                     allocation_available=all(available),
                     amount_semantics='sum_outputs_including_change' if all(available) else 'legacy_source_total',
                     network_context={key: scalar(row.get(key)) for key in network_fields},
                     network_provenance={'source': 'canonical_ingestion', 'source_row': scalar(row.get('source_row')),
                                         'interpretation': 'reported_or_synthetic_observation_not_ownership'})
        score = scored.get(row['txid'], dict(anomaly_score=None, threshold=None, flagged=None, model_version=None))
        graph.nodes[tid] = dict(id=tid, type='transaction', label=row['txid'][:10]+'…'+row['txid'][-6:],
                                timestamp=stamp, **score, attributes=attrs)
        for side, allocations in zip(('input', 'output'), amounts):
            addresses = row[f'{side}_addresses']
            if all(available) and len(addresses) != len(allocations):
                raise ValueError('allocation length mismatch')
            grouped = defaultdict(lambda: [0, 0])
            for i, address in enumerate(addresses):
                grouped[address][0] += 1
                if all(available):
                    grouped[address][1] += to_satoshis(allocations[i])
            for address, (count, amount) in sorted(grouped.items()):
                aid = node_id('address', address)
                graph.nodes.setdefault(aid, dict(id=aid, type='address', label=address[:10]+'…'+address[-6:],
                                                timestamp=None, anomaly_score=None, flagged=None,
                                                attributes={'address': address}))
                source, target = (aid, tid) if side == 'input' else (tid, aid)
                eid = json.dumps([side, row['txid'], address], separators=(',', ':'))
                graph.edges[eid] = dict(id=eid, source=source, target=target, type=side,
                                        amount_satoshis=amount if all(available) else None,
                                        amount_btc=from_satoshis(amount) if all(available) else None,
                                        attributes={'allocation_count': count})
                adjacent[source].append(eid)
                adjacent[target].append(eid)
                outgoing[source].append(eid)
        if all(available):
            ins, outs = (sum(to_satoshis(v) for v in values) for values in amounts)
            if outs != attrs['amount_satoshis'] or ins != outs + attrs['fee_satoshis']:
                raise ValueError('canonical allocation conservation violated')
    graph.adjacent = {n: tuple(sorted(adjacent[n])) for n in graph.nodes}
    graph.outgoing = {n: tuple(sorted(outgoing[n])) for n in graph.nodes}
    from .analytics import annotate
    annotate(graph)
    return graph
