"""Acquisition integrity tests use no external network or customer records."""
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forecasting.acquire import SOURCES, acquire, download


class Response(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}
        self.url = "https://public.example/data"


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "raw.bin"
        self.url = "https://public.example/data"
        self.body = b"complete public dataset"
        self.digest = hashlib.sha256(self.body).hexdigest()

    def fetch(self, **kwargs):
        return download(self.url, self.path, expected_sha256=self.digest, expected_size=len(self.body), **kwargs)

    @patch("forecasting.acquire.urlopen")
    def test_hash_verified_download_and_retention(self, opener):
        opener.return_value = Response(self.body, headers={"Content-Length": str(len(self.body))})
        result = self.fetch()
        self.assertEqual(self.path.read_bytes(), self.body)
        self.assertEqual(result["sha256"], self.digest)
        self.assertEqual(self.fetch()["status"], "retained")
        self.assertEqual(opener.call_count, 1)

    @patch("forecasting.acquire.urlopen")
    def test_bad_hash_never_publishes_destination(self, opener):
        opener.return_value = Response(b"x" * len(self.body))
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.fetch()
        self.assertFalse(self.path.exists())
        self.assertTrue(self.path.with_suffix(".bin.part").exists())

    @patch("forecasting.acquire.urlopen")
    def test_existing_file_is_checked_before_use(self, opener):
        self.path.write_bytes(b"x" * len(self.body))
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.fetch()
        opener.assert_not_called()

    @patch("forecasting.acquire.urlopen")
    def test_confirmed_range_resumes(self, opener):
        self.path.with_suffix(".bin.part").write_bytes(self.body[:5])
        opener.return_value = Response(self.body[5:], status=206, headers={"Content-Range": f"bytes 5-{len(self.body)-1}/{len(self.body)}"})
        result = self.fetch()
        self.assertEqual(result["resumed_from"], 5)
        self.assertEqual(opener.call_args.args[0].get_header("Range"), "bytes=5-")
        self.assertEqual(self.path.read_bytes(), self.body)

    @patch("forecasting.acquire.urlopen")
    def test_server_ignoring_range_restarts(self, opener):
        self.path.with_suffix(".bin.part").write_bytes(self.body[:5])
        opener.return_value = Response(self.body, headers={"Content-Length": str(len(self.body))})
        result = self.fetch()
        self.assertEqual(result["resumed_from"], 0)
        self.assertEqual(self.path.read_bytes(), self.body)

    @patch("forecasting.acquire.urlopen")
    def test_unverified_snapshot_partial_always_restarts(self, opener):
        self.path.with_suffix(".bin.part").write_bytes(b"older")
        opener.return_value = Response(self.body)
        download(self.url, self.path)
        self.assertIsNone(opener.call_args.args[0].get_header("Range"))
        self.assertEqual(self.path.read_bytes(), self.body)

    @patch("forecasting.acquire.urlopen")
    def test_invalid_range_preserves_existing_partial(self, opener):
        partial = self.path.with_suffix(".bin.part")
        partial.write_bytes(self.body[:5])
        opener.return_value = Response(self.body[5:], status=206, headers={"Content-Range": "bytes 6-22/23"})
        with self.assertRaisesRegex(ValueError, "resume offset"):
            self.fetch()
        self.assertEqual(partial.read_bytes(), self.body[:5])

    @patch("forecasting.acquire.urlopen")
    def test_known_and_unknown_length_limits(self, opener):
        opener.return_value = Response(self.body, headers={"Content-Length": str(len(self.body))})
        with self.assertRaisesRegex(ValueError, "size limit"):
            self.fetch(max_bytes=3)
        opener.return_value = Response(self.body)
        with self.assertRaisesRegex(ValueError, "size limit"):
            download(self.url, self.path, max_bytes=3)
        self.assertFalse(self.path.exists())

    @patch("forecasting.acquire.urlopen")
    def test_truncated_body_not_published(self, opener):
        opener.return_value = Response(self.body[:5], headers={"Content-Length": str(len(self.body))})
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.fetch()
        self.assertFalse(self.path.exists())

    @patch("forecasting.acquire.urlopen")
    def test_complete_partial_recovered_without_download(self, opener):
        self.path.with_suffix(".bin.part").write_bytes(self.body)
        self.assertEqual(self.fetch()["status"], "recovered_verified_partial")
        self.assertEqual(self.path.read_bytes(), self.body)
        opener.assert_not_called()

    @patch("forecasting.acquire.urlopen")
    def test_non_https_rejected(self, opener):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            download("http://public.example/data", self.path)
        opener.assert_not_called()

    @patch("forecasting.acquire.urlopen")
    def test_snapshot_manifest_locks_first_download(self, opener):
        opener.return_value = Response(self.body)
        directory = Path(self.directory.name)
        with patch.dict(SOURCES["moneydata"], {"sha256": None, "bytes": None}):
            first = acquire("moneydata", directory)
            second = acquire("moneydata", directory)
        self.assertEqual(first, second)
        self.assertEqual(opener.call_count, 1)
        raw = directory / SOURCES["moneydata"]["filename"]
        raw.write_bytes(b"x" * len(self.body))
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            acquire("moneydata", directory)


if __name__ == "__main__":
    unittest.main()
