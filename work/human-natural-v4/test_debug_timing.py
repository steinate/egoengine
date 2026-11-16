"""Exercise actual ffmpeg sampling/encoding, including an irregular final interval."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image


class DebugTimingTest(unittest.TestCase):
    def test_robot_human_hold_same_source_frames_at_original_times(self):
        spec = importlib.util.spec_from_file_location(
            "encoder", Path(__file__).with_name("encode_debug.py")
        )
        encoder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(encoder)
        with tempfile.TemporaryDirectory(prefix="ego-debug-timing-") as tmp:
            base = Path(tmp)
            encoder.BASE = base
            for name in ("source", "audit", "samples/ego", "samples/front", "robot-input"):
                (base / name).mkdir(parents=True)
            for name in ("human-animation.npz", "source/world-tracks.npz"):
                (base / name).write_bytes(b"synthetic timing fixture, not a real trajectory")
            digest = hashlib.sha256((base / "human-animation.npz").read_bytes()).hexdigest()
            samples = [0, 3, 6, 8]
            colors = [(20 + i * 20, 60, 90) for i in range(9)]
            for i, color in enumerate(colors):
                im = Image.new("RGB", (640, 360), color)
                im.save(base / "robot-input" / f"{i:04d}.png")
                if i in samples:
                    for view in ("ego", "front"):
                        im.save(base / "samples" / view / f"{i:04d}.png")
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-framerate",
                    "15",
                    "-i",
                    str(base / "robot-input/%04d.png"),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(base / "source/robot-full.mp4"),
                ],
                check=True,
            )
            report = dict(
                source_animation_sha256=digest,
                source_world_tracks_sha256=digest,
                render_script_sha256="synthetic",
                quality="debug",
                renderer="RayTracedLighting",
                resolution=[640, 360],
                source_frames=samples,
                source_episode_frames=9,
                fps=15,
                source_time_s=[i / 15 for i in samples],
                max_object_position_error_m=0,
                max_object_rotation_error_rad=0,
                sync_audit_passed=True,
            )
            for path in (
                base / "audit/verification-both.json",
                base / "samples/verification-both.json",
            ):
                path.write_text(json.dumps(report))
            with patch.object(
                sys, "argv", ["encode_debug.py", "--input", "samples", "--audit", "audit"]
            ):
                encoder.main()
            raw = subprocess.check_output(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    str(base / "samples/delivery/robot-ego-front-debug.mp4"),
                    "-f",
                    "rawvideo",
                    "-pix_fmt",
                    "rgb24",
                    "-",
                ]
            )
            decoded = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 390, 1920, 3)
            self.assertEqual(len(decoded), 9)
            expected = np.asarray([colors[i] for i in [0, 0, 0, 3, 3, 3, 6, 6, 8]])
            for column in range(3):
                observed = decoded[:, 150:220, column * 640 + 200 : column * 640 + 300].mean(
                    axis=(1, 2)
                )
                np.testing.assert_allclose(observed, expected, atol=6, rtol=0)


if __name__ == "__main__":
    unittest.main()
