"""Status-code / response-shape tests for the transport-independent upload handler."""
import json
import unittest

from app.ingestion import Code
from app.service import process_upload

from .helpers import make_row, to_csv


class TestProcessUpload(unittest.TestCase):
    def test_200_success_shape(self):
        status, body = process_upload("d.csv", to_csv([make_row(1), make_row(2)]))
        self.assertEqual(status, 200)
        self.assertEqual(body["summary"], {"rows_received": 2, "valid_rows": 2, "rejected_rows": 0, "duplicate_rows": 0})
        for key in ("status", "schema", "validation_errors", "error_summary", "duplicates", "warnings", "file_errors"):
            self.assertIn(key, body)
        json.dumps(body)

    def test_200_partial(self):
        status, body = process_upload("d.csv", to_csv([make_row(1), make_row(2, src_ip="x"), make_row(1)]))
        self.assertEqual((status, body["status"]), (200, "partial"))
        self.assertEqual(body["summary"], {"rows_received": 3, "valid_rows": 1, "rejected_rows": 1, "duplicate_rows": 1})

    def test_422_missing_columns_still_reports_schema(self):
        status, body = process_upload("d.csv", b"a,b\n1,2\n")
        self.assertEqual((status, body["status"]), (422, "failed"))
        self.assertEqual(body["file_errors"][0]["code"], Code.MISSING_REQUIRED_COLUMNS)
        self.assertEqual(body["schema"]["detected_columns"], ["a", "b"])

    def test_422_when_every_row_invalid(self):
        status, _ = process_upload("d.csv", to_csv([make_row(1, src_ip="x")]))
        self.assertEqual(status, 422)

    def test_415_unsupported(self):
        self.assertEqual(process_upload("d.xlsx", b"x")[0], 415)

    def test_413_too_large(self):
        status, body = process_upload("d.csv", b"x" * 100, max_bytes=10)
        self.assertEqual((status, body["file_errors"][0]["code"]), (413, Code.FILE_TOO_LARGE))


if __name__ == "__main__":
    unittest.main()
