"""Shared builders for ingestion tests."""
import csv
import io
import json
from typing import Dict, List, Optional

BECH32 = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
BASE58 = "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"
P2SH = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"

COLUMNS = [
    "timestamp", "src_ip", "dst_ip", "src_port", "dst_port", "txid",
    "input_addresses", "output_addresses", "num_inputs", "num_outputs",
    "amount_btc", "fee_btc", "fee_rate_sat_vb", "country", "asn", "asn_org",
    "label", "anomaly_type",
]


def tx(n: int) -> str:
    return f"{n:064x}"


def make_row(n: int = 1, **overrides) -> Dict[str, object]:
    row = {
        "timestamp": f"2025-01-01T00:00:{n % 60:02d}Z",
        "src_ip": "8.8.8.8",
        "dst_ip": "1.1.1.1",
        "src_port": "50000",
        "dst_port": "8333",
        "txid": tx(n),
        "input_addresses": BECH32,
        "output_addresses": f"{BASE58}|{P2SH}",
        "num_inputs": "1",
        "num_outputs": "2",
        "amount_btc": "0.5",
        "fee_btc": "0.0001",
        "fee_rate_sat_vb": "20.5",
        "country": "US",
        "asn": "15169",
        "asn_org": "GOOGLE",
        "label": "normal",
        "anomaly_type": "",
    }
    row.update(overrides)
    return row


def to_csv(rows: List[dict], columns: Optional[List[str]] = None) -> bytes:
    columns = columns or COLUMNS
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for r in rows:
        writer.writerow(["" if r.get(c) is None else r.get(c, "") for c in columns])
    return buf.getvalue().encode("utf-8")


def to_jsonl(rows: List[dict]) -> bytes:
    return ("\n".join(json.dumps(r) for r in rows) + "\n").encode("utf-8")
