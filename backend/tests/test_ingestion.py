import json
import sys
import unittest
from pathlib import Path

import pandas as pd

from app.ingestion import Code, ingest_bytes, readers
from app.ingestion.readers import BaseReader, RawRow, ReadResult, register_reader
from app.ingestion.schema import CANONICAL_NAMES, GROUND_TRUTH_NAMES

from .helpers import BASE58, BECH32, COLUMNS, P2SH, make_row, to_csv, to_jsonl, tx


def ingest_rows(rows, columns=None, name="t.csv"):
    return ingest_bytes(to_csv(rows, columns), name)


def codes(result):
    return [e.code for e in result.report.errors]


def fields(result):
    return [e.field for e in result.report.errors]


class AccountingMixin:
    def assertAccounting(self, report):
        self.assertEqual(
            report.rows_received, report.valid_rows + report.rejected_rows + report.duplicate_rows
        )


class TestValidData(unittest.TestCase, AccountingMixin):
    def test_valid_csv(self):
        r = ingest_rows([make_row(i) for i in range(1, 6)])
        rep = r.report
        self.assertEqual(rep.status, "success")
        self.assertEqual((rep.rows_received, rep.valid_rows, rep.rejected_rows, rep.duplicate_rows), (5, 5, 0, 0))
        self.assertAccounting(rep)
        self.assertEqual(len(r.transactions), 5)

    def test_canonical_types_and_normalisation(self):
        r = ingest_rows([make_row(1, timestamp="2025-01-01T10:00:00+02:00", txid=tx(1).upper(),
                                  src_ip=" 2001:0db8:0000:0000:0000:0000:0000:0001 ", src_port="8333.0")])
        df = r.transactions
        row = df.iloc[0]
        self.assertIsInstance(df["timestamp"].dtype, pd.DatetimeTZDtype)
        self.assertEqual(str(row["timestamp"]), "2025-01-01 08:00:00+00:00")  # offset converted to UTC
        self.assertEqual(row["txid"], tx(1))                                  # lowercased
        self.assertEqual(row["src_ip"], "2001:db8::1")                        # canonical IPv6
        self.assertEqual(row["src_port"], 8333)
        self.assertEqual(row["input_addresses"], [BECH32])
        self.assertEqual(row["output_addresses"], [BASE58, P2SH])             # pipe-string -> list, order kept
        self.assertEqual(list(df.columns), list(CANONICAL_NAMES) + ["source_row"])

    def test_output_is_chronological_with_stable_ties(self):
        rows = [make_row(1, timestamp="2025-01-01T00:00:30Z"),
                make_row(2, timestamp="2025-01-01T00:00:10Z"),
                make_row(3, timestamp="2025-01-01T00:00:10Z")]
        df = ingest_rows(rows).transactions
        self.assertEqual(list(df["source_row"]), [2, 3, 1])

    def test_amounts_rounded_to_satoshi(self):
        df = ingest_rows([make_row(1, amount_btc="1e-3", fee_btc="0.123456789")]).transactions
        self.assertEqual(df.iloc[0]["amount_btc"], 0.001)
        self.assertEqual(df.iloc[0]["fee_btc"], 0.12345679)


class TestGroundTruthIsolation(unittest.TestCase):
    def test_labels_never_in_transaction_table(self):
        r = ingest_rows([make_row(1), make_row(2, label="anomalous", anomaly_type="dust_attack")])
        for col in GROUND_TRUTH_NAMES:
            self.assertNotIn(col, r.transactions.columns)
        gt = r.ground_truth
        self.assertEqual(list(gt["txid"]), list(r.transactions["txid"]))
        self.assertEqual(list(gt["label"]), ["normal", "anomalous"])
        self.assertEqual(gt.iloc[1]["anomaly_type"], "dust_attack")
        self.assertTrue(pd.isna(gt.iloc[0]["anomaly_type"]))

    def test_no_ground_truth_columns_gives_none(self):
        cols = [c for c in COLUMNS if c not in GROUND_TRUTH_NAMES]
        r = ingest_rows([make_row(1)], columns=cols)
        self.assertIsNone(r.ground_truth)
        self.assertEqual(r.report.status, "success")

    def test_bad_label_is_warning_not_rejection(self):
        r = ingest_rows([make_row(1, label="suspicious")])
        self.assertEqual(r.report.valid_rows, 1)
        self.assertIn(Code.INVALID_OPTIONAL_VALUE, r.report.warning_counts)
        self.assertTrue(pd.isna(r.ground_truth.iloc[0]["label"]))


