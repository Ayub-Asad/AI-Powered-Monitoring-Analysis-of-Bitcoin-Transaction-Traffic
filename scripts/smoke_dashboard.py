"""Local HTTP + optional Chromium DevTools smoke; standard library only.

Start the API and a headless Chromium browser with --remote-debugging-port=9223.
No external requests, generated corpora, or model fitting.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import time
from urllib.request import urlopen
from urllib.parse import urlsplit, quote

ROOT=Path(__file__).resolve().parents[1]
FIRST='c03fa0edd88742770a0d009c75c20f5d979dd2ae1d4ef22203f390aed54c0f46'
LAST='3ca9331ae6d7bbb004e69a8f7ef31114e4b034954a3b4d33536d4ac2ef7e913e'


def get(url):
    with urlopen(url,timeout=90) as r:
        return json.load(r)


class CDP:
    """Minimal local RFC6455 client for Chromium JSON commands."""
    def __init__(self,url):
        u=urlsplit(url)
        self.sock=socket.create_connection((u.hostname,u.port),timeout=30)
        key=base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f'GET {u.path} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        header=b''
        while not header.endswith(b'\r\n\r\n'):header+=self.read(1)
        assert header.startswith(b'HTTP/1.1 101 '),header
        self.counter=0
        self.events=[]

    def read(self,n):
        data=b''
        while len(data)<n:
            chunk=self.sock.recv(n-len(data))
            if not chunk:raise RuntimeError('Browser closed connection')
            data+=chunk
        return data

    def call(self,method,params=None):
        self.counter+=1
        data=json.dumps(dict(id=self.counter,method=method,params=params or {})).encode()
        mask=os.urandom(4);n=len(data)
        header=bytes([0x81,0x80|n]) if n<126 else bytes([0x81,0xfe])+struct.pack('!H',n)
        self.sock.sendall(header+mask+bytes(v^mask[i%4] for i,v in enumerate(data)))
        while True:
            first,second=self.read(2);size=second&127
            if size==126:size=struct.unpack('!H',self.read(2))[0]
            elif size==127:size=struct.unpack('!Q',self.read(8))[0]
            payload=self.read(size)
            if first&15==8:raise RuntimeError('Browser socket closed')
            message=json.loads(payload)
            if message.get('id')==self.counter:
                if 'error' in message:raise RuntimeError(message['error'])
                return message['result']
            self.events.append(message)

    def evaluate(self,expression):
        r=self.call('Runtime.evaluate',dict(expression=expression,awaitPromise=True,returnByValue=True))
        if 'exceptionDetails' in r:raise AssertionError(r['exceptionDetails'])
        return r['result'].get('value')

    def wait(self,expression):
        for _ in range(150):
            if self.evaluate(expression):return
            time.sleep(.2)
        raise AssertionError('Browser condition timed out: '+expression)


def main():
    p=argparse.ArgumentParser();p.add_argument('--browser-port',type=int);args=p.parse_args()
    started=time.perf_counter();base='http://127.0.0.1:8000'
    overview=get(base+'/api/overview');assert overview['total_transactions']==18000
    alerts=get(base+'/api/alerts?flagged_only=true&limit=20')['items']
    assert all(a['anomaly_score']>=b['anomaly_score'] for a,b in zip(alerts,alerts[1:]))
    txid=alerts[0]['attributes']['txid']
    graph=get(base+'/api/graph/'+txid)
    address=next(n['attributes']['address'] for n in graph['nodes'] if n['type']=='address')
    assert get(base+'/api/transactions/'+txid)['nodes']
    assert get(base+'/api/addresses/'+address)['nodes']
    assert get(base+'/api/timeline/'+address)['timeline']
    assert get(base+'/api/search?q='+address)['total_matches']==1
    for hops in (1,2,3):
        d=get(base+f'/api/graph/{txid}?hops={hops}&max_nodes=10&max_edges=15')
        assert len(d['nodes'])<=10 and len(d['edges'])<=15
    demo=get(base+f'/api/trace?source={FIRST}&target={LAST}&max_hops=100')
    assert demo['found'] and len(demo['sequence'])==30
    assert alerts[0]['attributes']['network_context']['src_ip']
    report=dict(status='PASS',overview=overview,queue_first_txid=txid,address=address,
                demo=dict(first=FIRST,last=LAST,summary=demo['sequence_summary']),browser='not run')
    if args.browser_port:
        tabs=get(f'http://127.0.0.1:{args.browser_port}/json')
        c=CDP(next(t['webSocketDebuggerUrl'] for t in tabs if t['type']=='page'))
        c.call('Runtime.enable');c.call('Network.enable');c.call('Page.enable')
        c.call('Network.setBlockedURLs',{'urls':['https://*']})
        c.call('Emulation.setDeviceMetricsOverride',dict(width=1366,height=768,deviceScaleFactor=1,mobile=False))
        c.call('Page.navigate',{'url':base})
        c.wait("document.querySelectorAll('.node').length>0")
        assert c.evaluate("document.querySelectorAll('.metric').length===4")
        c.evaluate("document.querySelectorAll('.queue-row')[1].click()")
        c.wait("document.querySelectorAll('.queue-row')[1].classList.contains('selected')")
        assert c.evaluate("document.getElementById('details').textContent.includes('NETWORK OBSERVATION CONTEXT')")
        c.evaluate("document.getElementById('hops').value='2';document.getElementById('hops').dispatchEvent(new Event('change'))")
        c.wait("document.getElementById('graph-message').textContent.includes('Bound') || document.getElementById('graph-message').textContent.includes('2 hop')")
        c.evaluate("document.getElementById('hops').value='3';document.getElementById('hops').dispatchEvent(new Event('change'))")
        c.wait("document.getElementById('graph-message').textContent.includes('Bound') || document.getElementById('graph-message').textContent.includes('3 hop')")
        c.evaluate("document.querySelector('.node[data-id^=\"address:\"]').dispatchEvent(new MouseEvent('click'))")
        c.wait("document.getElementById('entity-type').textContent==='Observed address'")
        assert c.evaluate("document.querySelectorAll('#timeline button').length>0")
        c.evaluate("document.getElementById('expand').click()")
        c.wait("document.getElementById('notice').textContent.startsWith('Investigation ready')")
        c.evaluate(f"document.getElementById('search').value='{FIRST}';document.getElementById('search-form').dispatchEvent(new Event('submit',{{cancelable:true}}))")
        c.wait(f"document.getElementById('details').textContent.includes('{FIRST}')")
        c.evaluate("document.getElementById('trace-start').click()")
        c.evaluate(f"document.getElementById('search').value='{LAST}';document.getElementById('search-form').dispatchEvent(new Event('submit',{{cancelable:true}}))")
        c.wait(f"document.getElementById('details').textContent.includes('{LAST}')")
        c.evaluate("document.getElementById('trace').click()")
        c.wait("document.getElementById('trace-summary').textContent.includes('30 address-linked')")
        assert c.evaluate("document.querySelectorAll('.edge.path').length>0")
        c.evaluate("document.getElementById('zoom-in').click()")
        assert 'scale(1.25)' in c.evaluate("document.getElementById('viewport').getAttribute('transform')")
        c.evaluate("document.getElementById('fit').click()")
        assert 'scale(1)' in c.evaluate("document.getElementById('viewport').getAttribute('transform')")
        point=c.evaluate("(()=>{const r=document.getElementById('graph').getBoundingClientRect();return {x:r.left+10,y:r.top+10}})()")
        c.call('Input.dispatchMouseEvent',dict(type='mousePressed',button='left',clickCount=1,**point))
        c.call('Input.dispatchMouseEvent',dict(type='mouseMoved',button='left',buttons=1,x=point['x']+20,y=point['y']+10))
        c.call('Input.dispatchMouseEvent',dict(type='mouseReleased',button='left',clickCount=1,x=point['x']+20,y=point['y']+10))
        assert 'translate(0 0)' not in c.evaluate("document.getElementById('viewport').getAttribute('transform')")
        c.evaluate("document.getElementById('fit').click()")
        screenshot=c.call('Page.captureScreenshot',{'captureBeyondViewport':True})
        out=ROOT/'artifacts/dashboard';out.mkdir(parents=True,exist_ok=True)
        (out/'workspace.png').write_bytes(base64.b64decode(screenshot['data']))
        for width,height in [(1920,1080),(768,900)]:
            c.call('Emulation.setDeviceMetricsOverride',dict(width=width,height=height,deviceScaleFactor=1,mobile=False))
            assert c.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),width
        c.evaluate("document.getElementById('search').value='noSuchObservation123';document.getElementById('search-form').dispatchEvent(new Event('submit',{cancelable:true}))")
        c.wait("document.getElementById('notice').textContent==='No matching observations.'")
        c.evaluate("document.getElementById('search').value='<invalid>';document.getElementById('search-form').dispatchEvent(new Event('submit',{cancelable:true}))")
        c.wait("document.getElementById('notice').classList.contains('error')")
        c.call('Network.setBlockedURLs',{'urls':['https://*','*/api/search*']})
        c.evaluate("document.getElementById('search').value='valid';document.getElementById('search-form').dispatchEvent(new Event('submit',{cancelable:true}))")
        c.wait("document.getElementById('notice').textContent.includes('fetch')")
        c.call('Network.setBlockedURLs',{'urls':['https://*']})
        requests=[e['params']['request']['url'] for e in c.events if e.get('method')=='Network.requestWillBeSent']
        external=[u for u in requests if not u.startswith((base,'data:'))]
        errors=[e for e in c.events if e.get('method')=='Runtime.exceptionThrown']
        assert not external,external
        assert not errors,errors
        report['browser']=dict(status='PASS',viewports=['1366x768','1920x1080','768x900'],requests=len(requests),external_requests=external,exceptions=errors,
            checks=['queue click','network context','1/2/3 hops','address selection','expansion','timeline','exact search','chronological trace','path highlight','zoom','reset','pan','no results','invalid input','request failure'])
        c.sock.close()
    inventory=json.loads((ROOT/'artifacts/graph/protected-before.json').read_text())
    changed=[path for path,digest in inventory.items() if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest]
    assert not changed,changed
    report['protected']=dict(files_checked=len(inventory),changed=changed)
    report['seconds']=round(time.perf_counter()-started,3)
    target=ROOT/'reports/dashboard';target.mkdir(exist_ok=True)
    (target/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
