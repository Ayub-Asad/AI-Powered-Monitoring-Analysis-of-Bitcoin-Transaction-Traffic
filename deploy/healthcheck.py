"""Readiness check using only Python's standard library."""
import json
import os
import sys
from urllib.request import urlopen


def main():
    try:
        port = int(os.environ.get('PORT', '8000'))
        with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=4) as response:
            data = json.load(response)
        return 0 if data.get('status') == 'ok' and data.get('graph_status') == 'ready' else 1
    except Exception:
        return 1


if __name__ == '__main__':
    sys.exit(main())
