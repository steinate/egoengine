"""Encode a sampled episode with original timing and matching robot frames."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw


def run(args):
    subprocess.run(args, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path)
    args = parser.parse_args()
    episode = args.episode.resolve()
    base = episode / "human"
    folder = base / "render"
    report = json.loads((folder / "verification.json").read_text())
    assert max(report["sync_audit_mae_255"].values()) < 5
    assert report["max_world_matrix_error"] < 1e-5
    assert (
        report["source_sha256"]
        == hashlib.sha256((episode / "source/world-tracks.npz").read_bytes()).hexdigest()
    )
    assert (
        report["source_animation_sha256"]
        == hashlib.sha256((base / "human-animation.npz").read_bytes()).hexdigest()
    )
    frames = report["samples"]
    count = report["frames"]
    fps = round(report["fps"])
    times = np.asarray(frames) / fps
    assert frames == sorted(set(frames)) and frames[0] == 0 and frames[-1] == count - 1
    out = folder / "delivery"
    out.mkdir(exist_ok=True)
    robot = folder / "robot-samples"
    robot.mkdir(exist_ok=True)
    expression = "+".join(f"eq(n\\,{i})" for i in frames)
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(episode / "source/robot-raw.mp4"),
            "-vf",
            f"select='{expression}',scale=640:360,setpts=N/({fps}*TB)",
            "-r",
            str(fps),
            str(robot / "%04d.png"),
        ]
    )
    assert len(list(robot.glob("*.png"))) == len(frames)
    triptych = folder / "triptych"
    triptych.mkdir(exist_ok=True)
    for index, source in enumerate(frames):
        canvas = Image.new("RGB", (1920, 390), "#111827")
        draw = ImageDraw.Draw(canvas)
        paths = [
            robot / f"{index + 1:04d}.png",
            folder / "ego" / f"{source:04d}.png",
            folder / "front" / f"{source:04d}.png",
        ]
        for column, (label, path) in enumerate(zip(("Robot", "Human ego", "Human front"), paths)):
            with Image.open(path) as im:
                assert im.size == (640, 360)
                canvas.paste(im.convert("RGB"), (column * 640, 30))
            draw.text(
                (column * 640 + 10, 8),
                f"{label} | source {source} | {source / fps:.3f}s | sampled debug",
                fill="white",
            )
        canvas.save(triptych / f"{source:04d}.png", compress_level=1)
    durations = np.diff(np.r_[times, count / fps])
    assert np.all(durations > 0)
    hold_frames = np.diff(frames + [count])
    checks = {}
    for name, images in (("human-ego-debug", folder / "ego"), ("robot-ego-front-debug", triptych)):
        sequence = folder / f"encode-{name}"
        sequence.mkdir(exist_ok=True)
        index = 0
        for source, repeat in zip(frames, hold_frames):
            # A constant-rate symlink sequence preserves exact integer frame
            # boundaries; it stores no duplicate image payloads.
            target = Path("..") / images.name / f"{source:04d}.png"
            for _ in range(int(repeat)):
                link = sequence / f"{index:06d}.png"
                if link.is_symlink():
                    assert link.readlink() == target
                else:
                    link.symlink_to(target)
                index += 1
        assert index == count
        output = out / f"{name}.mp4"
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(sequence / "%06d.png"),
                "-t",
                str(count / fps),
                "-r",
                str(fps),
                "-frames:v",
                str(count),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )
        probe = json.loads(
            subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-count_frames",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=nb_read_frames,duration,r_frame_rate",
                    "-of",
                    "json",
                    str(output),
                ]
            )
        )["streams"][0]
        assert int(probe["nb_read_frames"]) == count
        assert abs(float(probe["duration"]) - count / fps) < 1 / fps
        checks[name] = {"probe": probe, "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    report.update(
        videos=checks,
        encoding="Sampled source frames held until next source timestamp; all views share the same samples. Not a full-rate render.",
    )
    (out / "debug-verification.json").write_text(json.dumps(report, indent=2))
    print("DEBUG_VIDEO_VERIFIED", out, flush=True)


if __name__ == "__main__":
    main()
