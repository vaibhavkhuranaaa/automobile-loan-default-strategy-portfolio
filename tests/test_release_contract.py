import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTest(unittest.TestCase):
    def test_health_reports_checkout_revision(self):
        os.environ.pop("SOURCE_SHA", None)
        from api import main

        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()

        class Connection:
            def execute(self, _query):
                return self

            def fetchone(self):
                return (233_154,)

            def close(self):
                pass

        with patch.object(main, "connection", return_value=Connection()):
            response = main.health()

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["records"], 233_154)
        self.assertEqual(response["source_sha"], head)

    def test_deployment_and_registry_use_source_sha(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        deploy = (ROOT / "scripts" / "deploy.sh").read_text()
        release = json.loads((ROOT / "portfolio" / "release.json").read_text())

        self.assertIn('ARG SOURCE_SHA=""', dockerfile)
        self.assertIn('SOURCE_SHA=${SOURCE_SHA}', dockerfile)
        self.assertIn('--build-arg "SOURCE_SHA=$SHA"', deploy)
        self.assertIn('--set-env-vars "SOURCE_SHA=$SHA"', deploy)
        self.assertIn("git archive HEAD", deploy)
        self.assertIn('cp data/quarantine/loans.db "$CONTEXT/data/quarantine/loans.db"', deploy)
        self.assertEqual(release["verification"]["sourceShaField"], "source_sha")

    def test_public_tree_excludes_delivery_state_and_datasets(self):
        tracked = subprocess.check_output(
            ["git", "ls-files"], cwd=ROOT, text=True
        ).splitlines()
        history = [
            line.split(" ", 1)[1]
            for line in subprocess.check_output(
                ["git", "rev-list", "--objects", "HEAD"], cwd=ROOT, text=True
            ).splitlines()
            if " " in line
        ]
        self.assertFalse(any(path.startswith(".project/") for path in tracked))
        self.assertFalse(any(Path(path).suffix in {".db", ".sqlite", ".sqlite3"} for path in tracked))
        self.assertFalse(any(path.startswith(".project/") for path in history))
        self.assertFalse(any(Path(path).suffix in {".db", ".sqlite", ".sqlite3"} for path in history))
        self.assertFalse(any(path.startswith("bi/exports/") for path in history))
        self.assertFalse(any(path.startswith("artifacts/kpi_pack/") and Path(path).suffix in {".csv", ".xlsx"} for path in history))

    def test_public_loan_api_uses_record_references(self):
        analytics = (ROOT / "api" / "analytics.py").read_text()
        main = (ROOT / "api" / "main.py").read_text()
        loans_view = (ROOT / "web" / "src" / "views" / "Loans.jsx").read_text()
        db_builder = (ROOT / "scripts" / "build_db.py").read_text()

        self.assertIn('"recordRef": f"VL-{row[\'public_ref\']}"', analytics)
        self.assertNotIn('"loanId": int(row["loan_id"])', analytics)
        self.assertIn("/loans/{record_ref}", analytics)
        self.assertNotIn("offset: int = Query", analytics)
        self.assertNotIn('"offset": 0', analytics)
        self.assertNotIn('"id_asc"', analytics)
        self.assertIn("LIMIT 20", analytics)
        self.assertIn("row.recordRef", loans_view)
        self.assertNotIn('@app.get("/api/loans")', main)
        self.assertIn("secrets.token_hex(6)", db_builder)
        self.assertIn('"public_ref": record_refs(len(frame))', db_builder)


if __name__ == "__main__":
    unittest.main()
