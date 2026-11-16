"""Object-locked native Worker IK for validated, newly planned task episodes."""

import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation, Slerp

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("root", type=Path)
p.add_argument("episode", type=Path)
p.add_argument("--grasp-roll", type=float, default=0.0)
p.add_argument("--output", default="human")
a = p.parse_args()
root = a.root.resolve()
ep = a.episode.resolve()
assert Path(a.output).name == a.output
out = ep / a.output
out.mkdir(exist_ok=True)
sys.path.insert(0, str(root / "human41"))
from human_control import Human
from worker import Arm, rot, smooth, fingers, tip_local, IDLE, CLOSED, FINGER_LOW, FINGER_HIGH
from pxr import Usd, UsdGeom

result = json.loads((ep / "result.json").read_text())
assert result["official_success"] and result["cadence_valid"], result
assert json.loads((ep / "source-validation.json").read_text())["passed"]
track = dict(np.load(ep / "source/world-tracks.npz"))
meta = json.loads((ep / "source/scene-meta.json").read_text())
events = json.loads((ep / "source/events.json").read_text())
prov = json.loads((ep / "task-provenance.json").read_text())
N = len(track["time_s"])
fps = 1 / np.median(np.diff(track["time_s"]))
task = ep.parent.name
h = Human()
body = h.rest.copy()
contacts = {}


def phaseframes(side, skill, command):
    return [
        e["frame"]
        for e in events
        for z in e["phase"]
        if z["side"] == side and z["skill"] == skill and z["command"] == command
    ]


for side in prov["active"]:
    lr = {"L": "left", "R": "right"}[side]
    name = prov["object"]
    if task == "close_microwave":
        angles = track[name + "_joints"][:, 0]
        moving = np.where(np.abs(angles - angles[0]) > 0.012)[0]
        assert len(moving), "Door never moved"
        grasp = max(0, int(moving[0]) - 5)
        release = int(np.argmin(angles))
        path = meta["objects"][name]["object_link_path"]
        if not path.startswith("/"):
            path = meta["objects"][name]["prim_path"] + "/" + path
        matrices = track["prim_world"][:, meta["prim_paths"].index(path)]
    else:
        grasp = phaseframes(lr, "Pick", "attach_obj")[0]
        releases = phaseframes(lr, "Place", "open_gripper") + phaseframes(
            lr, "Gripper_Action", "open_gripper"
        )
        release = min(x for x in releases if x > grasp)
        path = meta["objects"][name]["prim_path"]
        matrices = track[name + "_world"]
    # World matrices retain object scale; remove it only for the rigid contact frame.
    rigid = matrices.copy()
    rigid[:, :3, :3] /= np.linalg.norm(rigid[:, :3, :3], axis=1)[:, None, :]
    open_frame = release
    # Events describe the command applied before this recorded physics frame.
    # A release impulse already present in that frame must not drive the hand.
    if task != "close_microwave" and release > grasp:
        delta_angle = Rotation.from_matrix(
            rigid[release - 1, :3, :3].T @ rigid[release, :3, :3]
        ).magnitude()
        delta_position = np.linalg.norm(rigid[release, :3, 3] - rigid[release - 1, :3, 3])
        if delta_angle > np.deg2rad(15) or delta_position > 0.03:
            release -= 1
    contacts[side] = dict(
        grasp=grasp, release=release, open_command_frame=open_frame, path=path, matrices=rigid
    )

stage = Usd.Stage.Open(str(ep / "source/scene.usdc"))


