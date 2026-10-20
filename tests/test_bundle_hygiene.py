import re
import subprocess
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FUNCTIONS_DIR = _REPO_ROOT / "functions"

# Matches `import strands` / `from strands import ...` / `from strands.x import`
# but NOT the Lambda runtime dependency `strands_decider`.
_STRANDS_AGENTS_IMPORT = re.compile(
    r"^\s*(?:import\s+strands\b(?!_)|from\s+strands\b(?!_))",
    re.MULTILINE,
)
_HF_TOKEN_LITERAL = re.compile(r"hf_[A-Za-z0-9]{8,}")


class BundleHygieneTests(unittest.TestCase):
    def test_functions_do_not_import_strands_agents_package(self):
        offenders = []
        for path in _FUNCTIONS_DIR.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if _STRANDS_AGENTS_IMPORT.search(text):
                offenders.append(str(path.relative_to(_REPO_ROOT)))
        self.assertEqual(
            offenders,
            [],
            f"strands-agents must stay out of functions/: {offenders}",
        )

    def test_no_hf_token_literal_in_tracked_source(self):
        tracked = subprocess.run(
            ["git", "ls-files"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()

        offenders = []
        for rel_path in tracked:
            if rel_path == "uv.lock" or rel_path.startswith(".agents/"):
                continue
            path = _REPO_ROOT / rel_path
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for match in _HF_TOKEN_LITERAL.finditer(text):
                token = match.group(0)
                # Allow the Hugging Face package names that legitimately start hf_.
                if token.startswith(("hf_xet", "hf_hub")):
                    continue
                offenders.append(f"{rel_path}: {token}")
        self.assertEqual(offenders, [], f"hf_ token literal found: {offenders}")


if __name__ == "__main__":
    unittest.main()
