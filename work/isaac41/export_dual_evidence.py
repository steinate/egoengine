"""Export and verify both arms from an official Split Aloha LMDB episode."""

import argparse, json, pickle, hashlib
from pathlib import Path
import numpy as np
import lmdb, imageio.v2 as imageio

p = argparse.ArgumentParser()
p.add_argument("episode")
p.add_argument("output")
a = p.parse_args()
episode = Path(a.episode)
out = Path(a.output)
out.mkdir(parents=True, exist_ok=True)
env = lmdb.open(str(episode / "lmdb"), readonly=True, lock=False)
tracks = {}
summary = {}
with env.begin() as tx:

    def get(k):
        return np.asarray(pickle.loads(tx.get(k.encode())))

    for arm in ["left", "right"]:
        q = get(f"states.{arm}_joint.position")
        act = get(f"master_actions.{arm}_joint.position")
        grip = get(f"states.{arm}_gripper.position")
        tracks[arm + "_joint_state"] = q
        tracks[arm + "_joint_action"] = act
        tracks[arm + "_gripper_width"] = grip
        summary[arm] = {
            "frames": len(q),
            "dof": q.shape[-1],
            "joint_range_rad": np.ptp(q, axis=0).tolist(),
            "max_joint_motion_rad": float(np.ptp(q, axis=0).max()),
            "finite": bool(np.isfinite(q).all()),
        }
    camera = {}
    for name in ["head", "hand_left", "hand_right"]:
        video = episode / f"images.rgb.{name}/demo.mp4"
        reader = imageio.get_reader(video)
        meta = reader.get_meta_data()
        n = reader.count_frames()
        for i in [0, n // 2, n - 1]:
            imageio.imwrite(out / f"{name}-frame-{i:04d}.jpg", reader.get_data(i))
        camera[name] = {
            "frames": n,
            "fps": meta["fps"],
            "size": list(meta["size"]),
            "source_file": str(video),
        }
        reader.close()
n = summary["left"]["frames"]
result = {
    "robot": "Split Aloha",
    "task": "official dual-arm target tracking",
    "pipeline": "launcher.py + configs/simbox/de_plan_with_render_template.yaml",
    "frames": n,
    "arms": summary,
    "cameras": camera,
    "task_config_sha256": "1f51ee0df9fae869fb2dcb4a7b33ef39f8963632470cd6b4e07d1786960c72f7",
    "source_episode": str(episode),
    "passed": all(
        s["finite"] and s["max_joint_motion_rad"] > 0.01 and s["frames"] == n
        for s in summary.values()
    )
    and all(s["frames"] == n for s in camera.values()),
}
np.savez_compressed(out / "dual-arm-tracks.npz", **tracks)
(out / "verification.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
assert result["passed"]
