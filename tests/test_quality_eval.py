"""Tests du banc de qualité (bench/quality_eval.py).

Un unique test déterministe et hors-ligne (aucun réseau, aucune lecture d'image)
couvre les trois assertions attendues par FEAT-003 :
1. ``main(['--mock','--no-emit-report'])`` renvoie 0 et le stdout contient le
   bandeau SYNTHÉTIQUES/ILLUSTRATIFS plus une ligne par image d'échantillon ;
2. ``main(['--mock','--emit-report', <tmp>])`` renvoie 0, écrit le fichier qui
   contient l'en-tête « | image | », le placeholder live et les 6 noms d'images ;
3. le rendu Markdown produit un tableau portant les colonnes par image.
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "bench"))

import quality_eval


class QualityEvalMockTests(unittest.TestCase):
    def test_mock_table_report_and_renderer(self):
        # (1) main --mock --no-emit-report : bandeau synthétique + 6 images.
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = quality_eval.main(["--mock", "--no-emit-report"])
        output = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("SYNTHÉTIQUES", output)
        self.assertIn("ILLUSTRATIFS", output)
        for image in quality_eval.SAMPLE_IMAGES:
            self.assertIn(image, output)

        # (2) main --mock --emit-report : fichier écrit, en-tête, placeholder, images.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "quality-eval.md"
            inner = io.StringIO()
            with redirect_stdout(inner):
                emit_code = quality_eval.main(["--mock", "--emit-report", str(target)])
            self.assertEqual(emit_code, 0)
            self.assertTrue(target.is_file())
            content = target.read_text(encoding="utf-8")
            self.assertIn("| image |", content)
            self.assertIn(quality_eval.LIVE_PLACEHOLDER, content)
            for image in quality_eval.SAMPLE_IMAGES:
                self.assertIn(image, content)

        # (3) rendu Markdown : colonnes par image présentes.
        records = [
            quality_eval._mock_record(image, "situation")
            for image in quality_eval.SAMPLE_IMAGES
        ]
        table = quality_eval.format_markdown_table(records)
        for column in ("image", "mode", "intentions", "scores", "#refs", "elapsed_ms"):
            self.assertIn(column, table)
        for image in quality_eval.SAMPLE_IMAGES:
            self.assertIn(image, table)


if __name__ == "__main__":
    unittest.main()