class TestFormats(unittest.TestCase):
    def setUp(self):
        self.rows = [make_row(i) for i in range(1, 4)]

    def test_csv_json_jsonl_are_equivalent(self):
        a = ingest_bytes(to_csv(self.rows), "d.csv")
        b = ingest_bytes(json.dumps(self.rows).encode(), "d.json")
        c = ingest_bytes(to_jsonl(self.rows), "d.jsonl")
        d = ingest_bytes(json.dumps({"transactions": self.rows}).encode(), "d.json")
        for res in (a, b, c, d):
            self.assertEqual(res.report.valid_rows, 3, res.report.file_errors)
            pd.testing.assert_frame_equal(a.transactions, res.transactions)

    def test_json_native_types_and_address_lists(self):
        row = make_row(1, src_port=8333, amount_btc=0.25, input_addresses=[BECH32], output_addresses=[BASE58])
        r = ingest_bytes(json.dumps([row]).encode(), "d.json")
        self.assertEqual(r.report.valid_rows, 1)
        self.assertEqual(r.transactions.iloc[0]["output_addresses"], [BASE58])

    def test_unsupported_extension(self):
        r = ingest_bytes(b"<x/>", "d.xml")
        self.assertEqual(r.report.file_errors[0].code, Code.UNSUPPORTED_FORMAT)
        self.assertEqual(r.report.status, "failed")

    def test_format_override(self):
        r = ingest_bytes(to_csv(self.rows), "upload.dat", fmt="csv")
        self.assertEqual(r.report.valid_rows, 3)

    def test_new_format_can_be_registered_without_touching_pipeline(self):
        class FakeXML(BaseReader):
            name, extensions = "xml", (".xml",)

            def read(self, text):
                return ReadResult(COLUMNS, [RawRow(1, make_row(1))])

        register_reader(FakeXML())
        try:
            r = ingest_bytes(b"<transactions/>", "d.xml")
            self.assertEqual((r.report.format, r.report.valid_rows), ("xml", 1))
        finally:
            readers._BY_NAME.pop("xml"); readers._BY_EXT.pop(".xml")

    def test_json_lines_content_in_json_file_gives_hint(self):
        r = ingest_bytes(to_jsonl(self.rows), "d.json")
        self.assertEqual(r.report.file_errors[0].code, Code.INVALID_JSON)
        self.assertIn("jsonl", r.report.file_errors[0].message)


