"""Focused release integrity and location tests; no production regeneration."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('release_tools', ROOT/'scripts/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_release_inventory_excludes_training_and_secrets():
    names = release.inventory()
    assert 'data/v2/development.csv' in names
    assert f'{release.MODEL}/pipeline.joblib' in names
    assert not any('data/ml/' in n or '__pycache__' in n or '.env' in n for n in names)
    assert not any('ground_truth' in n or 'predictions' in n for n in names)
    assert len([n for n in names if n.endswith('.joblib')]) == 1


def test_integrity_detects_changed_and_missing_file(tmp_path):
    (tmp_path/'data').write_bytes(b'original')
    (tmp_path/'release_manifest.json').write_text(json.dumps(dict(version=1, files={'data': release.digest(tmp_path/'data')})))
    release.verify(tmp_path)
    (tmp_path/'data').write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        release.verify(tmp_path)
    (tmp_path/'data').unlink()
    with pytest.raises(ValueError, match='missing'):
        release.verify(tmp_path)


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'C:/absolute', 'bad\\path'])
def test_rejects_unsafe_manifest_paths(tmp_path, name):
    (tmp_path/'release_manifest.json').write_text(json.dumps(dict(version=1, files={name: 'bad'})))
    with pytest.raises(ValueError, match='unsafe'):
        release.verify(tmp_path)


def test_release_from_unrelated_working_directory(tmp_path):
    result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/release.py'), 'verify'],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout+result.stderr


def test_runtime_default_locations_from_unrelated_directory(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'backend'))
    monkeypatch.chdir(tmp_path)
    from app.investigation import ROOT as app_root
    from app.ml.schema import ROOT as ml_root
    assert app_root == ml_root == ROOT
    assert (app_root/'data/v2/development.csv').is_file()
    assert (app_root/release.MODEL/'manifest.json').is_file()
    assert (app_root/'frontend/dist/index.html').is_file()


def test_shell_files_are_lf_and_offline_pip_is_explicit():
    for name in ('install.sh', 'start.sh', 'verify.sh', 'scripts/build_wheelhouse.sh'):
        data = (ROOT/name).read_bytes()
        assert data.startswith(b'#!/usr/bin/env bash\n') and b'\r' not in data
    script = (ROOT/'install.sh').read_text()
    assert '--no-index' in script and '--only-binary=:all:' in script
    assert b'\r' not in (ROOT/'frontend/dist/manifest.json').read_bytes()


def test_frozen_versions_match_runtime_lock():
    artifact = json.loads((ROOT/release.MODEL/'manifest.json').read_text())
    lock = (ROOT/'backend/requirements-offline-lock.txt').read_text()
    assert artifact['environment']['python'] == release.PYTHON
    for name, version in artifact['environment'].items():
        if name != 'python':
            assert f'{name}=={version}' in lock
