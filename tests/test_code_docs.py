import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE_DOCS = ROOT / "scripts" / "code_docs.py"


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)


class CodeDocsTests(unittest.TestCase):
    def make_repo(self, tmp_root: Path) -> Path:
        repo = tmp_root / "demo"
        repo.mkdir()
        (repo / "package.json").write_text('{"scripts":{"test":"echo ok"}}\n')
        (repo / "src").mkdir()
        (repo / "src" / "routes.ts").write_text("export const routes = ['/health'];\n")
        (repo / "Dockerfile").write_text("FROM node:22-alpine\n")
        run(["git", "init"], repo)
        run(["git", "config", "user.email", "test@example.com"], repo)
        run(["git", "config", "user.name", "Test User"], repo)
        run(["git", "add", "."], repo)
        run(["git", "commit", "-m", "initial"], repo)
        return repo

    def test_generate_creates_docs_and_diagrams(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            run([sys.executable, str(CODE_DOCS), "generate", str(repo)], ROOT)

            self.assertTrue((repo / "docs" / "README.md").exists())
            self.assertTrue((repo / "docs" / "architecture.md").exists())
            self.assertTrue((repo / "docs" / "interfaces.md").exists())
            self.assertTrue((repo / "docs" / "operations.md").exists())
            self.assertTrue((repo / "docs" / "diagrams" / "context.mmd").exists())
            self.assertTrue((repo / "docs" / "diagrams" / "critical-sequence.mmd").exists())

            inventory = json.loads((repo / "docs" / "generated" / "code-doc-inventory.json").read_text())
            self.assertEqual(inventory["counts"]["manifests"], 2)
            self.assertGreaterEqual(inventory["counts"]["interfaces"], 1)
            self.assertGreaterEqual(inventory["counts"]["deployments"], 1)

    def test_check_fails_when_generated_docs_are_not_committed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            result = subprocess.run(
                [sys.executable, str(CODE_DOCS), "check", str(repo)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Documentation drift detected", result.stderr)

    def test_check_passes_after_docs_are_committed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            run([sys.executable, str(CODE_DOCS), "generate", str(repo)], ROOT)
            run(["git", "add", "docs"], repo)
            run(["git", "commit", "-m", "add docs"], repo)

            result = run([sys.executable, str(CODE_DOCS), "check", str(repo)], ROOT)
            self.assertIn("Documentation is up to date.", result.stdout)


if __name__ == "__main__":
    unittest.main()