class TestFileLevelFailures(unittest.TestCase):
    def test_missing_required_columns(self):
        cols = [c for c in COLUMNS if c not in ("txid", "amount_btc")]
        r = ingest_rows([make_row(1)], columns=cols)
        self.assertEqual(r.report.status, "failed")
        self.assertEqual(r.report.file_errors[0].code, Code.MISSING_REQUIRED_COLUMNS)
        msg = r.report.file_errors[0].message
        self.assertIn("txid", msg); self.assertIn("amount_btc", msg)
        self.assertEqual(r.report.schema["missing_required_columns"], ["txid", "amount_btc"])
        self.assertIn("src_ip", r.report.schema["detected_columns"])  # user still sees what was found
        self.assertEqual(len(r.transactions), 0)

    def test_missing_optional_columns_ok(self):
        cols = [c for c in COLUMNS if c not in ("country", "asn", "asn_org", "fee_rate_sat_vb", "num_inputs", "num_outputs")]
        r = ingest_rows([make_row(1)], columns=cols)
        self.assertEqual(r.report.valid_rows, 1)
        row = r.transactions.iloc[0]
        self.assertEqual((row["num_inputs"], row["num_outputs"]), (1, 2))  # derived from lists
        self.assertTrue(pd.isna(row["country"]) and pd.isna(row["asn"]) and pd.isna(row["fee_rate_sat_vb"]))
        self.assertIn("country", r.report.schema["missing_optional_columns"])

    def test_header_aliases_and_unknown_columns(self):
        cols = ["Time", "Source IP", "Dest-IP", "source_port", "destination_port", "Tx_ID",
                "input_addresses", "output_addresses", "amount", "fee_btc", "mystery"]
        row = make_row(1)
        row.update({"Time": row["timestamp"], "Source IP": row["src_ip"], "Dest-IP": row["dst_ip"],
                    "source_port": row["src_port"], "destination_port": row["dst_port"],
                    "Tx_ID": row["txid"], "amount": row["amount_btc"], "mystery": "x"})
        r = ingest_rows([row], columns=cols)
        self.assertEqual(r.report.valid_rows, 1, r.report.file_errors)
        self.assertEqual(r.report.schema["renamed_columns"]["Tx_ID"], "txid")
        self.assertEqual(r.report.schema["unrecognized_columns"], ["mystery"])

    def test_two_columns_for_same_field(self):
        r = ingest_bytes(to_csv([make_row(1)], COLUMNS + ["TxID"]), "d.csv")
        self.assertEqual(r.report.file_errors[0].code, Code.DUPLICATE_COLUMNS)

    def test_empty_and_header_only(self):
        self.assertEqual(ingest_bytes(b"", "d.csv").report.file_errors[0].code, Code.EMPTY_FILE)
        self.assertEqual(ingest_bytes(b"\n\n", "d.csv").report.file_errors[0].code, Code.EMPTY_FILE)
        self.assertEqual(ingest_bytes(to_csv([]), "d.csv").report.file_errors[0].code, Code.NO_DATA_ROWS)
        self.assertEqual(ingest_bytes(b"[]", "d.json").report.file_errors[0].code, Code.NO_DATA_ROWS)

    def test_invalid_json_and_structure(self):
        self.assertEqual(ingest_bytes(b"{not json", "d.json").report.file_errors[0].code, Code.INVALID_JSON)
        self.assertEqual(ingest_bytes(b'{"a": 1}', "d.json").report.file_errors[0].code, Code.INVALID_STRUCTURE)

    def test_undecodable_bytes(self):
        r = ingest_bytes(b"\xff\xfe\x00bad", "d.csv")
        self.assertEqual(r.report.file_errors[0].code, Code.UNDECODABLE_FILE)

    def test_utf8_bom_tolerated(self):
        r = ingest_bytes(b"\xef\xbb\xbf" + to_csv([make_row(1)]), "d.csv")
        self.assertEqual(r.report.valid_rows, 1)


class TestMalformedRecords(unittest.TestCase, AccountingMixin):
    def test_csv_wrong_field_count(self):
        good = to_csv([make_row(1), make_row(2)]).decode().splitlines()
        text = "\n".join([good[0], good[1], "only,three,fields", good[2] + ",extra"]) + "\n"
        r = ingest_bytes(text.encode(), "d.csv")
        self.assertEqual((r.report.valid_rows, r.report.rejected_rows), (1, 2))
        self.assertEqual(codes(r), [Code.MALFORMED_ROW, Code.MALFORMED_ROW])
        self.assertEqual([e.row for e in r.report.errors], [2, 3])
        self.assertAccounting(r.report)

    def test_jsonl_bad_lines(self):
        lines = [json.dumps(make_row(1)), "{broken", "[1, 2]", "", json.dumps(make_row(2))]
        r = ingest_bytes("\n".join(lines).encode(), "d.jsonl")
        self.assertEqual((r.report.rows_received, r.report.valid_rows, r.report.rejected_rows), (4, 2, 2))
        self.assertEqual(codes(r), [Code.MALFORMED_ROW] * 2)

    def test_json_array_with_non_object(self):
        r = ingest_bytes(json.dumps([make_row(1), "oops", 5]).encode(), "d.json")
        self.assertEqual((r.report.valid_rows, r.report.rejected_rows), (1, 2))

    def test_all_rows_bad_is_failed(self):
        r = ingest_rows([make_row(1, src_ip="nope"), make_row(2, src_ip="nope")])
        self.assertEqual((r.report.status, r.report.valid_rows, r.report.rejected_rows), ("failed", 0, 2))

    def test_multiple_errors_in_one_row_all_reported(self):
        r = ingest_rows([make_row(1, src_ip="999.1.1.1", dst_port="99999", amount_btc="abc")])
        self.assertEqual(sorted(fields(r)), ["amount_btc", "dst_port", "src_ip"])
        self.assertEqual(r.report.rejected_rows, 1)
        self.assertEqual(r.report.total_errors, 3)


