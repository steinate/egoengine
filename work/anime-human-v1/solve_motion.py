"""Solve Amber's own hands and arms against the immutable episode contacts."""

import json, hashlib, time
import numpy as np
from scipy.optimize import least_squares, minimize_scalar
from scipy.interpolate import CubicSpline
from scipy.signal import savgol_filter
from scipy.spatial.transform import Rotation
from rig_model import *

old = np.load(B / "reference/human-animation.npz")
track = dict(np.load(B / "source/world-tracks.npz"))
N = len(old["source_frame"])
rig = Rig()
names = [n.split("/")[-1] for n in old["names"]]
Gref = old["local"].copy()
for j, p in enumerate(old["parents"]):
    Gref[:, j] = (old["world_transform"] if p < 0 else Gref[:, p]) @ old["local"][:, j]
hands = {s: Hand(rig, s) for s in ["L", "R"]}
results = {}
report = {}
start = time.time()
for side, hand in hands.items():
    W = Gref[:, names.index(side + "_Hand")]
    tips = []
    joints = []
    for f, length in zip(
        ["Thumb", "Index", "Mid", "Ring", "Pinky"], [0.023, 0.021, 0.023, 0.020, 0.017]
    ):
        ids = [names.index(side + "_" + f + str(k)) for k in [1, 2, 3]]
        points = Gref[:, ids][:, :, :3, 3]
        tip = points[:, -1] + Gref[:, ids[-1], :3, 1] * length
        tips.append(tip)
        joints.append(points)
    tips = np.stack(tips, axis=1)
    joints = np.stack(joints, axis=1)
    target = np.einsum("nji,nkj->nki", W[:, :3, :3], tips - W[:, None, :3, 3])
    nodes = np.einsum("nji,nfkj->nfki", W[:, :3, :3], joints - W[:, None, None, :3, 3])
    keys = np.unique(np.r_[np.arange(0, N, 4), N - 1, 137, 433, 621, 780, 1044, 1191, 1331])
    sol = []
    previous = np.r_[np.zeros(6), [0, 0, 0, 0.2, 0.2], np.tile([0, 0.3, 0.4], 4)]
    lo = np.r_[[-0.035] * 3, [-0.65] * 3, hand.lo]
    hi = np.r_[[0.035] * 3, [0.65] * 3, hand.hi]
    for frame in keys:
        goal = target[frame]
        goalnodes = nodes[frame]

        def residual(x):
            g, t = hand.fk(x[6:])
            R = rot(x[3:6])
            t = t @ R.T + x[:3]
            p = g[:, :, :3, 3] @ R.T + x[:3]
            return np.r_[
                (t - goal).ravel() * 400,
                (p - goalnodes).ravel() * 25,
                x[:3] * 8,
                x[3:6] * 0.2,
                (x[6:] - previous[6:]) * 0.08,
            ]

        fit = least_squares(
            residual,
            np.clip(previous, lo + 1e-7, hi - 1e-7),
            bounds=(lo, hi),
            max_nfev=100 if frame == 0 else 32,
            ftol=1e-6,
            xtol=1e-6,
        )
        previous = fit.x
        sol.append(previous.copy())
        if len(sol) % 80 == 0:
            print("HAND", side, frame, "elapsed", round(time.time() - start), flush=True)
    x = CubicSpline(keys, sol, axis=0, bc_type="natural")(np.arange(N))
    x = np.clip(savgol_filter(x, 13, 3, axis=0), lo, hi)
    wrist = []
    errs = []
    boneworld = []
    for i in range(N):
        H = W[i] @ transform(rot(x[i, 3:6]), x[i, :3])
        g, t = hand.fk(x[i, 6:])
        wrist.append(H)
        boneworld.append(H @ g)
        errs.append(np.linalg.norm(t @ H[:3, :3].T + H[:3, 3] - tips[i], axis=1))
    results[side + "_q"] = x[:, 6:]
    results[side + "_canonical_wrist_world"] = np.array(wrist)
    results[side + "_finger_world"] = np.array(boneworld)
    report[side] = {
        "max_tip_error_mm": float(np.max(errs) * 1000),
        "p95_tip_error_mm": float(np.percentile(errs, 95) * 1000),
    }

# The user explicitly permits the avatar support plane to differ from the
# table's base plane. Keep pelvis and spine upright at every frame, and solve
# reach by a fixed stand height/location and native clavicle/arm articulation.
root = transform(rot([0, 0, np.pi]), [0.10, -0.582, -0.465])
restworld = root @ rig.rest
foot_targets = {
    s: restworld[rig.idx("足首." + s), :3, 3] + np.array([-0.070 if s == "L" else 0.070, 0, 0.008])
    for s in hands
}


def body(lean):
    G = restworld.copy()
    for side, sign in [("L", -1), ("R", 1)]:
        j = rig.idx("肩." + side)
        rig.set(G, "肩." + side, rot([0, 0, sign * np.deg2rad(28)]) @ G[j, :3, :3])
    return G


