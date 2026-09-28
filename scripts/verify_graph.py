"""Read-only development verification; scenario sidecar is evaluation-only.

No dataset generation, training, threshold changes or frozen report writes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.ingestion import ingest_file
from app.graph import (build_graph, Limits, dumps, transaction_lookup, address_lookup,
                       neighbourhood, trace_sequence, timeline, suspicious_neighbourhood)
from app.graph.integration import score_with_artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='new compact report; refuses overwrite')
    parser.add_argument('--protected-inventory', type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    timings = {}
    def measured(name, operation):
        start = perf_counter()
        result = operation()
        timings[name] = perf_counter()-start
        return result
    ingested = measured('ingestion', lambda: ingest_file(ROOT/'data/v2/development.csv'))
    txs = ingested.transactions
    assert len(txs) == 18000
    unscored = measured('unscored_construction', lambda: build_graph(txs))
    assert all(n['anomaly_score'] is None for n in unscored.nodes.values())
    del unscored
    artifact = ROOT/'artifacts/ml/tuning/run-001/tuned-42'
    scores = measured('frozen_inference', lambda: score_with_artifact(txs, artifact))
    graph = measured('scored_construction', lambda: build_graph(txs, scores))
    for score in scores.to_dict('records'):
        node = graph.nodes['transaction:'+score['txid']]
        assert all(node[key] == score[key] for key in ('anomaly_score', 'threshold', 'flagged', 'model_version'))
    txid = sorted(txs.txid)[0]
    address = sorted(n['attributes']['address'] for n in graph.nodes.values() if n['type'] == 'address')[0]
    lookup = measured('transaction_lookup', lambda: transaction_lookup(graph, txid))
    addr = measured('address_lookup', lambda: address_lookup(graph, address))
    multi = measured('three_hop', lambda: neighbourhood(graph, 'transaction:'+txid, 3))
    bounded = measured('limited_three_hop', lambda: neighbourhood(graph, 'transaction:'+txid, 3, Limits(max_nodes=10)))
    assert bounded['truncated'] and len(bounded['nodes']) <= 10
    flagged = scores.loc[scores.flagged, 'txid'].iloc[0]
    suspicious = measured('suspicious_neighbourhood', lambda: suspicious_neighbourhood(graph, flagged))
    ordered = measured('timeline', lambda: timeline(graph, 'address:'+address))
    assert ordered['timeline'] == sorted(ordered['timeline'], key=lambda n: (n['timestamp'], n['id']))
    for result in (lookup, addr, multi, bounded, suspicious, ordered):
        json.loads(dumps(result))
    # Evaluation metadata selects examples ONLY AFTER construction and scoring.
    # Generic path utilities receive entity IDs, never categories/scenario IDs.
    truth = [json.loads(line) for line in (ROOT/'data/v2/development.ground_truth.jsonl').read_text().splitlines()]
    examples = {}
    for category in ('rapid_fire_layering', 'peeling_chain'):
        scenario = next(r['scenario_id'] for r in truth if r['anomaly_type'] == category)
        members = sorted((r['txid'] for r in truth if r['scenario_id'] == scenario),
                         key=lambda t: (graph.nodes['transaction:'+t]['timestamp'], t))
        start = perf_counter()
        for first, second in zip(members, members[1:]):
            pair = trace_sequence(graph, 'transaction:'+first, 'transaction:'+second, max_hops=2,
                                  limits=Limits(max_nodes=2000, max_edges=4000, max_expansions=20000))
            assert pair['found'], (category, first, second)
        path = trace_sequence(graph, 'transaction:'+members[0], 'transaction:'+members[-1],
                              max_hops=2*(len(members)-1),
                              limits=Limits(max_nodes=2000, max_edges=4000, max_expansions=20000))
        # Dense shared-address activity can exhaust a long-path budget. Retain
        # that outcome; verify a practical three-transaction view separately.
        preview = trace_sequence(graph, 'transaction:'+members[0], 'transaction:'+members[2], max_hops=4,
                                 limits=Limits(max_nodes=2000, max_edges=4000, max_expansions=20000))
        assert preview['found']
        examples[category] = dict(evaluation_only=True, scenario_transaction_count=len(members),
                                  adjacent_pairs_reconstructed=len(members)-1,
                                  first_txid=members[0], last_txid=members[-1],
                                  returned_sequence=path['sequence_summary'],
                                  end_to_end_found=path['found'], end_to_end_truncated=path['truncated'],
                                  end_to_end_truncation_reason=path['truncation_reason'],
                                  three_transaction_preview=preview['sequence_summary'],
                                  full_scenario_order_reconstructed=[t['txid'] for t in path['sequence']] == members,
                                  seconds=perf_counter()-start)
    protection = None
    if args.protected_inventory:
        inventory = json.loads(args.protected_inventory.read_text())
        changed = [p for p, value in inventory.items() if not (ROOT/p).is_file() or
                   hashlib.sha256((ROOT/p).read_bytes()).hexdigest() != value]
        assert not changed, changed
        protection = dict(files_checked=len(inventory), changed=changed)
    report = dict(status='PASS', dataset='data/v2/development.csv',
                  artifact=str(artifact.relative_to(ROOT)).replace('\\', '/'),
                  artifact_manifest_sha256=hashlib.sha256((artifact/'manifest.json').read_bytes()).hexdigest(),
                  nodes=len(graph.nodes), edges=len(graph.edges), transactions=len(txs),
                  addresses=len(graph.nodes)-len(txs), scored_transactions=len(scores),
                  flagged_transactions=int(scores.flagged.sum()), seconds=timings,
                  representative_txid=txid, representative_address=address,
                  three_hop_summary=multi['summary'], three_hop_truncated=multi['truncated'],
                  bounded_summary=bounded['summary'], examples=examples, protected=protection,
                  scope='Synthetic development smoke verification, not model evaluation or verified UTXO tracing')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
