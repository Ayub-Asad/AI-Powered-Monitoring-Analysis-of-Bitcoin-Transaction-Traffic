import json
import unittest
import numpy as np
import pandas as pd
from app.ingestion import ingest_bytes
from app.ingestion.pipeline import build_transactions_frame
from app.features import extract_features, FeatureConfig, ml_ready_frame
from app.features.schema import TRANSACTION_ML_FEATURES, WALLET_ML_FEATURES
from .helpers import make_row, BECH32 as A, BASE58 as B, P2SH as C


def records():
    return [make_row(1, timestamp="2025-01-01T00:00:00Z", input_addresses=[A,A], input_amounts=[.4,.2],
                     output_addresses=[B,B,A], output_amounts=[.3,.1,.1], num_inputs=2, num_outputs=3, amount_btc=.5, fee_btc=.1),
            make_row(2, timestamp="2025-01-01T00:00:30Z", input_addresses=[B], input_amounts=[.4],
                     output_addresses=[A,C], output_amounts=[.25,.1], num_inputs=1, num_outputs=2, amount_btc=.35, fee_btc=.05),
            make_row(3, timestamp="2025-01-01T00:01:00Z", input_addresses=[A], input_amounts=[.1],
                     output_addresses=[C], output_amounts=[.1], num_inputs=1, num_outputs=1, amount_btc=.1, fee_btc=0)]


def canonical(rows):
    result = ingest_bytes(json.dumps(rows).encode(), "x.json")
    assert result.report.rejected_rows == 0, result.report.errors
    return result.transactions


