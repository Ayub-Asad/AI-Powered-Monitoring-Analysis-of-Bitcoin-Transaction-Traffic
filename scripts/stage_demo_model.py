"""Verify/stage an existing trusted model; never generate or train artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def verify(directory):
    expected = json.loads((ROOT/'deploy/model_checksums.json').read_text())
    for name, digest in expected.items():
        path = directory/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Missing or changed frozen artifact: {name}. Stage trusted tuned-42 files; do not retrain.')
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, default=ROOT/'artifacts/ml/tuning/run-001/tuned-42')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    expected = verify(args.model_dir)
    if not args.verify_only:
        target = ROOT/'.container-model'
        target.mkdir(exist_ok=True)
        for name in expected:
            shutil.copyfile(args.model_dir/name, target/name)
        verify(target)
    print('Verified frozen tuned-42 model, manifest and threshold')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        sys.exit(str(error))
