import json, subprocess, hashlib, shutil
from pathlib import Path

ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
BASE = ROOT / "human-natural-v4"
OUT = BASE / "delivery"
OUT.mkdir(exist_ok=True)
N = json.loads((BASE / "source/contact-schedule.json").read_text())["frames"]
rv = {}
for name in ["ego", "front"]:
    parts = [
        json.loads(f.read_text())
        for f in sorted((BASE / "render").glob(f"verification-{name}-part*.json"))
    ]
    assert len(parts) == 3
    assert all(
        part["render_script_sha256"]
        == hashlib.sha256((BASE / "render.py").read_bytes()).hexdigest()
        for part in parts
    )
    assert sorted(int(p.stem) for p in (BASE / "render" / name).glob("*.png")) == list(range(N))
    for log in (BASE / "render").glob(f"kit-{name}-part*.log"):
        assert not any(
            "[Error]" in line and "rtx.optixdenoising.plugin" in line
            for line in log.read_text(errors="replace").splitlines()
        )
    frames = sorted(i for part in parts for i in part["source_frames"])
    assert frames == list(range(N))
    assert len({x["source_animation_sha256"] for x in parts}) == 1
    assert len({(x["quality"], x["renderer"], tuple(x["resolution"])) for x in parts}) == 1
    report = dict(parts[0])
    report.update(
        frames=N,
        source_frames=frames,
        segments=parts,
        max_object_position_error_m=max(x["max_object_position_error_m"] for x in parts),
        max_object_rotation_error_rad=max(x["max_object_rotation_error_rad"] for x in parts),
    )
    rv[name] = report

assert (
    all(x["source_frames"] == list(range(N)) for x in rv.values())
    and rv["ego"]["source_animation_sha256"] == rv["front"]["source_animation_sha256"]
    and all(rv["ego"][key] == rv["front"][key] for key in ("quality", "renderer", "resolution"))
)
r = dict(rv["ego"])
r["views"] = rv
r["max_object_position_error_m"] = max(x["max_object_position_error_m"] for x in rv.values())
r["max_object_rotation_error_rad"] = max(x["max_object_rotation_error_rad"] for x in rv.values())
v = json.loads((OUT / "ik-and-pair-verification.json").read_text())
assert (
    r["source_frames"] == list(range(N))
    and r["source_animation_sha256"] == v["source_animation_sha256"]
)
assert r["max_object_position_error_m"] < 1e-6 and r["max_object_rotation_error_rad"] < 1e-6
original = BASE / "source/robot-full.mp4"
shutil.copy(original, OUT / "robot-full.mp4")


def run(args):
    subprocess.run(args, check=True)


for name in ["ego", "front"]:
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-framerate",
            "15",
            "-i",
            str(BASE / f"render/{name}/%04d.png"),
            "-frames:v",
            str(N),
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
            str(OUT / f"human-{name}-full.mp4"),
        ]
    )
font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
filters = []
for i, label in enumerate(
    [
        "Verified robot - full episode",
        "Human ego - same object motion",
        "Human front - same episode",
    ]
):
    filters.append(
        f"[{i}:v]scale=960:540,pad=960:584:0:44:color=0x111827,drawtext=fontfile={font}:text='{label} | frame %{{n}}':x=14:y=10:fontcolor=white:fontsize=21[v{i}]"
    )
filters.append("[v0][v1][v2]hstack=inputs=3[v]")
run(
    [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(original),
        "-i",
        str(OUT / "human-ego-full.mp4"),
        "-i",
        str(OUT / "human-front-full.mp4"),
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
        str(OUT / "robot-ego-front-full.mp4"),
    ]
)
checks = {}
for name in [
    "robot-full.mp4",
    "human-ego-full.mp4",
    "human-front-full.mp4",
    "robot-ego-front-full.mp4",
]:
    path = OUT / name
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
                str(path),
            ]
        )
    )["streams"][0]
    assert int(probe["nb_read_frames"]) == N and probe["r_frame_rate"] == "15/1"
    checks[name] = {"probe": probe, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
v["render"] = r
v["videos"] = checks
(OUT / "ik-and-pair-verification.json").write_text(json.dumps(v, indent=2))
shutil.copy(BASE / "retarget-report.json", OUT / "retarget-report.json")
shutil.copy(BASE / "skin-cache/manifest.json", OUT / "skinning-verification.json")
for name in ["ego", "front"]:
    for i in [137, 1044, N - 1]:
        shutil.copy(BASE / f"render/{name}/{i:04d}.png", OUT / f"{name}-{i:04d}.png")
print("FULL_PAIRED_VIDEO_DONE", json.dumps(checks), flush=True)