class TestDuplicates(unittest.TestCase, AccountingMixin):
    def test_exact_duplicate(self):
        r = ingest_rows([make_row(1), make_row(2), make_row(1)])
        rep = r.report
        self.assertEqual((rep.valid_rows, rep.duplicate_rows, rep.duplicates_exact, rep.duplicates_conflicting), (2, 1, 1, 0))
        self.assertEqual(rep.status, "partial")
        self.assertEqual(rep.duplicate_samples[0], {"txid": tx(1), "row": 3, "first_seen_row": 1, "kind": "exact"})
        self.assertAccounting(rep)

    def test_conflicting_duplicate_keeps_first(self):
        r = ingest_rows([make_row(1, amount_btc="1.0"), make_row(1, amount_btc="9.0")])
        self.assertEqual((r.report.duplicate_rows, r.report.duplicates_conflicting), (1, 1))
        self.assertEqual(r.transactions.iloc[0]["amount_btc"], 1.0)

    def test_duplicate_detected_after_normalisation(self):
        r = ingest_rows([make_row(1), make_row(1, txid=" " + tx(1).upper() + " ")])
        self.assertEqual(r.report.duplicate_rows, 1)

    def test_txids_are_unique_in_output(self):
        r = ingest_rows([make_row(i % 3 + 1) for i in range(9)])
        self.assertTrue(r.transactions["txid"].is_unique)
        self.assertEqual(r.report.duplicate_rows, 6)

    def test_rejected_row_is_not_counted_as_duplicate(self):
        r = ingest_rows([make_row(1, src_ip="bad"), make_row(1)])
        self.assertEqual((r.report.rejected_rows, r.report.duplicate_rows, r.report.valid_rows), (1, 0, 1))


class TestTxid(unittest.TestCase):
    def test_invalid_txids(self):
        bad = ["abc", tx(1)[:-1], tx(1) + "0", "g" * 64, "0x" + tx(1)[2:], ""]
        r = ingest_rows([make_row(i + 1, txid=t) for i, t in enumerate(bad)])
        self.assertEqual(r.report.valid_rows, 0)
        self.assertEqual(set(codes(r)), {Code.INVALID_TXID, Code.MISSING_VALUE})


class TestIP(unittest.TestCase):
    def test_invalid_ips_rejected(self):
        for bad in ["999.1.1.1", "abc", "1.2.3", "1.2.3.4:8333", "010.1.1.1", "0.0.0.0", "224.0.0.1", "1.2.3.4/24"]:
            with self.subTest(ip=bad):
                r = ingest_rows([make_row(1, src_ip=bad)])
                self.assertEqual(r.report.rejected_rows, 1)
                self.assertEqual(r.report.errors[0].code, Code.INVALID_IP)
                self.assertEqual(r.report.errors[0].field, "src_ip")

    def test_dst_ip_validated_too(self):
        r = ingest_rows([make_row(1, dst_ip="nope")])
        self.assertEqual(fields(r), ["dst_ip"])

    def test_private_ip_kept_with_warning(self):
        r = ingest_rows([make_row(1, src_ip="192.168.1.5")])
        self.assertEqual(r.report.valid_rows, 1)
        self.assertEqual(r.report.warning_counts[Code.NON_PUBLIC_IP], 1)


class TestPorts(unittest.TestCase):
    def test_invalid_ports(self):
        for bad in ["0", "65536", "-1", "abc", "80.5", "8e3", "99999999"]:
            with self.subTest(port=bad):
                r = ingest_rows([make_row(1, src_port=bad)])
                self.assertEqual(r.report.rejected_rows, 1)
                self.assertEqual(r.report.errors[0].code, Code.INVALID_PORT)

    def test_valid_ports(self):
        for good in ["1", "22", "8333", "65535", "8333.0", " 443 "]:
            with self.subTest(port=good):
                self.assertEqual(ingest_rows([make_row(1, dst_port=good)]).report.valid_rows, 1)

    def test_json_bool_port_rejected(self):
        r = ingest_bytes(json.dumps([make_row(1, src_port=True)]).encode(), "d.json")
        self.assertEqual(r.report.errors[0].code, Code.INVALID_PORT)


