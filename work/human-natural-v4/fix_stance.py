"""Put lateral reach in waist, preserving every upper-body world transform."""

from arm_model import *

a = dict(np.load(OUT / "human-animation.npz"))
h.world = a["world_transform"]
errors = []
drift = []
waist = h.idx("Waist")
hip = h.idx("Hip")
legids = [j for j, n in enumerate(h.names) if "/Pelvis/" in n or n.endswith("/Pelvis")]
for i, p in enumerate(a["local"]):
    old = h.fk(p)
    stable = body_pose(a["hip_lean_rad"][i], 0.0)
    p[hip] = stable[hip]
    p[legids] = stable[legids]
    new = h.fk(p)
    p[waist] = np.linalg.inv(new[hip]) @ old[waist]
    final = h.fk(p)
    errors.append(
        np.max(
            np.abs(
                final[[h.idx(s + "_Hand") for s in "LR"]] - old[[h.idx(s + "_Hand") for s in "LR"]]
            )
        )
    )
    a["feet"][i] = final[[h.idx(s + "_Foot") for s in "LR"], :3, 3]
    drift.append(np.linalg.norm(a["feet"][i] - a["feet"][0], axis=1).max())
assert max(errors) < 1e-12 and max(drift) < 1e-6
np.savez_compressed(OUT / "human-animation.npz", **a)
print("STANCE_FIXED wrist_transform_error", max(errors), "foot_drift", max(drift), flush=True)
