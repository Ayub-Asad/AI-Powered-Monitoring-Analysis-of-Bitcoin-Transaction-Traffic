"""Bounded HTTP deployment smoke; standard library, no analytical mutation."""
import argparse
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

TX = '6438536fd7ddeb015a2a0a7e5cc5f0d2df04d600d9ea0592c9fa3f1a41db3202'
ADDRESS = '1ESbdF6ACUgGWDe9fvPjeisQRNLWvzPJtE'
FIRST = 'c03fa0edd88742770a0d009c75c20f5d979dd2ae1d4ef22203f390aed54c0f46'
LAST = '3ca9331ae6d7bbb004e69a8f7ef31114e4b034954a3b4d33536d4ac2ef7e913e'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def exercise(base, public=True):
    def get(path, raw=False):
        with urlopen(base+path, timeout=180) as response:
            body = response.read()
        return body if raw else json.loads(body)
    overview = get('/api/overview')
    expected = dict(total_transactions=18000, total_addresses=7059, graph_edges=60836,
                    flagged_transactions=6153, scored_transactions=18000)
    require(all(overview[k] == v for k,v in expected.items()), 'Frozen overview changed')
    health = get('/api/health')
    require(health['status'] == 'ok' and health['graph_status'] == 'ready', 'Not ready')
    for path in ['/', '/assets/app.js', '/assets/styles.css']:
        require(get(path, True), 'Missing dashboard asset: '+path)
    alerts = get('/api/alerts?flagged_only=true&limit=20')['items']
    require(alerts[0]['attributes']['txid'] == TX, 'Demo ranking changed')
    tx = get('/api/transactions/'+TX)
    node = next(n for n in tx['nodes'] if n['id'] == 'transaction:'+TX)
    require(node['threshold'] == 0.4977731392929165 and node['flagged'], 'Frozen threshold changed')
    require(get('/api/addresses/'+ADDRESS)['nodes'], 'Address missing')
    require(get('/api/graph/'+TX+'?hops=2')['edges'], 'Graph empty')
    require(get('/api/timeline/'+ADDRESS)['timeline'], 'Timeline empty')
    require(get('/api/search?q='+ADDRESS)['total_matches'] == 1, 'Search failed')
    trace = get(f'/api/trace?source={FIRST}&target={LAST}&max_hops=100')
    require(trace['found'] and len(trace['sequence']) == 30, 'Verified trace changed')
    try:
        urlopen(Request(base+'/ingest', data=b'invalid multipart', method='POST'), timeout=10)
        raise RuntimeError('Unexpected ingestion success')
    except HTTPError as error:
        require(error.code == (403 if public else 422), 'Incorrect ingestion mode')
    return dict(status='PASS', overview=overview, health=health, public_demo=public,
                demo_score=node['anomaly_score'], threshold=node['threshold'], trace_transactions=30)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--local-mode', action='store_true')
    parser.add_argument('--wait', type=int, default=240)
    args = parser.parse_args()
    start = time.monotonic()
    while True:
        try:
            with urlopen(args.base_url+'/api/health', timeout=3):
                break
        except OSError:
            if time.monotonic()-start > args.wait:
                raise SystemExit('Application readiness timed out')
            time.sleep(1)
    print(json.dumps(exercise(args.base_url.rstrip('/'), not args.local_mode), indent=2))