class TestNumericFields(unittest.TestCase):
    def test_invalid_amounts(self):
        cases = {"abc": Code.INVALID_NUMBER, "1,5": Code.INVALID_NUMBER, "nan!": Code.INVALID_NUMBER,
                 "inf": Code.INVALID_NUMBER, "1e999": Code.INVALID_NUMBER, "1_000": Code.INVALID_NUMBER,
                 "-1": Code.OUT_OF_RANGE, "0": Code.OUT_OF_RANGE, "1e-10": Code.OUT_OF_RANGE,
                 "21000001": Code.OUT_OF_RANGE}
        for bad, code in cases.items():
            with self.subTest(amount=bad):
                r = ingest_rows([make_row(1, amount_btc=bad)])
                self.assertEqual((r.report.rejected_rows, r.report.errors[0].code, r.report.errors[0].field),
                                 (1, code, "amount_btc"))

    def test_invalid_fee(self):
        self.assertEqual(ingest_rows([make_row(1, fee_btc="-0.1")]).report.errors[0].code, Code.OUT_OF_RANGE)
        self.assertEqual(ingest_rows([make_row(1, fee_btc="free")]).report.errors[0].code, Code.INVALID_NUMBER)

    def test_zero_fee_allowed(self):
        self.assertEqual(ingest_rows([make_row(1, fee_btc="0")]).report.valid_rows, 1)

    def test_json_non_scalar_numeric(self):
        r = ingest_bytes(json.dumps([make_row(1, amount_btc=[1, 2])]).encode(), "d.json")
        self.assertEqual(r.report.errors[0].code, Code.INVALID_NUMBER)

    def test_bad_optional_numeric_is_nulled_with_warning(self):
        r = ingest_rows([make_row(1, fee_rate_sat_vb="fast", asn="AS-nope", country="USA")])
        self.assertEqual(r.report.valid_rows, 1)
        row = r.transactions.iloc[0]
        self.assertTrue(pd.isna(row["fee_rate_sat_vb"]) and pd.isna(row["asn"]) and pd.isna(row["country"]))
        self.assertEqual(r.report.warning_counts[Code.INVALID_OPTIONAL_VALUE], 3)


class TestTimestamps(unittest.TestCase):
    def test_accepted_forms(self):
        expected = "2025-01-01 00:00:00+00:00"
        for ts in ["2025-01-01T00:00:00Z", "2025-01-01 00:00:00", "2025-01-01T00:00:00+00:00",
                   "2024-12-31T19:00:00-05:00", "1735689600", 1735689600, "1735689600000"]:
            with self.subTest(ts=ts):
                r = ingest_rows([make_row(1, timestamp=ts)])
                self.assertEqual(r.report.valid_rows, 1, r.report.errors)
                self.assertEqual(str(r.transactions.iloc[0]["timestamp"]), expected)

    def test_naive_timestamp_warns(self):
        r = ingest_rows([make_row(1, timestamp="2025-01-01 00:00:00")])
        self.assertEqual(r.report.warning_counts[Code.NAIVE_TIMESTAMP_ASSUMED_UTC], 1)

    def test_rejected_forms(self):
        for ts in ["yesterday", "2025-13-45T00:00:00Z", "01/02/2025", "2008-12-31T00:00:00Z", "2999-01-01T00:00:00Z"]:
            with self.subTest(ts=ts):
                r = ingest_rows([make_row(1, timestamp=ts)])
                self.assertEqual(r.report.rejected_rows, 1)
                self.assertIn(r.report.errors[0].code, {Code.INVALID_TIMESTAMP, Code.OUT_OF_RANGE})