targets = {
    s: results[s + "_canonical_wrist_world"] @ np.linalg.inv(hands[s].C) @ rig.rest[hands[s].wrist]
    for s in hands
}
lean = np.zeros(N)
allG = []
cam = []
errors = []
elbows = []
for i in range(N):
    G = body(lean[i])
    er = []
    es = []
    for side, sign in [("L", -1), ("R", 1)]:
        # Both PMX deform and control leg chains receive the same planted-foot solve.
        for suffix in ["", "D"]:
            rig.limb(
                G,
                [n + suffix + "." + side for n in ["足", "ひざ", "足首"]],
                foot_targets[side],
                np.array([sign * 0.16, -0.32, 0.08]),
            )
            rig.set(
                G,
                "足首" + suffix + "." + side,
                restworld[rig.idx("足首" + suffix + "." + side), :3, :3],
            )
        H = targets[side][i]
        S = G[rig.idx("腕." + side), :3, 3]
        pole = S + np.array([sign * 0.32, -0.28, -0.23])
        er.append(rig.limb(G, ["腕." + side, "ひじ." + side, "手首." + side], H[:3, 3], pole))
        # Share forearm pronation with original twist skinning bones.
        j = rig.idx("ひじ." + side)
        natural = G[rig.idx("手首." + side), :3, :3].copy()
        axis = unit(H[:3, 3] - G[j, :3, 3])
        q = Rotation.from_matrix(H[:3, :3] @ natural.T).as_quat()
        angle = 2 * np.arctan2(q[:3] @ axis, q[3])
        angle = (angle + np.pi) % (2 * np.pi) - np.pi
        for n, f in [("手捩1", 0.25), ("手捩2", 0.5), ("手捩3", 0.75), ("手捩", 0.75)]:
            k = rig.idx(n + "." + side)
            ax = unit(G[rig.idx("手首." + side), :3, 3] - G[k, :3, 3]) if n == "手捩" else axis
            rig.set(G, n + "." + side, rot(ax * angle * f) @ G[k, :3, :3])
        rig.set(G, "手首." + side, H[:3, :3])
        for f in range(5):
            for k in range(3):
                j = hands[side].ids[f, k]
                rig.set(G, rig.names[j], results[side + "_finger_world"][i, f, k, :3, :3])
        # Elbow auxiliary skinning follows half the bend rather than its disabled
        # PMX append-rotation constraint.
        j = rig.idx("ひじ." + side)
        u = rig.idx("腕." + side)
        D = G[j, :3, :3] @ rig.rest[j, :3, :3].T
        U = G[u, :3, :3] @ rig.rest[u, :3, :3].T
        mid = U @ rot(Rotation.from_matrix(U.T @ D).as_rotvec() * 0.5)
        rig.set(G, "ひじ補助." + side, mid @ rig.rest[rig.idx("ひじ補助." + side), :3, :3])
        es.append(G[j, :3, 3].copy())
    # Keep a visible face and a stable head-relative right axis. Looking almost
    # straight down must never flip ego roll by 180 degrees when eye Y crosses
    # the object's Y. Head pitch is capped; eyes provide the remaining gaze.
    head = rig.idx("頭")
    pos = G[head, :3, 3]
    pitch = np.deg2rad(25.0)
    direction = np.array([0, np.cos(pitch), -np.sin(pitch)])
    headD = align(root[:3, :3] @ np.array([0, -1, 0]), direction) @ root[:3, :3]
    rig.set(G, "頭", headD @ rig.rest[head, :3, :3])
    # Original long-hair chains retain gravity-oriented rest directions rather
    # than sticking upward with the neck; their root attachment remains native.
    for hair in ["スカート_0_1", "tf_0_1"]:
        j = rig.idx(hair)
        rig.set(G, hair, rot([-0.05, 0, 0]) @ root[:3, :3] @ rig.rest[j, :3, :3])
    eye = (G[rig.idx("目.L"), :3, 3] + G[rig.idx("目.R"), :3, 3]) * 0.5 + direction * 0.025
    z = unit(eye - np.array([0, -0.16, 0.84]))
    right = np.array([1.0, 0, 0])
    up = unit(np.cross(z, right))
    right = np.cross(up, z)
    cam.append(transform(np.stack([right, up, z], 1), eye))
    allG.append(G)
    errors.append(er)
    elbows.append(es)
allG = np.array(allG)
errors = np.array(errors)
assert np.isfinite(allG).all()
results.update(
    bone_world=allG,
    camera_world_usd=np.array(cam),
    source_frame=old["source_frame"],
    video_time_s=old["video_time_s"],
    torso_lean_rad=lean,
    avatar_root_world=root,
    nominal_support_plane_z_m=np.array(-0.4664),
    arm_reach_error_m=errors,
    elbows=np.array(elbows),
    names=rig.names,
    parents=rig.parents,
    rest=rig.rest,
)
for k, v in track.items():
    results[k] = v
np.savez_compressed(B / "anime-animation.npz", **results)
report.update(
    frames=N,
    fps=15,
    torso_lean_degrees=0.0,
    avatar_root_world=root.tolist(),
    nominal_support_plane_z_m=-0.4664,
    uniform_model_scale=SCALE,
    max_arm_reach_error_m=float(errors.max()),
    source_world_tracks_sha256=hashlib.sha256(
        (B / "source/world-tracks.npz").read_bytes()
    ).hexdigest(),
    method="Native PMX hand FK with bounded finger IK and spatial contact targets; native two-bone arms with outward poles, strictly upright fixed pelvis/spine, lower independent support plane, planted feet. No robot joint angles.",
    dynamics="Exact original object pose replay; this is a paired visual demonstration, not a new human-driven physics rollout.",
)
(B / "ik-report.json").write_text(json.dumps(report, indent=2))
print("DONE", json.dumps(report), flush=True)
