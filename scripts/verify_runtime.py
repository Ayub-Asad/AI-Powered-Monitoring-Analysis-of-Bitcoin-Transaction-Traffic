"""Exercise bundled ASGI routes with Python network connections denied.

This is process-level verification, not an OS firewall or browser isolation test.
Uses only runtime dependencies; never needs pytest/httpx or training data.
"""
import asyncio
import json
import os
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
sys.path.insert(0, str(ROOT/'scripts'))
TX = '6438536fd7ddeb015a2a0a7e5cc5f0d2df04d600d9ea0592c9fa3f1a41db3202'
ADDRESS = '1ESbdF6ACUgGWDe9fvPjeisQRNLWvzPJtE'
FIRST = 'c03fa0edd88742770a0d009c75c20f5d979dd2ae1d4ef22203f390aed54c0f46'
LAST = '3ca9331ae6d7bbb004e69a8f7ef31114e4b034954a3b4d33536d4ac2ef7e913e'


async def get(app, url, raw=False):
    parsed = urlsplit(url)
    messages = []

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(message):
        messages.append(message)

    await app(dict(type='http', asgi={'version': '3.0'}, http_version='1.1', method='GET',
                   scheme='http', path=parsed.path, raw_path=parsed.path.encode(),
                   query_string=parsed.query.encode(), root_path='', headers=[],
                   client=('127.0.0.1', 1), server=('127.0.0.1', 8000)), receive, send)
    status = next(m['status'] for m in messages if m['type'] == 'http.response.start')
    if status != 200:
        raise RuntimeError(f'{url}: HTTP {status}')
    body = b''.join(m.get('body', b'') for m in messages)
    return body if raw else json.loads(body)


async def exercise():
    from app.main import app
    assert (await get(app, '/health'))['status'] == 'ok'
    assert await get(app, '/', raw=True)
    for name in ('app.js', 'styles.css'):
        assert await get(app, '/assets/'+name, raw=True)
    overview = await get(app, '/api/overview')
    assert overview['total_transactions'] == 18000
    assert overview['scored_transactions'] == 18000
    alerts = (await get(app, '/api/alerts?limit=20'))['items']
    assert alerts[0]['attributes']['txid'] == TX
    assert alerts[0]['attributes']['network_context']['src_ip']
    assert (await get(app, '/api/transactions/'+TX))['nodes']
    assert (await get(app, '/api/addresses/'+ADDRESS))['nodes']
    assert (await get(app, '/api/search?q='+ADDRESS))['total_matches'] == 1
    assert (await get(app, '/api/timeline/'+ADDRESS))['timeline']
    for hops in (1, 2, 3):
        graph = await get(app, f'/api/graph/{TX}?hops={hops}')
        assert graph['nodes'] and len(graph['nodes']) <= 80 and len(graph['edges']) <= 160
    trace = await get(app, f'/api/trace?source={FIRST}&target={LAST}&max_hops=100')
    assert trace['found'] and len(trace['sequence']) == 30
    return dict(overview=overview, demo_transaction=TX, demo_address=ADDRESS,
                trace=trace['sequence_summary'])


def main():
    from release import check_python, verify, inventory
    check_python()
    assert verify()['files'] == inventory()
    if os.environ.get('BTI_DATASET') or os.environ.get('BTI_ARTIFACT'):
        raise ValueError('unset BTI_DATASET/BTI_ARTIFACT to verify the bundled defaults')
    started = time.perf_counter()
    # Creating the event loop can require a local socketpair on Windows.
    loop = asyncio.new_event_loop()
    try:
        with patch.object(socket.socket, 'connect', side_effect=RuntimeError('network denied by release verifier')), \
             patch.object(socket.socket, 'connect_ex', side_effect=RuntimeError('network denied by release verifier')), \
             patch.object(socket.socket, 'sendto', side_effect=RuntimeError('network denied by release verifier')), \
             patch.object(socket, 'getaddrinfo', side_effect=RuntimeError('DNS denied by release verifier')):
            result = loop.run_until_complete(exercise())
    finally:
        loop.close()
    print(json.dumps(dict(status='PASS', seconds=round(time.perf_counter()-started, 3),
                         network_test='Python socket connect/connect_ex/sendto/DNS denied; not OS isolation', **result), indent=2))


if __name__ == '__main__':
    main()
