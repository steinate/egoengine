import json, csv, hashlib, shutil, subprocess
from pathlib import Path
import numpy as np
from PIL import Image

BASE = Path("/vepfs/public/pengjiaqi/interndata-human-pair/human41")
OUT = BASE / "delivery"
OUT.mkdir(exist_ok=True)
physical = json.loads((BASE / "output/physics-final/result.json").read_text())
control = json.loads((BASE / "output/no-contact-control/result.json").read_text())
render = json.loads((BASE / "output/render-final/result.json").read_text())
skin = json.loads((BASE / "output/skin-cache/manifest.json").read_text())
assert physical["success_lift_hold"] and physical["minimum_hold_lift_m"] > 0.10
assert control["hand_contact_events_with_impulse"] == 0 and control["max_cube_lift_m"] < 0.001
assert render["frames"] == 130 and render["max_skinning_joint_position_error_m"] < 1e-5
assert (
    render["source_physics_sha256"]
    == hashlib.sha256((BASE / "output/physics-final/physics-tracks.npz").read_bytes()).hexdigest()
)
videos = {}
for view in ["ego", "observer"]:
    folder = BASE / "output/render-final" / view
    stats = []
    for i in range(130):
        path = folder / f"{i:04d}.png"
        im = np.array(Image.open(path))
        assert im.shape == (720, 1280, 3) and im.std() > 1
        stats.append(
            {
                "frame": i,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "std": float(im.std()),
            }
        )
    target = OUT / f"human-grasp-{view}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            "15",
            "-i",
            str(folder / "%04d.png"),
            "-frames:v",
            "130",
            "-c:v",
            "libx264",
            "-crf",
            "17",
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
                "-show_entries",
                "stream=width,height,nb_read_frames,r_frame_rate:format=duration",
                "-of",
                "json",
                str(target),
            ]
        )
    )
    assert int(probe["streams"][0]["nb_read_frames"]) == 130
    videos[view] = {"probe": probe, "images": stats}
    shutil.copy2(folder / "0075.png", OUT / f"grasp-lift-{view}.png")
data = np.load(BASE / "output/physics-final/physics-tracks.npz")
shutil.copy2(BASE / "output/physics-final/physics-tracks.npz", OUT / "human-physics-tracks.npz")
with (OUT / "object-trajectory.csv").open("w") as f:
    w = csv.writer(f)
    w.writerow(
        [
            "control_time_s",
            "x_m",
            "y_m",
            "z_m",
            "qw",
            "qx",
            "qy",
            "qz",
            "vx_m_s",
            "vy_m_s",
            "vz_m_s",
            "hand_contact_impulse_Ns",
        ]
    )
    for i, t in enumerate(data["time_s"]):
        w.writerow(
            [
                t,
                *data["cube_position_m"][i],
                *data["cube_quaternion_wxyz"][i],
                *data["cube_linear_velocity_m_s"][i],
                data["hand_contact_impulse_Ns"][i],
            ]
        )
for source, target in [
    ("output/physics-final/result.json", "physics-result.json"),
    ("output/no-contact-control/result.json", "no-contact-control.json"),
    ("output/human-plan.json", "human-plan.json"),
    ("output/grasp-solution.json", "grasp-ik.json"),
    ("output/physics-final/cameras.json", "cameras.json"),
    ("output/mocap-inspection.json", "mocap-reference.json"),
]:
    shutil.copy2(BASE / source, OUT / target)
(OUT / "skinning-verification.json").write_text(json.dumps(skin, indent=2))
(OUT / "verification.json").write_text(
    json.dumps(
        {"physics": physical, "negative_control": control, "render": render, "videos": videos},
        indent=2,
    )
)
contacts = json.loads((BASE / "output/physics-final/contacts.json").read_text())
impulses = [c for c in contacts if c[3] > 1e-8]
(OUT / "contact-evidence.json").write_text(
    json.dumps(
        {
            "columns": [
                "control_time_s",
                "actor_paths",
                "minimum_separation_m",
                "sum_contact_impulse_magnitudes_Ns",
            ],
            "events": impulses,
        },
        indent=2,
    )
)
manifest = {
    "asset": "Reallusion CC3 Worker, NVIDIA public rigged characters evaluation sample",
    "asset_download": "https://d4i3qtqj3r0z5.cloudfront.net/Characters_NVD%4010012.zip",
    "asset_archive_sha256": hashlib.sha256(
        (BASE / "assets/Characters_NVD10012.zip").read_bytes()
    ).hexdigest(),
    "runtime": (BASE.parent / "runtime41/VERSION").read_text().strip(),
    "asset_license_note": "Bundled Reallusion Readme restricts sample to evaluation/non-production use. Not cleared for AI training. Current Reallusion content policy lists AI training under Enterprise licensing. No model assets or textures included in code archive.",
    "asset_license_url": "https://www.reallusion.com/license/content.html",
    "source_physics_sha256": render["source_physics_sha256"],
    "scripts": {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(BASE.glob("*.py"))
    },
    "time_convention": "time_s is nominal control time; cube state is read after the following 1/240 s physics tick. No hardware timestamps. Video samples every second 30 Hz control record, at 15 fps.",
}
(OUT / "source-manifest.json").write_text(json.dumps(manifest, indent=2))
print(
    "DELIVERY_VALIDATED",
    [(k, v["probe"]["streams"][0]["nb_read_frames"]) for k, v in videos.items()],
    flush=True,
)
