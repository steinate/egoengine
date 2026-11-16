import json, subprocess, hashlib, shutil
from pathlib import Path

ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
BASE = ROOT / "human-ik-v2"
OUT = BASE / "delivery"
OUT.mkdir(exist_ok=True)
rv = {
    name: json.loads((BASE / f"render/verification-{name}.json").read_text())
    for name in ["ego", "front"]
}
assert (
    all(x["source_frames"] == list(range(844)) for x in rv.values())
    and rv["ego"]["source_animation_sha256"] == rv["front"]["source_animation_sha256"]
)
r = dict(rv["ego"])
r["views"] = rv
r["max_object_position_error_m"] = max(x["max_object_position_error_m"] for x in rv.values())
r["max_object_rotation_error_rad"] = max(x["max_object_rotation_error_rad"] for x in rv.values())
v = json.loads((OUT / "ik-and-pair-verification.json").read_text())
assert (
    r["source_frames"] == list(range(844))
    and r["source_animation_sha256"] == v["source_animation_sha256"]
)
assert r["max_object_position_error_m"] < 1e-6 and r["max_object_rotation_error_rad"] < 1e-6
original = (
    ROOT
    / "outputs41/official-dual-grasp/BananaBaseTask/split_aloha/stack_lift_cubes/two_lr/2026-11-12_09_43_18_286976/images.rgb.head/demo.mp4"
)


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
            "844",
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
            str(OUT / f"human-{name}-optimized.mp4"),
        ]
    )
font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
filters = []
for i, label in enumerate(
    ["Official robot", "Human ego - optimized IK", "Human front - optimized IK"]
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
        str(OUT / "human-ego-optimized.mp4"),
        "-i",
        str(OUT / "human-front-optimized.mp4"),
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[v]",
        "-frames:v",
        "844",
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
        str(OUT / "robot-ego-front-optimized.mp4"),
    ]
)
checks = {}
for name in [
    "human-ego-optimized.mp4",
    "human-front-optimized.mp4",
    "robot-ego-front-optimized.mp4",
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
    assert int(probe["nb_read_frames"]) == 844 and probe["r_frame_rate"] == "15/1"
    checks[name] = {"probe": probe, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
v["render"] = r
v["videos"] = checks
(OUT / "ik-and-pair-verification.json").write_text(json.dumps(v, indent=2))
shutil.copy(BASE / "retarget-report.json", OUT / "retarget-report.json")
shutil.copy(BASE / "skin-cache/manifest.json", OUT / "skinning-verification.json")
for name in ["ego", "front"]:
    for i in [140, 550, 843]:
        shutil.copy(BASE / f"render/{name}/{i:04d}.png", OUT / f"{name}-{i:04d}.png")
print("OPTIMIZED_VIDEO_DONE", json.dumps(checks), flush=True)
