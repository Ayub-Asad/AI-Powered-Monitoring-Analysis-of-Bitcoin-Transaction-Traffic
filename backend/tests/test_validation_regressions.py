import json
import unittest
from app.ingestion import ingest_bytes
from .helpers import make_row


class TestValidationRegressions(unittest.TestCase):
    def test_negative_subsatoshi_fee_rejected(self):
        for fee in ["-0.000000001", "-1e-400"]:
            with self.subTest(fee=fee):
                result = ingest_bytes(json.dumps([make_row(fee_btc=fee)]).encode(), "x.json")
                self.assertEqual(result.report.rejected_rows, 1)

    def test_timestamp_overflow_reported(self):
        for value in [10**400, "0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-14:00"]:
            with self.subTest(value=value):
                result = ingest_bytes(json.dumps([make_row(timestamp=value)]).encode(), "x.json")
                self.assertEqual(result.report.rejected_rows, 1)
                self.assertEqual(result.report.errors[0].field, "timestamp")
