"""Read-only offline graph smoke/benchmark; optional bounded investigation JSON."""
import argparse
import json
from pathlib import Path
from time import perf_counter
from app.ingestion import ingest_file
from . import build_graph, neighbourhood, transaction_lookup, address_lookup, dumps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--artifact', type=Path, help='trusted local frozen model directory')
    parser.add_argument('--entity', help='namespaced transaction:TXID or address:ADDRESS')
    parser.add_argument('--hops', type=int, default=2)
    parser.add_argument('--out', type=Path, help='new bounded JSON file; refuses overwrite')
    args = parser.parse_args()
    start = perf_counter()
    ingested = ingest_file(args.input)
    ingestion_seconds = perf_counter()-start
    scores, scoring_seconds = None, None
    if args.artifact:
        from .integration import score_with_artifact
        start = perf_counter()
        scores = score_with_artifact(ingested.transactions, args.artifact)
        scoring_seconds = perf_counter()-start
    start = perf_counter()
    graph = build_graph(ingested.transactions, scores)
    construction_seconds = perf_counter()-start
    if not graph.nodes:
        raise ValueError('no usable transactions')
    txid = sorted(ingested.transactions.txid)[0]
    address = sorted(n['attributes']['address'] for n in graph.nodes.values() if n['type'] == 'address')[0]
    timings = {}
    for name, operation in [('transaction_lookup', lambda: transaction_lookup(graph, txid)),
                            ('address_lookup', lambda: address_lookup(graph, address)),
                            ('neighbourhood', lambda: neighbourhood(graph, args.entity or f'transaction:{txid}', args.hops))]:
        start = perf_counter()
        result = operation()
        timings[name] = perf_counter()-start
        # Strict JSON encoding is part of the smoke verification.
        dumps(result)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x', encoding='utf-8') as handle:
            handle.write(dumps(result)+'\n')
    print(json.dumps(dict(nodes=len(graph.nodes), edges=len(graph.edges), transactions=len(ingested.transactions),
                          addresses=len(graph.nodes)-len(ingested.transactions),
                          scored_transactions=0 if scores is None else len(scores),
                          flagged_transactions=0 if scores is None else int(scores.flagged.sum()),
                          ingestion_seconds=ingestion_seconds, scoring_seconds=scoring_seconds,
                          construction_seconds=construction_seconds, operation_seconds=timings,
                          sample_summary=result['summary'], sample_truncated=result['truncated']), indent=2))


if __name__ == '__main__':
    main()
