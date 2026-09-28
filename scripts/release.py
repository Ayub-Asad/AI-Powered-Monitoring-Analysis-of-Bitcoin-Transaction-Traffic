"""Offline release inventory, checksum verification and allowlisted tar packaging.

No model loading, fitting, generation, network access or third-party imports.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'artifacts/ml/tuning/run-001/tuned-42'
PYTHON = '3.13.14'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(root=ROOT):
    names = ['install.sh', 'start.sh', 'verify.sh', 'README_OFFLINE.md',
             'backend/requirements.txt', 'backend/requirements-offline-lock.txt',
             'scripts/build_dashboard.py', 'scripts/release.py',
             'scripts/build_wheelhouse.sh', 'scripts/verify_runtime.py',
             'docs/demo_walkthrough.md', 'docs/release_checklist.md',
             'data/v2/development.csv']
    names += [f'{MODEL}/{name}' for name in ('pipeline.joblib', 'manifest.json', 'threshold.json')]
    names += [p.relative_to(root).as_posix() for p in (root/'backend/app').rglob('*.py')]
    names += [f'frontend/{folder}/{name}' for folder in ('src', 'dist')
              for name in ('index.html', 'styles.css', 'app.js')]
    names += ['frontend/dist/manifest.json']
    return {name: digest(root/name) for name in sorted(names)}


def verify(root=ROOT, manifest='release_manifest.json'):
    data = json.loads((root/manifest).read_text(encoding='utf-8'))
    if data.get('version') != 1 or not data.get('files'):
        raise ValueError('invalid or empty checksum manifest')
    for name, expected in data['files'].items():
        relative = PurePosixPath(name)
        candidate = (root/name).resolve()
        if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name or not candidate.is_relative_to(root.resolve()):
            raise ValueError(f'unsafe manifest path: {name}')
        if not candidate.is_file() or digest(candidate) != expected:
            raise ValueError(f'missing or changed release file: {name}')
    return data


def check_python():
    if platform.python_implementation() != 'CPython' or platform.python_version() != PYTHON:
        raise ValueError(f'frozen artifact requires CPython {PYTHON}; got {platform.python_version()}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['manifest', 'verify', 'python', 'wheels', 'verify-wheels', 'bundle'])
    parser.add_argument('--output', type=Path, default=ROOT/'releases/bitcoin-offline.tar.gz')
    parser.add_argument('--without-wheels', action='store_true', help='preparation bundle only, NOT offline-installable')
    args = parser.parse_args()
    if args.action == 'python':
        check_python()
    elif args.action == 'manifest':
        (ROOT/'release_manifest.json').write_text(json.dumps(dict(version=1, python=PYTHON, files=inventory()), indent=2)+'\n', encoding='utf-8')
    elif args.action == 'verify':
        data = verify()
        # Do not accept an accidentally shortened runtime inventory.
        if data['files'] != inventory():
            raise ValueError('release inventory differs from the required runtime files')
        print(f"Verified {len(data['files'])} release files")
    elif args.action == 'wheels':
        if platform.system() != 'Linux':
            raise ValueError('build Linux wheels on the compatible Linux preparation machine')
        check_python()
        files = sorted((ROOT/'wheels').glob('*.whl'))
        if not files:
            raise ValueError('wheelhouse is empty')
        data = dict(version=1, python=PYTHON, platform=platform.platform(), machine=platform.machine(),
                    lock_sha256=digest(ROOT/'backend/requirements-offline-lock.txt'),
                    files={p.name: digest(p) for p in files})
        (ROOT/'wheels/manifest.json').write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    else:
        if args.action == 'bundle':
            data = verify()
            if data['files'] != inventory():
                raise ValueError('regenerate the release manifest before packaging')
        if args.action == 'verify-wheels' or not args.without_wheels:
            wheels = verify(ROOT/'wheels', 'manifest.json')
            if wheels.get('python') != PYTHON or wheels.get('lock_sha256') != digest(ROOT/'backend/requirements-offline-lock.txt'):
                raise ValueError('wheelhouse Python/lock mismatch; rebuild on the target Linux platform')
            if args.action == 'verify-wheels':
                if platform.system() != 'Linux' or wheels.get('machine') != platform.machine():
                    raise ValueError('wheelhouse requires its recorded Linux architecture')
                print(f"Verified {len(wheels['files'])} wheels; pip will also check platform tags")
                return
        if args.action == 'bundle':
            names = list(data['files']) + ['release_manifest.json']
            if not args.without_wheels:
                names += ['wheels/'+name for name in wheels['files']] + ['wheels/manifest.json']
            args.output.parent.mkdir(parents=True, exist_ok=True)
            if args.output.exists():
                raise ValueError('output already exists; use a new --output path')
            with tarfile.open(args.output, 'w:gz') as archive:
                for name in sorted(names):
                    info = archive.gettarinfo(str(ROOT/name), arcname='bitcoin-offline/'+name)
                    info.uid = info.gid = 0
                    info.uname = info.gname = ''
                    info.mtime = 0
                    info.mode = 0o755 if name.endswith('.sh') else 0o644
                    with (ROOT/name).open('rb') as stream:
                        archive.addfile(info, stream)
            print(f'{args.output}: {digest(args.output)}')
            if args.without_wheels:
                print('PREPARATION ONLY: Linux wheelhouse still required before offline installation')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        sys.exit(f'Release error: {error}')
