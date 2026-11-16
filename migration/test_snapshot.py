"""Migration checks: exact contents/permissions/links and corruption rejection."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parent


class SnapshotTests(unittest.TestCase):
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