def vertices(path, frame):
    pts = []
    for pr in Usd.PrimRange(stage.GetPrimAtPath(path)):
        if not pr.IsA(UsdGeom.Mesh):
            continue
        v = np.asarray(UsdGeom.Mesh(pr).GetPointsAttr().Get())
        if not len(v):
            continue
        ancestor = max(
            [
                x
                for x in meta["prim_paths"]
                if str(pr.GetPath()).startswith(x + "/") or str(pr.GetPath()) == x
            ],
            key=len,
        )
        A = np.asarray(
            UsdGeom.Xformable(stage.GetPrimAtPath(ancestor)).ComputeLocalToWorldTransform(
                Usd.TimeCode.Default()
            )
        ).T
        M = np.asarray(UsdGeom.Xformable(pr).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T
        W = track["prim_world"][frame, meta["prim_paths"].index(ancestor)] @ np.linalg.inv(A) @ M
        pts.append(v @ W[:3, :3].T + W[:3, 3])
    assert pts, path
    v = np.concatenate(pts)
    return v[:: max(1, len(v) // 8000)]


fits = {}
for side, c in contacts.items():
    sign = 1 if side == "R" else -1
    frame = c["grasp"]
    cloud = vertices(c["path"], frame)
    tcp = track[side + "_tcp_world"][frame, :3, 3]
    # The robot TCP locates the grasp region only. Human bones/finger angles are independent.
    nearest = cloud[np.linalg.norm(cloud - tcp, axis=1).argsort()[: min(200, len(cloud))]]
    center = nearest.mean(0)
    R = rot(2, sign * 0.35) @ rot(0, -0.5) @ np.array([[0, 0, -sign], [0, 1, 0], [sign, 0, 0.0]])
    if a.grasp_roll:
        axis = c["matrices"][frame, :3, 1]
        R = Rotation.from_rotvec(axis * np.deg2rad(a.grasp_roll)).as_matrix() @ R
    f0 = IDLE.copy() if task == "close_microwave" else CLOSED.copy()
    tips = tip_local(h, side, f0)
    origin = center - (tips @ R.T).mean(0)
    tree = cKDTree(cloud)
    initial_tips = tips @ R.T + origin
    # Fixed opposing landmarks keep the fingers spread instead of collapsing onto one vertex.
    targets = cloud[tree.query(initial_tips)[1]]

    def unpack(x):
        H = np.eye(4)
        H[:3, :3] = R @ Rotation.from_rotvec(x[3:6]).as_matrix()
        H[:3, 3] = x[:3]
        return H

    def residual(x):
        H = unpack(x)
        ts = tip_local(h, side, x[6:]) @ H[:3, :3].T + H[:3, 3]
        return np.r_[
            (ts - targets).ravel() * 220, (x[:3] - origin) * 15, x[3:6] * 1.5, (x[6:] - f0) * 0.6
        ]

    fit = least_squares(
        residual,
        np.r_[origin, np.zeros(3), f0],
        bounds=(
            np.r_[origin - 0.06, [-0.5] * 3, FINGER_LOW],
            np.r_[origin + 0.06, [0.5] * 3, FINGER_HIGH],
        ),
        max_nfev=100,
    )
    H = unpack(fit.x)
    lock = np.linalg.inv(c["matrices"][frame]) @ H
    fits[side] = (H, fit.x[6:], lock)
    c["fit_tip_error_m"] = float(
        np.max(
            np.linalg.norm(tip_local(h, side, fit.x[6:]) @ H[:3, :3].T + H[:3, 3] - targets, axis=1)
        )
    )
    print("CONTACT_FIT", side, frame, c["release"], c["fit_tip_error_m"], flush=True)

# Select a fixed upright stance using the whole carry range, not robot geometry.
alltargets = np.concatenate(
    [
        (c["matrices"][c["grasp"] : c["release"] + 1] @ fits[s][2])[:, :3, 3]
        for s, c in contacts.items()
    ]
)
center = alltargets.mean(0)
candidates = []
table_path = meta["robot_root"].rsplit("/", 1)[0] + "/table"
table_box = (
    UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
    .ComputeWorldBound(stage.GetPrimAtPath(table_path))
    .ComputeAlignedBox()
)
front_limit = float(table_box.GetMin()[1]) - 0.12
for yaw in [-45, -30, -15, 0, 15, 30, 45]:
    for back in [0.22, 0.30, 0.38]:
        for height in [0.02, 0.10, 0.18, 0.26]:
            h.world[:3, :3] = rot(2, np.deg2rad(yaw)) @ np.diag([-1.0, -1.0, 1.0])
            h.world[:3, 3] = 0
            g = h.fk(body)
            shoulder_center = np.mean([g[h.idx(s + "_Upperarm"), :3, 3] for s in contacts], axis=0)
            h.world[:3, 3] = center + [0, -back, height] - shoulder_center
            h.world[1, 3] = min(h.world[1, 3], front_limit)
            g = h.fk(body)
            cost = 0.0
            for s, c in contacts.items():
                ts = (c["matrices"][c["grasp"] : c["release"] + 1 : 10] @ fits[s][2])[:, :3, 3]
                S = g[h.idx(s + "_Upperarm"), :3, 3]
                ds = np.linalg.norm(ts - S, axis=1)
                length = sum(
                    np.linalg.norm(h.rest[h.idx(s + "_" + n), :3, 3]) for n in ["Forearm", "Hand"]
                )
                cost += np.sum(np.maximum(ds - length + 0.04, 0) ** 2) * 100 + np.mean(
                    (ds - 0.35) ** 2
                )
            candidates.append((cost, h.world.copy()))
ranked = []
unique = {tuple(np.round(W.ravel(), 8)): (cost, W) for cost, W in candidates}
for _, W in sorted(unique.values(), key=lambda x: x[0])[:20]:
    h.world = W
    score = 0.0
    for s, c in contacts.items():
        arm = Arm(h, s, body)
        for frame in np.linspace(c["grasp"], c["release"], 5, dtype=int):
            H = c["matrices"][frame] @ fits[s][2]
            q, (_, g) = arm.solve(H)
            score += np.linalg.norm(g[-1, :3, 3] - H[:3, 3]) ** 2 * 1500**2
            score += Rotation.from_matrix(H[:3, :3].T @ g[-1, :3, :3]).magnitude() ** 2 * 35**2
            score += np.sum(q[7:9] ** 2)
    ranked.append((score, W.copy()))
h.world = min(ranked, key=lambda x: x[0])[1]
print("STANCE_SELECTED", min(x[0] for x in ranked), h.world.tolist(), flush=True)
arms = {s: Arm(h, s, body) for s in ["L", "R"]}
rest = {}
for s, arm in arms.items():
    sign = arm.sign
    g = h.fk(body)
    H = np.eye(4)
    H[:3, :3] = (
        rot(2, sign * 0.2) @ rot(0, -0.35) @ np.array([[0, 0, -sign], [0, 1, 0], [sign, 0, 0.0]])
    )
    H[:3, 3] = (
        g[h.idx(s + "_Upperarm"), :3, 3]
        + sign * 0.07 * arm.right
        + 0.16 * arm.forward
        + [0, 0, -0.36]
    )
    rest[s] = H


def blend(A, B, u):
    u = float(smooth(u))
    H = np.eye(4)
    H[:3, 3] = (1 - u) * A[:3, 3] + u * B[:3, 3]
    H[:3, :3] = Slerp([0, 1], Rotation.from_matrix(np.array([A[:3, :3], B[:3, :3]])))(u).as_matrix()
    return H


def target(s, i):
    if s not in contacts:
        return rest[s], IDLE
    c = contacts[s]
    gr, re = c["grasp"], c["release"]
    begin = max(0, gr - int(2.5 * fps))
    end = min(N - 1, re + int(2 * fps))
    H0, f, lock = fits[s]
    H = c["matrices"][i] @ lock
    if i < gr:
        u = (i - begin) / max(gr - begin, 1)
        return blend(rest[s], H, u), IDLE + (f - IDLE) * smooth(
            (i - (gr - int(0.6 * fps))) / max(0.6 * fps, 1)
        )
    if i <= re:
        return H, f
    u = (i - re) / max(end - re, 1)
    released = c["matrices"][re] @ lock
    return blend(released, rest[s], u), f + (IDLE - f) * smooth((i - re) / max(0.5 * fps, 1))


poses = []
targets = []
qs = []
fs = []
errors = []
cameras = []
elbows = []
feet = []
history = {s: [] for s in arms}
for i in range(N):
    pose = body.copy()
    frameq = []
    framef = []
    frameH = []
    frameerrors = []
    for s, arm in arms.items():
        H, f = target(s, i)
        hist = history[s]
        q, (_, g) = arm.solve(H, hist[-1] if hist else None, hist[-2] if len(hist) > 1 else None)
        hist.append(q)
        pose = arm.apply(q, pose)
        pose = fingers(h, s, f, pose)
        frameq.append(q)
        framef.append(f)
        frameH.append(H)
        frameerrors.append(
            [
                np.linalg.norm(g[-1, :3, 3] - H[:3, 3]),
                Rotation.from_matrix(H[:3, :3].T @ g[-1, :3, :3]).magnitude(),
            ]
        )
    g = h.fk(pose)
    eye = g[[h.idx("L_Eye"), h.idx("R_Eye")], :3, 3].mean(0)
    z = eye - center
    z /= np.linalg.norm(z)
    x = np.cross([0, 0, 1], z)
    x /= np.linalg.norm(x)
    C = np.eye(4)
    C[:3, :3] = np.stack([x, np.cross(z, x), z], axis=1)
    C[:3, 3] = eye - z * 0.018
    poses.append(pose)
    targets.append(frameH)
    qs.append(frameq)
    fs.append(framef)
    errors.append(frameerrors)
    cameras.append(C)
    elbows.append(g[[h.idx("L_Forearm"), h.idx("R_Forearm")], :3, 3])
    feet.append(g[[h.idx("L_Foot"), h.idx("R_Foot")], :3, 3])
    if i % 100 == 0:
        print("IK", i, N, "max_error", np.max(np.asarray(errors)[:, :, 0]), flush=True)
np.savez_compressed(
    out / "human-animation.npz",
    **track,
    local=poses,
    world_transform=h.world,
    names=h.names,
    parents=h.parents,
    wrist_targets=targets,
    arm_q=qs,
    finger_q=fs,
    ik_errors=errors,
    camera_world_usd=cameras,
    elbows=elbows,
    feet=feet,
    source_frame=np.arange(N),
    video_time_s=track["time_s"],
)
report = dict(
    grasp_roll_degrees=a.grasp_roll,
    frames=N,
    fps=float(fps),
    source_sha256=hashlib.sha256((ep / "source/world-tracks.npz").read_bytes()).hexdigest(),
    max_wrist_position_error_m=float(np.max(np.asarray(errors)[:, :, 0])),
    max_wrist_orientation_error_deg=float(np.rad2deg(np.max(np.asarray(errors)[:, :, 1]))),
    stance_world=h.world.tolist(),
    contacts={s: {k: v for k, v in c.items() if k != "matrices"} for s, c in contacts.items()},
    method="Native Worker fixed upright stance, independent anatomical arm/finger IK; object-local contact locks; source object poses/time unchanged; visual replay, no human dynamics",
)
(out / "retarget-report.json").write_text(json.dumps(report, indent=2))
print("HUMAN_DONE", report, flush=True)
