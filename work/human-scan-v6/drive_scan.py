"""Fit scan-sized fingers to the accepted episode's spatial hand contacts."""

import sys, json, hashlib, argparse, time
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from scipy.interpolate import CubicSpline
from scipy.signal import savgol_filter
from hand_model import Hand, normals

ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
B = ROOT / "human-scan-v6"
sys.path.insert(0, str(ROOT / "human41"))
from human_control import Human

parser = argparse.ArgumentParser()
parser.add_argument("--start", type=int, default=0)
parser.add_argument("--end", type=int, default=1507)
parser.add_argument("--preview", action="store_true")
parser.add_argument("--bake-only", action="store_true")
a = parser.parse_args()
old = np.load(ROOT / "human-natural-v4/human-animation.npz")
mesh = np.load(B / "scan-mesh.npz")
N = len(old["source_frame"])
h = Human()
h.world = old["world_transform"]
g = np.stack([h.fk(p) for p in old["local"]])
rest = h.fk(h.rest)
ref = np.load(B / "contact-initialization.npz")
hands = {s: Hand(mesh, s) for s in ["L", "R"]}
out = B / "scan-cache"
out.mkdir(exist_ok=True)
results = {}
report = {}
source_hash = hashlib.sha256((B / "scan-mesh.npz").read_bytes()).hexdigest()
if not a.bake_only:
    for side, hand in hands.items():
        W = g[:, h.idx(side + "_Hand")]
        target = np.einsum(
            "nji,nkj->nki", W[:, :3, :3], ref[side + "_tip_reference_world"] - W[:, None, :3, 3]
        )
        qs = []
        errors = []
        previous = np.r_[0.0, 0.0, 0.0, 0.3, 0.2, np.tile([0.0, 0.2, 0.4], 4)]
        previous = np.clip(previous, hand.lo + 1e-7, hand.hi - 1e-7)
        # Spatial samples every three frames, with all task transitions explicitly kept.
        keys = np.unique(np.r_[np.arange(0, N, 3), N - 1, 137, 433, 621, 780, 1044, 1191, 1331])
        start = time.time()
        for frame in keys:
            goal = target[frame]

            def residual(q):
                return np.r_[
                    (hand.tips(q) - goal).ravel() * 300,
                    (q - previous) * 0.045,
                    q * np.r_[[0.015] * 5, np.tile([0.08, 0.01, 0.01], 4)],
                ]

            solved = least_squares(
                residual,
                previous,
                bounds=(hand.lo + 1e-8, hand.hi - 1e-8),
                max_nfev=150 if frame == 0 else 35,
                ftol=1e-7,
                xtol=1e-7,
            )
            previous = solved.x
            qs.append(previous.copy())
            if len(qs) % 75 == 0:
                print(
                    "FIT",
                    side,
                    frame,
                    "max_tip_mm",
                    np.linalg.norm(hand.tips(previous) - goal, axis=1).max() * 1000,
                    "seconds",
                    time.time() - start,
                    flush=True,
                )
        q = CubicSpline(keys, qs, axis=0, bc_type="natural")(np.arange(N))
        q = np.clip(savgol_filter(q, 15, 3, axis=0), hand.lo, hand.hi)
        error = np.array([np.linalg.norm(hand.tips(q[i]) - target[i], axis=1) for i in range(N)])
        results[side + "_q"] = q
        results[side + "_wrist_world"] = W
        results[side + "_tip_error_m"] = error
        report[side] = {
            "max_tip_error_mm": float(error.max() * 1000),
            "p95_tip_error_mm": float(np.percentile(error, 95) * 1000),
            "joint_centers_hand_local_m": hand.landmarks.tolist(),
            "max_joint_step_deg": float(np.max(np.abs(np.diff(q, axis=0))) * 180 / np.pi),
            "solved_frames": keys.tolist(),
        }
    np.savez_compressed(
        B / "scan-animation.npz",
        **results,
        source_frame=old["source_frame"],
        video_time_s=old["video_time_s"],
    )
    (B / "scan-fit-report.json").write_text(json.dumps(report, indent=2))
    print(
        "FIT_DONE",
        json.dumps(
            {
                s: {
                    k: v
                    for k, v in r.items()
                    if k not in ["joint_centers_hand_local_m", "solved_frames"]
                }
                for s, r in report.items()
            }
        ),
        flush=True,
    )
else:
    results = dict(np.load(B / "scan-animation.npz"))
animation_hash = hashlib.sha256((B / "scan-animation.npz").read_bytes()).hexdigest()
weights_hash = hashlib.sha256((B / "heat-weights.npz").read_bytes()).hexdigest()
deformer_hash = hashlib.sha256((B / "hand_model.py").read_bytes()).hexdigest()
samples = (
    [0, 137, 258, 433, 474, 780, 1006, 1044, 1130, 1331, 1506]
    if a.preview
    else range(a.start, min(a.end, N))
)
for frame in samples:
    data = {}
    for side, hand in hands.items():
        W = results[side + "_wrist_world"][frame]
        j = h.idx(side + "_ForearmTwist02")
        F = W.copy()
        F[:3, :3] = g[frame, j, :3, :3] @ rest[j, :3, :3].T @ rest[h.idx(side + "_Hand"), :3, :3]
        vertices = hand.deform(results[side + "_q"][frame], np.linalg.inv(W) @ F)
        vertices = vertices @ W[:3, :3].T + W[:3, 3]
        faces = mesh["faces"][:, ::-1] if side == "L" else mesh["faces"]
        data[side + "_points"] = vertices.astype(np.float32)
        data[side + "_normals"] = normals(vertices, faces).astype(np.float32)
        assert np.isfinite(vertices).all()
    data["animation_sha256"] = np.array(animation_hash)
    data["source_frame"] = np.array(frame)
    data["weights_sha256"] = np.array(weights_hash)
    data["deformer_sha256"] = np.array(deformer_hash)
    temp = out / f"{frame:04d}.tmp.npz"
    np.savez(temp, **data)
    temp.replace(out / f"{frame:04d}.npz")
    if frame % 30 == 0 or a.preview:
        print("SCAN_BAKED", frame, flush=True)
(
    out / ("manifest-preview.json" if a.preview else f"manifest-{a.start}-{min(a.end, N)}.json")
).write_text(
    json.dumps(
        {
            "frames": list(samples),
            "source_scan_mesh_sha256": source_hash,
            "animation_sha256": animation_hash,
            "weights_sha256": weights_hash,
            "deformer_sha256": deformer_hash,
            "vertices_per_hand": len(mesh["points_cm"]),
            "method": "17-DOF scan-sized hand, temporal fitting and dual quaternion skinning; native right scan mirrored for left hand; original body and accepted full human arm IK retained; original robot object motion unchanged",
        },
        indent=2,
    )
)