class TestFeatures(unittest.TestCase):
    def setUp(self):
        self.frame = canonical(records())
        self.tables = extract_features(self.frame)

    def test_transaction_definitions(self):
        row = self.tables.transaction_features.iloc[0]
        self.assertAlmostEqual(row.fee_to_amount_ratio, .2)
        self.assertAlmostEqual(row.input_output_count_ratio, 2/3)
        self.assertEqual((row.hour_of_day_utc, row.day_of_week_utc, row.is_night_utc), (0, 2, 1))

    def test_exact_flows_and_repeated_entries(self):
        wallets = self.tables.wallet_features.set_index("wallet_address")
        a, b, c = wallets.loc[A], wallets.loc[B], wallets.loc[C]
        self.assertEqual((a.transaction_count, a.incoming_transaction_count, a.outgoing_transaction_count), (3, 2, 2))
        self.assertAlmostEqual(a.total_sent_btc, .7)
        self.assertAlmostEqual(a.total_received_btc, .35)
        self.assertEqual((b.transaction_count, b.incoming_transaction_count, b.outgoing_transaction_count), (2, 1, 1))
        self.assertAlmostEqual(b.total_received_btc, .4)
        self.assertAlmostEqual(b.total_sent_btc, .4)
        self.assertAlmostEqual(c.total_received_btc, .2)
        self.assertEqual(c.total_sent_btc, 0)
        self.assertEqual((a.unique_counterparties, a.fan_in, a.fan_out), (2, 1, 2))

    def test_statistics_and_burst_boundaries(self):
        a = self.tables.wallet_features.set_index("wallet_address").loc[A]
        self.assertAlmostEqual(a.average_transaction_amount, np.mean([.5,.35,.1]))
        self.assertEqual(a.median_transaction_amount, .35)
        self.assertAlmostEqual(a.transaction_amount_std, np.std([.5,.35,.1], ddof=0))
        self.assertEqual((a.min_transaction_amount,a.max_transaction_amount), (.1,.5))
        self.assertEqual((a.active_duration_seconds,a.mean_inter_transaction_seconds,a.median_inter_transaction_seconds), (60,30,30))
        self.assertEqual(a.max_tx_in_60s, 3)
        other = extract_features(self.frame, FeatureConfig(30)).wallet_features.set_index("wallet_address").loc[A]
        self.assertEqual((other.max_tx_in_60s, other.max_tx_in_window), (3,2))
        rows = records()
        rows[2]["timestamp"] = "2025-01-01T00:01:00.000001Z"
        a = extract_features(canonical(rows)).wallet_features.set_index("wallet_address").loc[A]
        self.assertEqual(a.max_tx_in_60s, 2)

    def test_tied_times_and_singleton(self):
        rows = records()
        for row in rows:
            row["timestamp"] = "2025-01-01T00:00:00Z"
        a = extract_features(canonical(rows)).wallet_features.set_index("wallet_address").loc[A]
        self.assertEqual((a.active_duration_seconds,a.mean_inter_transaction_seconds,a.max_tx_in_60s), (0,0,3))
        single = extract_features(canonical(rows[:1])).wallet_features
        self.assertTrue((single.transaction_amount_std == 0).all())
        self.assertTrue((single.mean_inter_transaction_seconds == 0).all())
        self.assertTrue((single.max_tx_in_60s == 1).all())

    def test_legacy_mixed_availability_is_directional(self):
        rows = records()
        del rows[2]["input_amounts"]
        del rows[2]["output_amounts"]
        tables = extract_features(canonical(rows))
        w = tables.wallet_features.set_index("wallet_address")
        self.assertTrue(pd.isna(w.loc[A].total_sent_btc))
        self.assertFalse(w.loc[A].outgoing_amounts_available)
        self.assertEqual(w.loc[A].total_received_btc, .35)
        self.assertTrue(pd.isna(w.loc[C].total_received_btc))
        self.assertEqual(w.loc[C].total_sent_btc, 0)
        self.assertEqual(w.loc[B].total_sent_btc, .4)
        with self.assertRaises(ValueError):
            ml_ready_frame(tables.wallet_features, "wallet")

    def test_original_canonical_without_new_columns(self):
        frame = self.frame.drop(columns=["input_amounts", "output_amounts"])
        wallet = extract_features(frame).wallet_features
        self.assertTrue(wallet.loc[wallet.outgoing_transaction_count > 0, "total_sent_btc"].isna().all())

    def test_duplicate_observations(self):
        r = ingest_bytes(json.dumps(records()+[records()[0]]).encode(), "x.json")
        self.assertEqual(r.report.duplicate_rows, 1)
        pd.testing.assert_frame_equal(extract_features(r.transactions).wallet_features, self.tables.wallet_features)
        with self.assertRaises(ValueError):
            extract_features(pd.concat([self.frame,self.frame.iloc[:1]]))

    def test_order_determinism(self):
        tables = extract_features(self.frame.sample(frac=1, random_state=10))
        for name in ["transaction_features", "wallet_features", "wallet_context", "transaction_context"]:
            pd.testing.assert_frame_equal(getattr(tables,name), getattr(self.tables,name))

    def test_leakage_guards_and_label_independence(self):
        for field in ["label", "anomaly_type", "ground_truth", "scenario_id", "actor_id"]:
            with self.assertRaises(ValueError):
                extract_features(self.frame.assign(**{field: "secret"}))
        rows = records()
        for row in rows:
            row.update(label="anomalous", anomaly_type="any")
        other = extract_features(canonical(rows))
        pd.testing.assert_frame_equal(self.tables.wallet_features, other.wallet_features)
        pd.testing.assert_frame_equal(self.tables.transaction_features, other.transaction_features)
        for kind, table, expected in [("transaction",other.transaction_features,TRANSACTION_ML_FEATURES),
                                       ("wallet",other.wallet_features,WALLET_ML_FEATURES)]:
            matrix = ml_ready_frame(table,kind)
            self.assertEqual(tuple(matrix), expected)
            self.assertTrue(np.isfinite(matrix.to_numpy()).all())
            self.assertFalse({"txid","wallet_address","src_ip","country","asn"} & set(matrix))

    def test_one_satoshi_and_zero_fee(self):
        row = make_row(input_addresses=[A], output_addresses=[B,C], num_inputs=1, num_outputs=2,
                       amount_btc=1e-8, fee_btc=0, input_amounts=[1e-8], output_amounts=[0,1e-8])
        tables = extract_features(canonical([row]))
        self.assertEqual(tables.transaction_features.iloc[0].fee_to_amount_ratio, 0)
        self.assertTrue(np.isfinite(ml_ready_frame(tables.wallet_features,"wallet")).all().all())

    def test_legacy_zero_count_ratio_unavailable(self):
        tables = extract_features(canonical([make_row(num_outputs=0)]))
        self.assertTrue(pd.isna(tables.transaction_features.iloc[0].input_output_count_ratio))
        self.assertFalse(np.isinf(tables.transaction_features.select_dtypes(include="number")).any().any())

    def test_empty_input_and_bad_config(self):
        tables = extract_features(build_transactions_frame([]))
        self.assertEqual(tables.transaction_features.shape, (0,11))
        self.assertEqual(tables.wallet_features.shape, (0,21))
        for value in [0,-1,float("inf"),float("nan"),True]:
            with self.assertRaises(ValueError):
                FeatureConfig(value)