class TestAddresses(unittest.TestCase):
    def test_pipe_list_parsing_and_stray_pipes(self):
        r = ingest_rows([make_row(1, output_addresses=f" {BASE58} | {P2SH} |", num_outputs="2")])
        self.assertEqual(r.transactions.iloc[0]["output_addresses"], [BASE58, P2SH])
        self.assertNotIn(Code.COUNT_MISMATCH, r.report.warning_counts)

    def test_bech32_case_normalised(self):
        r = ingest_rows([make_row(1, input_addresses=BECH32.upper())])
        self.assertEqual(r.transactions.iloc[0]["input_addresses"], [BECH32])

    def test_invalid_address_rejected(self):
        for bad in ["notanaddress", f"{BECH32}|0xdeadbeef", "bc1qINVALID!", "1" + "l" * 33]:
            with self.subTest(addr=bad):
                r = ingest_rows([make_row(1, input_addresses=bad)])
                self.assertEqual(r.report.errors[0].code, Code.INVALID_ADDRESS)

    def test_empty_list_rejected(self):
        r = ingest_rows([make_row(1, output_addresses="|||")])
        self.assertEqual(r.report.errors[0].code, Code.EMPTY_ADDRESS_LIST)

    def test_repeated_address_kept_with_warning(self):
        r = ingest_rows([make_row(1, output_addresses=f"{BASE58}|{BASE58}")])
        self.assertEqual(r.transactions.iloc[0]["output_addresses"], [BASE58, BASE58])
        self.assertEqual(r.report.warning_counts[Code.DUPLICATE_ADDRESS_IN_LIST], 1)

    def test_count_mismatch_keeps_row_and_source_value(self):
        r = ingest_rows([make_row(1, num_inputs="3")])
        self.assertEqual(r.report.valid_rows, 1)
        self.assertEqual(r.transactions.iloc[0]["num_inputs"], 3)
        self.assertEqual(r.report.warning_counts[Code.COUNT_MISMATCH], 1)


class TestNulls(unittest.TestCase):
    def test_null_tokens_in_optional_fields(self):
        r = ingest_rows([make_row(1, country="N/A", asn="null", asn_org="None", fee_rate_sat_vb="NaN",
                                  num_inputs="", num_outputs="-")])
        self.assertEqual(r.report.valid_rows, 1)
        row = r.transactions.iloc[0]
        self.assertTrue(all(pd.isna(row[c]) for c in ("country", "asn", "asn_org", "fee_rate_sat_vb")))
        self.assertEqual((row["num_inputs"], row["num_outputs"]), (1, 2))
        self.assertEqual(r.report.warning_counts, {})

    def test_required_null_is_missing_value(self):
        for name in ("timestamp", "src_ip", "dst_port", "txid", "input_addresses", "amount_btc", "fee_btc"):
            with self.subTest(field=name):
                r = ingest_rows([make_row(1, **{name: "null"})])
                self.assertEqual((r.report.errors[0].code, r.report.errors[0].field), (Code.MISSING_VALUE, name))

    def test_json_null_and_absent_keys(self):
        row = make_row(1, country=None, asn=None)
        del row["fee_btc"]
        r = ingest_bytes(json.dumps([row, make_row(2, country=None)]).encode(), "d.json")
        self.assertEqual(r.report.valid_rows, 1)
        self.assertEqual((r.report.errors[0].code, r.report.errors[0].field, r.report.errors[0].row),
                         (Code.MISSING_VALUE, "fee_btc", 1))


class TestErrorReporting(unittest.TestCase):
    def test_error_list_capped_but_counts_complete(self):
        from app.ingestion import IngestionConfig
        rows = [make_row(i + 1, src_ip="bad") for i in range(30)] + [make_row(1000)]
        r = ingest_bytes(to_csv(rows), "d.csv", config=IngestionConfig(max_reported_errors=5))
        d = r.report.to_dict()
        self.assertEqual(len(d["validation_errors"]), 5)
        self.assertEqual(d["error_summary"]["total_errors"], 30)
        self.assertEqual(d["error_summary"]["by_code"], {Code.INVALID_IP: 30})
        self.assertTrue(d["error_summary"]["truncated"])

    def test_report_is_json_serialisable(self):
        rows = [make_row(1), make_row(1), make_row(2, src_ip="x"), make_row(3, output_addresses=f"{BASE58}|{BASE58}")]
        json.dumps(ingest_rows(rows).report.to_dict())

    def test_row_numbers_are_one_based_record_numbers(self):
        r = ingest_rows([make_row(1), make_row(2), make_row(3, src_ip="bad")])
        self.assertEqual(r.report.errors[0].row, 3)


