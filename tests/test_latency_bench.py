"""Tests du banc de latence (bench/latency.py).

On vérifie que la logique de statistiques (p50/p95) tourne contre un Decider /
une réponse simulés, que le seuil des 29 s déclenche un code de sortie non nul,
et que le banc saute proprement lorsque l'endpoint/l'environnement est absent.
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "bench"))

import latency


class LatencyStatsTests(unittest.TestCase):
    def test_summarize_reports_p50_and_p95(self):
        samples = [100.0, 200.0, 300.0, 400.0, 500.0]
        stats = latency.summarize(samples)

        self.assertEqual(stats["count"], 5)
        self.assertEqual(stats["min"], 100.0)
        self.assertEqual(stats["p50"], 300.0)
        # p95 interpolé entre 400 et 500.
        self.assertAlmostEqual(stats["p95"], 480.0)

    def test_percentile_single_sample(self):
        self.assertEqual(latency.percentile([42.0], 0.95), 42.0)

    def test_run_once_reads_server_elapsed_ms_from_mocked_decider(self):
        # Decider / réponse /query simulés : on vérifie que run_once relève la
        # mesure serveur debug.elapsed_ms et une durée horloge positive.
        calls = []

        def fake_post_json(url, payload, **_kwargs):
            calls.append((url, payload))
            if url.endswith("/uploads"):
                return {
                    "upload_url": "https://s3.example/upload",
                    "fields": {"key": "requests/x.png"},
                    "s3_key": "requests/x.png",
                    "content_type": "image/png",
                }
            return {"mode": payload["mode"], "cards": [], "debug": {"elapsed_ms": 1234}}

        def fake_upload(_authorization, _image_path, **_kwargs):
            return None

        wall_ms, server_ms = latency.run_once(
            "https://api.example",
            Path("sample.png"),
            "situation",
            "image/png",
            post_json=fake_post_json,
            upload=fake_upload,
        )

        self.assertGreaterEqual(wall_ms, 0.0)
        self.assertEqual(server_ms, 1234.0)
        self.assertTrue(any(url.endswith("/uploads") for url, _ in calls))
        self.assertTrue(any(url.endswith("/query") for url, _ in calls))

    def test_format_table_prints_p50_p95_and_nova_baseline(self):
        stats_by_mode = {
            "exam": latency.summarize([100.0, 200.0, 300.0]),
            "situation": latency.summarize([150.0, 250.0, 350.0]),
        }
        table = latency.format_table(stats_by_mode)

        self.assertIn("p50", table)
        self.assertIn("p95", table)
        self.assertIn(latency.NOVA_BASELINE_LABEL, table)
        self.assertIn("exam", table)
        self.assertIn("situation", table)

    def test_main_skips_cleanly_when_endpoint_absent(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = latency.main([])

        self.assertEqual(exit_code, 0)
        self.assertIn("ignoré", buffer.getvalue())

    def test_main_skips_cleanly_when_image_missing(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = latency.main(
                ["--api", "https://api.example", "--image", "does-not-exist.png"]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("ignoré", buffer.getvalue())

    def test_main_exits_non_zero_when_p95_reaches_cap(self):
        # run_once simulé renvoyant une latence au-dessus du plafond 29 s.
        def fake_run_once(*_args, **_kwargs):
            return float(latency.API_GATEWAY_TIMEOUT_MS + 500), 1234.0

        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "sample.png"
            image.write_bytes(b"\x89PNG\r\n")
            buffer = io.StringIO()
            with (
                patch.object(latency, "run_once", side_effect=fake_run_once),
                redirect_stdout(buffer),
            ):
                exit_code = latency.main(
                    ["--api", "https://api.example", "--image", str(image), "--runs", "3"]
                )

        self.assertEqual(exit_code, 1)
        output = buffer.getvalue()
        self.assertIn("ÉCHEC", output)

    def test_main_exits_zero_when_p95_under_cap(self):
        def fake_run_once(*_args, **_kwargs):
            return 1500.0, 900.0

        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "sample.png"
            image.write_bytes(b"\x89PNG\r\n")
            buffer = io.StringIO()
            with (
                patch.object(latency, "run_once", side_effect=fake_run_once),
                redirect_stdout(buffer),
            ):
                exit_code = latency.main(
                    ["--api", "https://api.example", "--image", str(image), "--runs", "3"]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("OK", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
