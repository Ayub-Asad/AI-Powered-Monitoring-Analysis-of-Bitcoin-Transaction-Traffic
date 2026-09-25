import csv
import hashlib
import io
import json
import sys
import tempfile
import unittest
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

import pandas as pd
from app.ingestion import ingest_bytes, ingest_file
from app.money import to_satoshis
from .helpers import make_row, BASE58

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.dataset_v2 import BitcoinDatasetV2Generator, budgets
from scripts.btc_synthetic_dataset_generator import BitcoinDatasetGenerator, write_csv, write_jsonl


def v2row(**changes):
    row = make_row(input_amounts=[0.5001], output_amounts=[0.2, 0.3])
    row.update(changes)
    return row


def ingest(row):
    return ingest_bytes(json.dumps([row]).encode(), "x.json")


class TestV2Validation(unittest.TestCase):
    def test_valid_and_ground_truth_isolation(self):
        result = ingest(v2row())
        self.assertEqual(result.report.valid_rows, 1)
        self.assertFalse({"label", "anomaly_type", "ground_truth", "actor_id", "scenario_id"} & set(result.transactions))

    def test_invalid_arrays_and_money(self):
        cases = [dict(input_amounts=None), dict(output_amounts=None), dict(input_amounts=[]),
                 dict(input_amounts=[0.5, 0.0001]), dict(output_amounts=[0.5]), dict(num_inputs=2),
                 dict(num_outputs="bad"), dict(output_amounts=[-0.2, 0.7]), dict(output_amounts=[True, 0.5]),
                 dict(output_amounts=["NaN", 0.5]), dict(input_amounts=[0.50010001]),
                 dict(amount_btc=0.4), dict(fee_btc="0.000100001"),
                 dict(input_addresses="|" + make_row()["input_addresses"]),
                 dict(output_amounts=[0.2, "0.300000001"]), dict(input_amounts="oops")]
        for change in cases:
            with self.subTest(change=change):
                self.assertEqual(ingest(v2row(**change)).report.rejected_rows, 1)

    def test_zero_and_one_satoshi(self):
        row = v2row(amount_btc=1e-8, fee_btc=0, input_amounts=[1e-8], output_amounts=[0, 1e-8])
        self.assertEqual(ingest(row).report.valid_rows, 1)
        row.update(amount_btc=0, input_amounts=[0], output_amounts=[0, 0])
        self.assertEqual(ingest(row).report.rejected_rows, 1)

    def test_repeated_addresses_not_dropped(self):
        row = v2row(output_addresses=[BASE58, BASE58])
        result = ingest(row)
        self.assertEqual(result.report.valid_rows, 1)
        self.assertEqual(result.transactions.iloc[0].output_amounts, [0.2, 0.3])

    def test_legacy_mismatch_remains_warning(self):
        result = ingest(make_row(num_inputs=9))
        self.assertEqual(result.report.valid_rows, 1)
        self.assertEqual(result.transactions.iloc[0].num_inputs, 9)
        self.assertIsNone(result.transactions.iloc[0].input_amounts)

    def test_allocations_participate_in_duplicate_detection(self):
        rows = [v2row(), v2row(), v2row(output_amounts=[0.1, 0.4])]
        r = ingest_bytes(json.dumps(rows).encode(), "x.json")
        self.assertEqual((r.report.valid_rows, r.report.duplicates_exact, r.report.duplicates_conflicting), (1, 1, 1))


