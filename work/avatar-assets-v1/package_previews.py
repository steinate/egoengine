from pathlib import Path
import json, subprocess, hashlib, zipfile, shutil
from PIL import Image, ImageDraw, ImageFont

B = Path("/vepfs/public/pengjiaqi/interndata-human-pair/avatar-assets-v1")
out = B / "delivery"
out.mkdir(exist_ok=True)
order = [
    ("rp_eric_rigged_001", "Eric | scanned | 88 bones"),
    ("rp_carla_rigged_001", "Carla | scanned | 88 bones"),
    ("rp_claudia_rigged_002", "Claudia | scanned | 88 bones"),
    ("mpfb_cc0_adult_male", "MPFB | CC0 | 52 bones"),
]
fontpath = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
font = ImageFont.truetype(fontpath, 21)
gallery = Image.new("RGB", (1920, 688), "#111827")
hands = Image.new("RGB", (1920, 1360), "#111827")
checks = {}
for j, (name, label) in enumerate(order):
    p = B / "renders" / name
    v = json.loads((p / "render-verification.json").read_text())
    assert v["frames"] == 61 and v["not_task_replay"]
    assert sorted(int(f.stem) for f in p.glob("[0-9]*.png")) == list(range(61))
    gallery.paste(Image.open(p / "full-0030.png").resize((480, 640)), (j * 480, 48))
    ImageDraw.Draw(gallery).text((j * 480 + 10, 13), label, fill="white", font=font)
    x = j % 2 * 960
    y = j // 2 * 680
    hands.paste(Image.open(p / "0030.png"), (x, y + 40))
    ImageDraw.Draw(hands).text((x + 12, y + 9), label, fill="white", font=font)
    for vname, f in [("full", "full-0030.png"), ("hands", "0030.png")]:
        shutil.copy(p / f, out / f"{name}-{vname}.png")
    target = out / f"{name}-articulation.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-framerate",
            "15",
            "-i",
            str(p / "%04d.png"),
            "-frames:v",
            "61",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(target),
        ],
        check=True,
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
                str(target),
            ]
        )
    )["streams"][0]
    assert int(probe["nb_read_frames"]) == 61
    checks[name] = {"probe": probe, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
gallery.save(out / "asset-gallery.jpg", quality=95)
hands.save(out / "hand-detail-gallery.jpg", quality=95)
args = ["ffmpeg", "-v", "error", "-y"]
filters = []
for j, (name, label) in enumerate(order):
    args.extend(["-i", str(out / f"{name}-articulation.mp4")])
    filters.append(
        f"[{j}:v]pad=960:680:0:40:color=0x111827,drawtext=fontfile={fontpath}:text='{label}':x=12:y=9:fontcolor=white:fontsize=22[v{j}]"
    )
filters.append("[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|960_0|0_680|960_680[v]")
args.extend(
    [
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[v]",
        "-frames:v",
        "61",
        "-r",
        "15",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(out / "four-assets-articulation.mp4"),
    ]
)
subprocess.run(args, check=True)
(out / "video-verification.json").write_text(json.dumps(checks, indent=2))
for name in [
    "renderpeople-download.json",
    "makehuman_system_assets-download.json",
    "skins02-download.json",
    "scan-inspection.json",
    "mpfb-inspection.json",
    "asset-drive-verification.json",
    "usd-compatibility.json",
    "mpfb-usd-mesh-verification.json",
    "README.txt",
]:
    shutil.copy(B / name, out / name)
with zipfile.ZipFile(out / "inspection-and-code.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for p in out.iterdir():
        if p.suffix in [".json", ".txt"]:
            z.write(p, p.name)
    for p in B.glob("*.py"):
        z.write(p, "code/" + p.name)
checksums = {
    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in out.iterdir()
    if p.is_file() and p.name != "checksums.json"
}
(out / "checksums.json").write_text(json.dumps(checksums, indent=2))
print("PREVIEWS_PACKAGED", checks, flush=True)
