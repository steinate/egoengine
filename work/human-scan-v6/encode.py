"""Encode only a complete, synchronized and verified scan-hand episode."""

import hashlib, json, subprocess, shutil
from pathlib import Path
import numpy as np

B = Path("/vepfs/public/pengjiaqi/interndata-human-pair/human-scan-v6")
D = B / "delivery"
D.mkdir(exist_ok=True)
N = 1507
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
cache = json.loads((B / "cache-verification.json").read_text())
contract = json.loads((B / "replay-contract.json").read_text())
parts = [
    json.loads((B / "render" / f"verification-{view}-full.json").read_text())
    for view in ["ego", "front"]
]
assert all(p["source_frames"] == list(range(N)) for p in parts)
assert all(p["scan_animation_sha256"] == cache["animation_sha256"] for p in parts)
assert all(p["render_script_sha256"] == sha(B / "render.py") for p in parts)
assert all(
    p["max_object_position_error_m"] < 1e-6 and p["max_object_rotation_error_rad"] < 1e-6
    for p in parts
)
for name, value in contract["source_hashes"].items():
    assert sha(B / "source" / name) == value, name


def run(args):
    subprocess.run(args, check=True)


for view in ["ego", "front"]:
    assert sorted(int(p.stem) for p in (B / "render" / view).glob("*.png")) == list(range(N))
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-framerate",
            "15",
            "-i",
            str(B / f"render/{view}/%04d.png"),
            "-frames:v",
            str(N),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(D / f"human-{view}-full.mp4"),
        ]
    )
font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
filters = []
for i, label in enumerate(
    [
        "Source robot | complete episode",
        "Human ego | DRL scanned hands",
        "Human front | same timeline",
    ]
):
    filters.append(
        f"[{i}:v]scale=960:540,pad=960:584:0:44:color=0x111827,drawtext=fontfile={font}:text='{label} | %{{n}}':x=14:y=10:fontcolor=white:fontsize=20[v{i}]"
    )
filters.append("[v0][v1][v2]hstack=inputs=3[v]")
run(
    [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(B / "source/robot-full.mp4"),
        "-i",
        str(D / "human-ego-full.mp4"),
        "-i",
        str(D / "human-front-full.mp4"),
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[v]",
        "-frames:v",
        str(N),
        "-r",
        "15",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(D / "robot-ego-front-full.mp4"),
    ]
)
checks = {}
for p in D.glob("*.mp4"):
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
                "stream=width,height,r_frame_rate,nb_read_frames,duration",
                "-of",
                "json",
                str(p),
            ]
        )
    )["streams"][0]
    assert int(probe["nb_read_frames"]) == N and probe["r_frame_rate"] == "15/1", p
    checks[p.name] = {"probe": probe, "sha256": sha(p)}
tracks = dict(np.load(B / "source/world-tracks.npz"))
animation = np.load(B / "scan-animation.npz")
reference = np.load(B / "contact-initialization.npz")
tracks.update({k: animation[k] for k in animation.files if not k.endswith("_tip_error_m")})
tracks["camera_world_usd"] = reference["camera_reference_world_usd"]
tracks["ego_camera_K"] = np.array(parts[0]["camera_K"])
tracks["front_camera_K"] = np.array(
    [[1280 * 25.5 / 36, 0, 640], [0, 1280 * 25.5 / 36, 360], [0, 0, 1]]
)
tracks["front_camera_world_usd"] = np.array(parts[0]["front_camera_world_usd"])
np.savez_compressed(D / "paired-world-trajectories.npz", **tracks)
for name in [
    "replay-contract.json",
    "download.json",
    "scan-inspection.json",
    "scan-fit-report.json",
    "surface-contact-report.json",
    "tray-contact-report.json",
    "template-report.json",
    "cache-verification.json",
]:
    shutil.copy2(B / name, D / name)
(D / "video-verification.json").write_text(
    json.dumps(
        {
            "frames": N,
            "fps": 15,
            "duration_s": N / 15,
            "source_objects_unchanged": True,
            "max_object_position_error_m": max(p["max_object_position_error_m"] for p in parts),
            "max_object_rotation_error_rad": max(p["max_object_rotation_error_rad"] for p in parts),
            "scan_animation_sha256": cache["animation_sha256"],
            "videos": checks,
            "renders": parts,
        },
        indent=2,
    )
)
for i in [137, 780, 1331, 1506]:
    for view in ["ego", "front"]:
        shutil.copy2(B / f"render/{view}/{i:04d}.png", D / f"{view}-{i:04d}.png")
print("COMPLETE_SCAN_PAIR_ENCODED", json.dumps(checks), flush=True)
