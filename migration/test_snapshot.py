"""Migration checks: exact contents/permissions/links and corruption rejection."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parent


class SnapshotTests(unittest.TestCase):
    def test_checkout_launcher_uses_original_component_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            project = base / "checkout"
            deployment = base / "deployment"
            (project / "migration").mkdir(parents=True)
            (project / "workflows/simbox").mkdir(parents=True)
            (project / "launcher.py").write_text("")
            shutil.copy2(TOOLS / "run_engine.sh", project / "migration/run_engine.sh")
            for component in ("assets", "curobo", "panda_drake"):
                (deployment / "assets/InternDataAssets" / component).mkdir(parents=True)
            (deployment / "runtime41").mkdir()
            runtime = deployment / "runtime41/python.sh"
            runtime.write_text('#!/bin/sh\nprintf "%s\\n" "$PYTHONPATH" "$PWD"\n')
            runtime.chmod(0o755)
            command = ["bash", str(project / "migration/run_engine.sh"), str(deployment), "-V"]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertIn(str(project), result.stdout)
            self.assertTrue((deployment / "tmp").is_dir())
            for component in ("assets", "curobo", "panda_drake"):
                self.assertEqual(
                    (project / "workflows/simbox" / component).resolve(),
                    deployment / "assets/InternDataAssets" / component,
                )
            link = project / "workflows/simbox/assets"
            link.unlink()
            link.symlink_to(deployment / "assets/InternDataAssets")
            result = subprocess.run(command, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(link.resolve(), deployment / "assets/InternDataAssets")

    def test_relocation_changes_only_restored_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            original = base / "original"
            restored = base / "restored"
            original.mkdir()
            restored.mkdir()
            content = f'ROOT = "{original}"\n'
            (original / "run.py").write_text(content)
            (restored / "run.py").write_text(content)
            (restored / "input-link").symlink_to(original / "run.py")
            (restored / "binary.npz").write_bytes(b"unchanged-binary")
            subprocess.run(
                [
                    sys.executable,
                    str(TOOLS / "relocate.py"),
                    str(restored),
                    "--old-root",
                    str(original),
                    "--report",
                    str(base / "report.json"),
                ],
                check=True,
                capture_output=True,
            )
            self.assertEqual((original / "run.py").read_text(), content)
            self.assertEqual(
                (restored / "run.py").read_text(), content.replace(str(original), str(restored))
            )
            self.assertEqual(os.readlink(restored / "input-link"), str(restored / "run.py"))
            self.assertEqual((restored / "binary.npz").read_bytes(), b"unchanged-binary")

    def test_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            (source / "model").mkdir(parents=True)
            payload = source / "model/mesh.bin"
            payload.write_bytes(bytes(range(256)) * 4096)
            script = source / "run.sh"
            script.write_text("#!/bin/sh\nexit 0\n")
            script.chmod(0o755)
            (source / "mesh-link").symlink_to("model/mesh.bin")
            os.link(payload, source / "model/mesh-hardlink.bin")
            bundle = root / "bundle"
            subprocess.run(
                [sys.executable, str(TOOLS / "build_snapshot.py"), str(source), str(bundle)],
                check=True,
                capture_output=True,
            )
            restored = root / "restored"
            command = [sys.executable, str(TOOLS / "restore.py"), str(bundle)]
            subprocess.run([*command, str(restored)], check=True, capture_output=True)
            self.assertEqual((restored / "model/mesh.bin").read_bytes(), payload.read_bytes())
            self.assertEqual((restored / "run.sh").stat().st_mode & 0o777, 0o755)
            self.assertTrue((restored / "tmp").is_dir())
            self.assertEqual(os.readlink(restored / "mesh-link"), "model/mesh.bin")
            self.assertEqual(
                (restored / "model/mesh.bin").stat().st_ino,
                (restored / "model/mesh-hardlink.bin").stat().st_ino,
            )
            # A second extraction must never overwrite an existing deployment.
            result = subprocess.run([*command, str(restored)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            index = json.loads((bundle / "deployment-index.json").read_text())
            archive = bundle / index["archives"][0]["archive"]
            with archive.open("ab") as stream:
                stream.write(b"corrupted")
            target = root / "should-not-exist"
            result = subprocess.run([*command, str(target)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
