"""Command-line ingestion:  python -m app.ingestion path/to/file.csv [--json] [--format csv]"""
import argparse
import json
import logging
import sys

from . import ingest_file


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ingestion", description="Validate/ingest a transaction file")
    parser.add_argument("path")
    parser.add_argument("--format", help="override format detection (csv|json|jsonl)")
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    parser.add_argument("-v", "--verbose", action="store_true", help="log per-row rejections")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    result = ingest_file(args.path, fmt=args.format)
    report = result.report.to_dict()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        s = report["summary"]
        print(f"{report['status'].upper()}  {report['filename']} ({report['format']})")
        print(f"  received={s['rows_received']} valid={s['valid_rows']} rejected={s['rejected_rows']} duplicates={s['duplicate_rows']}")
        for fe in report["file_errors"]:
            print(f"  FILE ERROR [{fe['code']}] {fe['message']}")
        for code, n in report["error_summary"]["by_code"].items():
            print(f"  error   {code}: {n}")
        for code, w in report["warnings"].items():
            print(f"  warning {code}: {w['count']}")
    return 0 if report["status"] != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
