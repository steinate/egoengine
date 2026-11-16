"""Check fresh-path staging and verified selective assets without network/GPU."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import task_assets


REPO = Path(__file__).resolve().parents[1]


class FreshSetupTests(unittest.TestCase):
    def test_stage_external_directory_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="ego setup ") as tmp:
            root = Path(tmp) / "run"
            command = [sys.executable, str(REPO / "migration/prepare_workspace.py"), str(root)]
            subprocess.run(command, check=True, capture_output=True)
            config = (root / "robot-stack-v2/configure.py").read_text()
            self.assertIn(f"ENGINE = Path({str(REPO)!r})", config)
            self.assertNotIn("/vepfs/public/pengjiaqi", config)
            self.assertEqual((root / "src/InternDataEngine41").resolve(), REPO)
            self.assertIn("migration/run_engine.sh", (root / "run_env41.sh").read_text())
            self.assertIn("omni.usd.libs", (root / "human41/usd_python.sh").read_text())
            self.assertTrue((root / "anime-human-v1/provenance.json").is_file())
            subprocess.run(command, check=True, capture_output=True)
            target = root / "robot-stack-v2/run.py"
            target.write_text("user changes\n")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Refusing", result.stderr)
            self.assertEqual(target.read_text(), "user changes\n")

    def test_asset_plan_has_no_network_and_no_duplicates(self):
        with (
            patch.object(sys, "argv", ["task_assets.py"]),
            patch("urllib.request.urlopen", side_effect=AssertionError("unexpected download")),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            task_assets.main()
        report = json.loads(output.getvalue())
        self.assertFalse(report["network_enabled"])
        files = task_assets.selected_files()
        self.assertEqual(len(files), len({f["path"] for f in files}))
        for component in [
            "assets/split_aloha_mid_360/",
            "assets/basic/stack_lift/",
            "curobo/src/curobo/content/",
            "panda_drake/",
        ]:
            self.assertTrue(
                any(f["path"].startswith("InternDataAssets/" + component) for f in files)
            )

    def test_both_hash_formats_reject_same_size_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "asset"
            content = b"correct data"
            path.write_bytes(content)
            entry = {
                "bytes": len(content),
                "upstream_lfs_sha256": hashlib.sha256(content).hexdigest(),
                "git_blob_oid": hashlib.sha1(
                    f"blob {len(content)}\0".encode() + content
                ).hexdigest(),
            }
            self.assertTrue(task_assets.matches(path, entry))
            entry["upstream_lfs_sha256"] = None
            self.assertTrue(task_assets.matches(path, entry))
            path.write_bytes(b"corrupt data")
            self.assertFalse(task_assets.matches(path, entry))


if __name__ == "__main__":
    unittest.main()
