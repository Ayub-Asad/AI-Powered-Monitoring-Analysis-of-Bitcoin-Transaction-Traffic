"""HTTP-level tests. Skipped automatically if fastapi/httpx aren't installed."""
import unittest

try:
    from fastapi.testclient import TestClient
    from app.main import app
    HAVE_FASTAPI = True
except Exception:  # pragma: no cover
    HAVE_FASTAPI = False

from .helpers import make_row, to_csv


@unittest.skipUnless(HAVE_FASTAPI, "fastapi/httpx/python-multipart not installed")
class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_ingest_csv(self):
        r = self.client.post("/ingest", files={"file": ("d.csv", to_csv([make_row(1), make_row(2)]), "text/csv")})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["summary"]["valid_rows"], 2)

    def test_ingest_format_override(self):
        r = self.client.post("/ingest?format=csv", files={"file": ("d.dat", to_csv([make_row(1)]))})
        self.assertEqual(r.status_code, 200)

    def test_ingest_unsupported(self):
        r = self.client.post("/ingest", files={"file": ("d.xlsx", b"x")})
        self.assertEqual(r.status_code, 415)

    def test_v2_jsonl_and_invalid_conservation(self):
        import json
        from .test_dataset_v2 import v2row
        valid = json.dumps(v2row()).encode()
        r = self.client.post("/ingest", files={"file": ("v2.jsonl", valid)})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["summary"]["valid_rows"], 1)
        invalid = json.dumps(v2row(input_amounts=[0.4])).encode()
        r = self.client.post("/ingest", files={"file": ("v2.jsonl", invalid)})
        self.assertEqual(r.status_code, 422)

    def test_ingest_missing_file_field(self):
        self.assertEqual(self.client.post("/ingest").status_code, 422)


if __name__ == "__main__":
    unittest.main()
