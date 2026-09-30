"""Deployment safety tests without production fitting or dataset mutation."""
import asyncio
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
import app.main as main

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE'])
def test_public_mode_rejects_without_reading_body(monkeypatch, method):
    monkeypatch.setattr(main, 'PUBLIC_DEMO', True)
    messages = []
    async def forbidden(*args):
        raise AssertionError('Mutation reached body reader or downstream app')
    async def send(message):
        messages.append(message)
    asyncio.run(main.ReadOnlyDemo(forbidden)(
        {'type': 'http', 'method': method, 'path': '/ingest'}, forbidden, send))
    assert messages[0]['status'] == 403
    assert b'read-only' in messages[1]['body']


def test_public_reads_and_preload(monkeypatch):
    monkeypatch.setattr(main, 'PUBLIC_DEMO', True)
    calls = []
    monkeypatch.setattr(main.store, 'load', lambda: calls.append('load'))
    with TestClient(main.app) as client:
        assert calls == ['load']
        assert client.get('/api/health').status_code == 200
        assert client.get('/').status_code == 200
        assert client.post('/ingest', content=b'not multipart').status_code == 403


def test_local_ingestion_contract_retained(monkeypatch):
    monkeypatch.setattr(main, 'PUBLIC_DEMO', False)
    with TestClient(main.app) as client:
        assert client.post('/ingest').status_code == 422


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize('value', ['0', '65536', 'abc', '8000;echo', '-1'])
def test_invalid_port(value):
    with pytest.raises(ValueError):
        module('container_start', 'deploy/start.py').port_value(value)


def test_model_handoff_rejects_missing_and_tampered(tmp_path):
    stage = module('stage_model', 'scripts/stage_demo_model.py')
    with pytest.raises(ValueError, match='Missing or changed'):
        stage.verify(tmp_path)
    (tmp_path/'pipeline.joblib').write_bytes(b'untrusted')
    with pytest.raises(ValueError, match='Missing or changed'):
        stage.verify(tmp_path)
