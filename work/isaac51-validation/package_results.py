import json, csv, hashlib, subprocess
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
BASE = ROOT / "validation51"
OUT = BASE / "delivery"
OUT.mkdir(exist_ok=True)
f = np.arange(420, 511)
a = np.load(ROOT / "outputs41/human-ego/world-tracks.npz")
keys = ["place_object_world", "pick_object_left1_world", "pick_object_right1_world"]
np.savez_compressed(
    OUT / "official-object-trajectories.npz",
    source_frames=f,
    nominal_physics_time_s=f / 30,
    playback_time_s=(f - f[0]) / 15,
    **{k: a[k][f] for k in keys},
)
with (OUT / "official-object-trajectories.csv").open("w") as h:
    w = csv.writer(h)
    w.writerow(
        ["source_frame", "nominal_physics_time_s", "clip_playback_time_s", "object"]
        + [f"T{i}{j}" for i in range(4) for j in range(4)]
    )
    for k in keys:
        for i in f:
            w.writerow([i, i / 30, (i - f[0]) / 15, k] + a[k][i].ravel().tolist())
results = {}
for mode in ["replay", "mixed", "mixed-upperlimb"]:
    folder = BASE / "output" / mode
    report = json.loads((folder / "result.json").read_text())
    n = report["frames"]
    fps = report["output_fps"]
    assert n == (91 if mode == "replay" else 31), (mode, n)
    images = []
    for i in range(n):
        pic = np.asarray(Image.open(folder / f"{i:04d}.png"))
        assert pic.shape == (540, 960, 3) and pic.std() > 1, (mode, i)
        images.append(
            {
                "frame": i,
                "std": float(pic.std()),
                "sha256": hashlib.sha256(pic.tobytes()).hexdigest(),
            }
        )
    target = (
        OUT
        / (
            {
                "replay": "official-trajectory-replay.mp4",
                "mixed": "native-gaussian-grasp-validation.mp4",
                "mixed-upperlimb": "native-gaussian-upperlimb-validation.mp4",
            }[mode]
        )
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(folder / "%04d.png"),
            "-frames:v",
            str(n),
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
    stream = json.loads(
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
    assert int(stream["streams"][0]["nb_read_frames"]) == n
    results[mode] = {"render": report, "video": stream, "frame_checks": images}
    camera = json.loads((folder / "camera.json").read_text())
    fpx = camera["focal_length"] / camera["horizontal_aperture"] * camera["width"]
    camera["K"] = [[fpx, 0, camera["width"] / 2], [0, fpx, camera["height"] / 2], [0, 0, 1]]
    camera["convention"] = "OpenCV camera axes right/down/forward; column-vector world transforms"
    (OUT / (mode + "-camera.json")).write_text(json.dumps(camera, indent=2))
(OUT / "timestamp-notes.txt").write_text(
    "Source frame indices are preserved. Playback timestamps are derived from the existing 15 fps reference video. nominal_physics_time_s is a nominal value computed as source_frame * (1/30 s), not a recovered hardware or recorder wall-clock timestamp. Native 31-frame videos sample every third source frame at 5 fps. All videos use imposed object transforms; no new task physics was simulated.\n"
)
(OUT / "delivery-check.json").write_text(json.dumps(results, indent=2))
print(
    "DELIVERY_VALIDATED",
    [(m, v["video"]["streams"][0]["nb_read_frames"]) for m, v in results.items()],
    flush=True,
)