class TestV2Generator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = BitcoinDatasetV2Generator(42)
        cls.records = cls.generator.generate()

    def test_exact_counts_and_txids(self):
        self.assertEqual(len(self.records), 18000)
        self.assertEqual(sum(r.label == "normal" for r in self.records), 15300)
        self.assertEqual(Counter(r.anomaly_type for r in self.records if r.anomaly_type), budgets(2700))
        self.assertEqual(list(budgets(2700).values()), [540, 405, 405, 405, 405, 270, 270])
        self.assertEqual(len({r.txid for r in self.records}), 18000)
        self.assertTrue(all(len(r.txid) == 64 and int(r.txid, 16) >= 0 for r in self.records))

    def test_seed42_determinism(self):
        other = BitcoinDatasetV2Generator(42)
        self.assertEqual(self.records, other.generate())
        self.assertEqual(self.generator.ground_truth, other.ground_truth)

    def test_accounting_and_lengths(self):
        for r in self.records:
            self.assertEqual(len(r.input_addresses), r.num_inputs)
            self.assertEqual(len(r.output_addresses), r.num_outputs)
            self.assertEqual(len(r.input_amounts), r.num_inputs)
            self.assertEqual(len(r.output_amounts), r.num_outputs)
            outs = sum(map(to_satoshis, r.output_amounts))
            self.assertEqual(outs, to_satoshis(r.amount_btc))
            self.assertEqual(sum(map(to_satoshis, r.input_amounts)), outs + to_satoshis(r.fee_btc))

    def test_complete_chains_and_pairs(self):
        groups = defaultdict(list)
        by_id = {r.txid: r for r in self.records}
        for row in self.generator.ground_truth:
            if row["anomaly_type"]:
                groups[row["scenario_id"]].append(by_id[row["txid"]])
        for rows in groups.values():
            rows.sort(key=lambda r: (r.timestamp, r.txid))
            kind = rows[0].anomaly_type
            if kind == "geo_velocity_impossible_travel":
                self.assertEqual(len(rows), 2)
                self.assertNotEqual(rows[0].country, rows[1].country)
                self.assertEqual(rows[0].input_addresses[0], rows[1].input_addresses[0])
            if kind in ("rapid_fire_layering", "peeling_chain"):
                self.assertGreaterEqual(len(rows), 2)
                for prev, curr in zip(rows, rows[1:]):
                    self.assertEqual(prev.output_addresses[-1], curr.input_addresses[0])
                    self.assertEqual(prev.output_amounts[-1], curr.input_amounts[0])
            if kind == "dust_attack":
                self.assertGreaterEqual(len(rows), 2)
                self.assertEqual(len({r.input_addresses[0] for r in rows}), 1)

    def test_network_mapping_and_context_overlap(self):
        contexts = defaultdict(set)
        for r in self.records:
            contexts[r.src_ip].add((r.country, r.asn, r.asn_org))
        self.assertTrue(all(len(v) == 1 for v in contexts.values()))
        normal = [r for r in self.records if r.label == "normal"]
        abnormal = [r for r in self.records if r.label == "anomalous"]
        for field in ("country", "asn", "dst_port"):
            self.assertTrue({getattr(r, field) for r in abnormal} <= {getattr(r, field) for r in normal})
        self.assertGreater(max(r.amount_btc for r in normal), 500)
        self.assertLess(min(r.fee_rate_sat_vb for r in normal), 1)
        self.assertGreater(max(r.fee_rate_sat_vb for r in normal), 2000)

    def test_formats_and_full_ingestion(self):
        with tempfile.TemporaryDirectory() as temp:
            csv_path, jsonl_path = Path(temp)/"x.csv", Path(temp)/"x.jsonl"
            write_csv(self.records, csv_path)
            write_jsonl(self.records, jsonl_path)
            a, b = ingest_file(csv_path), ingest_file(jsonl_path)
            self.assertEqual((a.report.valid_rows, a.report.rejected_rows, a.report.duplicate_rows), (18000, 0, 0))
            pd.testing.assert_frame_equal(a.transactions, b.transactions)
            pd.testing.assert_frame_equal(a.ground_truth, b.ground_truth)
            c = ingest_bytes(json.dumps([asdict(r) for r in self.records[:20]]).encode(), "x.json")
            self.assertEqual(c.report.valid_rows, 20)

    def test_small_and_empty_budgets(self):
        for total in (0, 1, 2, 7, 150):
            rows = BitcoinDatasetV2Generator(42).generate(0, total)
            self.assertEqual(len(rows), total)
        with self.assertRaises(ValueError):
            BitcoinDatasetV2Generator(42).generate(-1, 0)

    def test_original_dataset_unchanged_and_compatible(self):
        p = ROOT/"data/btc_synthetic_dataset.csv"
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), "d854ff1bccbdc40ed1989f31bf94fdbe976750e641be0ae27d322e697217bfad")
        r = ingest_file(p)
        self.assertEqual((r.report.valid_rows, r.report.rejected_rows), (8726, 0))
        self.assertTrue(r.transactions.input_amounts.isna().all())
