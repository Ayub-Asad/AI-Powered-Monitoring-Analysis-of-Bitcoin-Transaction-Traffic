"""Build the dependency-free static dashboard with a reproducible asset manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    source, target = ROOT / 'frontend/src', ROOT / 'frontend/dist'
    target.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in ('index.html', 'styles.css', 'app.js'):
        data = (source / name).read_bytes()
        (target / name).write_bytes(data)
        manifest[name] = hashlib.sha256(data).hexdigest()
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8', newline='\n')
    print('Built 3 local assets:', target)


if __name__ == '__main__':
    build()
