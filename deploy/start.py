"""Container launcher: one worker shares one frozen in-memory graph."""
import os
import sys


def port_value(value):
    if not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 65535:
        raise ValueError('PORT must be an integer between 1 and 65535')
    return str(int(value))


if __name__ == '__main__':
    try:
        port = port_value(os.environ.get('PORT', '8000'))
    except ValueError as error:
        sys.exit(str(error))
    print(f'Starting Bitcoin investigation on 0.0.0.0:{port}', flush=True)
    os.execv(sys.executable, [sys.executable, '-B', '-m', 'uvicorn', 'app.main:app',
             '--app-dir', 'backend', '--host', '0.0.0.0', '--port', port,
             '--workers', '1', '--limit-concurrency', '32', '--no-server-header'])