# --------------------------------------------------------------------------
# Integration against the real dataset generator (skipped if not in the repo)
# --------------------------------------------------------------------------
GEN = Path(__file__).resolve().parents[2] / "btc_synthetic_dataset_generator.py"


@unittest.skipUnless(GEN.exists(), "dataset generator not found next to backend/")
class TestGeneratorDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        import tempfile
        spec = importlib.util.spec_from_file_location("btc_gen", GEN)
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        recs = gen.BitcoinDatasetGenerator(seed=7).generate(n_normal=600, n_anomalous=120)
        cls.n = len(recs)
        cls.n_anom = sum(r.label == "anomalous" for r in recs)
        with tempfile.TemporaryDirectory() as d:
            gen.write_csv(recs, f"{d}/x.csv"); gen.write_jsonl(recs, f"{d}/x.jsonl")
            cls.csv = ingest_bytes(Path(f"{d}/x.csv").read_bytes(), "x.csv")
            cls.jsonl = ingest_bytes(Path(f"{d}/x.jsonl").read_bytes(), "x.jsonl")

    def test_all_rows_accepted(self):
        for res in (self.csv, self.jsonl):
            self.assertEqual((res.report.status, res.report.valid_rows, res.report.rejected_rows), ("success", self.n, 0))

    def test_csv_and_jsonl_agree(self):
        pd.testing.assert_frame_equal(self.csv.transactions, self.jsonl.transactions)

    def test_ground_truth_preserved_but_isolated(self):
        gt = self.csv.ground_truth
        self.assertEqual((gt["label"] == "anomalous").sum(), self.n_anom)
        self.assertFalse({"label", "anomaly_type"} & set(self.csv.transactions.columns))

    def test_generator_no_longer_produces_count_mismatches(self):
        # Regression guard for the 2026-09 generator fix: num_inputs/num_outputs
        # must always match the actual address-list length (was: independent
        # random draws in high_value_single_hop, hardcoded 1s in anomalous_port).
        self.assertNotIn(Code.COUNT_MISMATCH, self.csv.report.warning_counts)
        il = self.csv.transactions["input_addresses"].map(len)
        ol = self.csv.transactions["output_addresses"].map(len)
        self.assertTrue((il == self.csv.transactions["num_inputs"]).all())
        self.assertTrue((ol == self.csv.transactions["num_outputs"]).all())

    def test_peeling_chain_outputs_are_distinct_addresses(self):
        # Regression guard: peeling_chain used to emit "addr|addr" (same
        # address twice), which would create degenerate self-loops downstream
        # in graph construction. Now: distinct peel-target and change addresses.
        merged = self.csv.transactions.merge(self.csv.ground_truth, on="txid")
        peel = merged[merged["anomaly_type"] == "peeling_chain"]
        self.assertGreater(len(peel), 0)
        has_dupe = peel["output_addresses"].map(lambda lst: len(lst) != len(set(lst)))
        self.assertFalse(has_dupe.any())

    def test_fee_rate_consistent_with_fee_btc_for_every_anomaly_type(self):
        # Regression guard: fee_rate_sat_vb must be derived from fee_btc (not an
        # independent random draw), or a downstream model could trivially learn
        # "fee_rate/fee_btc ratio realistic => normal" as a shortcut that has
        # nothing to do with genuine anomalous behaviour.
        merged = self.csv.transactions.merge(self.csv.ground_truth, on="txid")
        implied_vbytes = merged["fee_btc"] * 1e8 / merged["fee_rate_sat_vb"]
        # A real transaction's vsize is on the order of ~150-400 vB for the
        # input/output counts this generator produces; anything wildly outside
        # that band indicates fee_btc and fee_rate_sat_vb were drawn independently.
        self.assertTrue(implied_vbytes.between(100, 500).all(), implied_vbytes.describe())

    def test_only_incidental_address_reuse_remains(self):
        # Some DUPLICATE_ADDRESS_IN_LIST warnings are expected (an address pool
        # can coincidentally supply the same address twice); this should now be
        # rare incidental reuse, not the guaranteed peeling_chain duplication.
        n = self.csv.report.warning_counts.get(Code.DUPLICATE_ADDRESS_IN_LIST, 0)
        self.assertLess(n, 0.01 * self.n)


if __name__ == "__main__":
    unittest.main()
