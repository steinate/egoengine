"""Human-constrained IK with source-rig twist conventions and planted feet."""

import argparse
from contact_plan import *

parser = argparse.ArgumentParser()
parser.add_argument("--keys", action="store_true")
args = parser.parse_args()
ref = base.copy()
reference = h.fk(ref)
restworld = h.fk(h.rest)


# Source character motions use shoulder twist compensation and half hand
# pronation on ForearmTwist02. Keep the primary forearm an elbow hinge.
def axial_y(R):
    q = Rotation.from_matrix(R).as_quat()
    return 2 * np.arctan2(q[1], q[3])


def body_pose(lean):
    p = ref.copy()
    j = h.idx("Hip")
    p[j, :3, :3] = reference[h.parents[j], :3, :3].T @ rot(0, -lean) @ reference[j, :3, :3]
    for side, sign in [("L", -1), ("R", 1)]:
        p, _ = chain(
            p,
            [side + "_Thigh", side + "_Calf", side + "_Foot"],
            np.array([sign * 0.14, -0.72, 0.060]),
            np.array([sign * 0.15, -0.52, 0.48]),
        )
        g = h.fk(p)
        j = h.idx(side + "_Foot")
        p[j, :3, :3] = g[h.parents[j], :3, :3].T @ restworld[j, :3, :3]
        for limb in ["Thigh", "Calf"]:
            j = h.idx(side + "_" + limb)
            twist = axial_y(h.rest[j, :3, :3].T @ p[j, :3, :3])
            for suffix, mult in [("Twist01", -0.5), ("Twist02", 0.5)]:
                k = h.idx(side + "_" + limb + suffix)
                p[k, :3, :3] = h.rest[k, :3, :3] @ rot(1, mult * twist)
    for name, pitch in [("NeckTwist01", -0.35), ("Head", -0.60)]:
        g = h.fk(p)
        j = h.idx(name)
        p[j, :3, :3] = g[h.parents[j], :3, :3].T @ rot(0, pitch) @ restworld[j, :3, :3]
    return p


keys = np.array(
    [0, 90, 137, 179, 300, 433, 500, 621, 720, 780, 818, 930, 1044, 1120, 1191, 1331, 1431, N - 1]
)
leans = np.deg2rad([20, 35, 45, 35, 35, 43, 22, 22, 35, 47, 38, 32, 35, 28, 32, 45, 32, 32])


def lean_at(i):
    k = min(np.searchsorted(keys, i, side="right") - 1, len(keys) - 2)
    u = smooth((i - keys[k]) / (keys[k + 1] - keys[k]))
    return leans[k] * (1 - u) + leans[k + 1] * u


lo = np.r_[[-0.22, -0.22], [-2.7, -2.7, -2.7], 0.10, -1.70, -0.40, -0.95]
hi = np.r_[[0.22, 0.22], [2.7, 2.7, 2.7], 2.50, 1.70, 0.40, 0.95]


def pose_q(side, p):
    d = lambda n: h.rest[h.idx(side + "_" + n), :3, :3].T @ p[h.idx(side + "_" + n), :3, :3]
    return np.clip(
        np.r_[
            0,
            0,
            Rotation.from_matrix(d("Upperarm")).as_rotvec(),
            Rotation.from_matrix(d("Forearm")).as_rotvec()[0],
            Rotation.from_matrix(d("Hand")).as_euler("YXZ"),
        ],
        lo + 1e-6,
        hi - 1e-6,
    )


priors = {s: np.array([pose_q(s, p) for p in h.priors]) for s in ["L", "R"]}
seed_cache = {}


class Arm:
    def __init__(self, side, p):
        self.side = side
        self.sign = 1 if side == "R" else -1
        self.ids = [h.idx(side + "_" + n) for n in ["Clavicle", "Upperarm", "Forearm", "Hand"]]
        g = h.fk(p)
        self.parent = g[h.parents[self.ids[0]]]
        self.parts = [p[self.ids[0]].copy()] + [h.rest[j].copy() for j in self.ids[1:]]

    def fk(self, q):
        p = [x.copy() for x in self.parts]
        p[0][:3, :3] = self.parts[0][:3, :3] @ rot(0, q[0]) @ rot(2, q[1])
        p[1][:3, :3] = self.parts[1][:3, :3] @ Rotation.from_rotvec(q[2:5]).as_matrix()
        p[2][:3, :3] = self.parts[2][:3, :3] @ rot(0, q[5])
        p[3][:3, :3] = self.parts[3][:3, :3] @ rot(1, q[6]) @ rot(0, q[7]) @ rot(2, q[8])
        g = []
        T = self.parent
        for v in p:
            T = T @ v
            g.append(T)
        return p, np.array(g)

    def solve(self, H, prev=None):
        candidates = priors[self.side]
        if self.side not in seed_cache:
            seed_cache[self.side] = np.array(
                [(np.linalg.inv(self.parent) @ self.fk(q)[1][-1])[:3, 3] for q in candidates]
            )
        seed_positions = seed_cache[self.side] @ self.parent[:3, :3].T + self.parent[:3, 3]
        dist = np.linalg.norm(seed_positions - H[:3, 3], axis=1)
        rank = np.argsort(dist)
        prior = candidates[rank[0]]
        previous = prior if prev is None else prev

        def residual(q):
            _, g = self.fk(q)
            W = g[3]
            S = g[1, :3, 3]
            E = g[2, :3, 3]
            return np.r_[
                (W[:3, 3] - H[:3, 3]) * 500,
                Rotation.from_matrix(H[:3, :3].T @ W[:3, :3]).as_rotvec() * 20,
                (q - prior) * np.array([0.8, 0.8, 0.12, 0.12, 0.12, 0.1, 0.08, 0.25, 0.2]),
                (q - previous) * 0.25,
                max(0, S[1] - 0.045 - E[1]) * 45,
                max(0, self.sign * (S[0] - E[0]) - 0.055) * 40,
                max(0, E[2] - S[2] + 0.03) * 35,
            ]

        seeds = [previous]
        if prev is None:
            seeds.extend(candidates[rank[:5]])
        results = [
            least_squares(
                residual,
                np.clip(q, lo + 1e-6, hi - 1e-6),
                bounds=(lo, hi),
                max_nfev=100,
                ftol=1e-7,
                xtol=1e-7,
            )
            for q in seeds
        ]
        best = min(results, key=lambda x: x.cost)
        if np.linalg.norm(self.fk(best.x)[1][-1, :3, 3] - H[:3, 3]) > 0.004:
            results.extend(
                least_squares(
                    residual, candidates[k], bounds=(lo, hi), max_nfev=100, ftol=1e-7, xtol=1e-7
                )
                for k in rank[:3]
            )
            best = min(results, key=lambda x: x.cost)
        return best.x, self.fk(best.x)


samples = (
    [0, 137, 433, 620, 780, 930, 1044, 1161, 1331, 1431, N - 1] if args.keys else list(range(N))
)
poses = []
targets = []
params = []
errors = []
cameras = []
elbows = []
feet = []
previous = {s: None for s in ["L", "R"]}
deviations = []
for i in samples:
    p = body_pose(lean_at(i))
    body = h.fk(p)
    # Resting hand follows the shoulder as the body leans; it is not pinned
    # behind the torso at a robot-style standby position.
    for s, sign in [("L", -1), ("R", 1)]:
        shoulder = body[h.idx(s + "_Upperarm"), :3, 3]
        rests[s] = fits[s][0].copy()
        rests[s][:3, 3] = shoulder + [sign * 0.065, 0.14, -0.39]
        rests[s][:3, :3] = (
            rot(2, sign * 0.15)
            @ rot(0, -0.40)
            @ np.array([[0, 0, -sign], [0, 1, 0], [sign, 0, 0.0]])
        )
    frameq = []
    frameH = []
    frameerr = []
    for side in ["L", "R"]:
        H, f = schedule(side, i)
        arm = Arm(side, p)
        q, (parts, g) = arm.solve(H, previous[side])
        previous[side] = q
        p[arm.ids] = parts
        p = fingers(side, f, p)
        twist = axial_y(
            h.rest[h.idx(side + "_Upperarm"), :3, :3].T @ p[h.idx(side + "_Upperarm"), :3, :3]
        )
        for n, angle in [
            ("UpperarmTwist01", -0.5 * twist),
            ("UpperarmTwist02", 0.5 * twist),
            ("ForearmTwist01", 0.0),
            ("ForearmTwist02", 0.5 * q[6]),
        ]:
            j = h.idx(side + "_" + n)
            p[j, :3, :3] = h.rest[j, :3, :3] @ rot(1, angle)
        frameq.append(q)
        frameH.append(H)
        frameerr.append(
            [
                np.linalg.norm(g[-1, :3, 3] - H[:3, 3]),
                Rotation.from_matrix(H[:3, :3].T @ g[-1, :3, :3]).magnitude(),
            ]
        )
    g = h.fk(p)
    eye = (g[h.idx("L_Eye"), :3, 3] + g[h.idx("R_Eye"), :3, 3]) / 2
    target = np.array([eye[0], -0.12, 0.84])
    forward = unit(target - eye)
    eye += forward * 0.018
    z = -forward
    x = unit(np.cross([0, 0, 1], z))
    y = np.cross(z, x)
    C = np.eye(4)
    C[:3, :3] = np.stack([x, y, z], 1)
    C[:3, 3] = eye
    poses.append(p)
    targets.append(frameH)
    params.append(frameq)
    errors.append(frameerr)
    cameras.append(C)
    elbows.append(g[[h.idx("L_Forearm"), h.idx("R_Forearm")], :3, 3])
    feet.append(g[[h.idx("L_Foot"), h.idx("R_Foot")], :3, 3])
    if args.keys or i % 50 == 0:
        print(
            "IK",
            i,
            "lean_deg",
            np.rad2deg(lean_at(i)),
            "errors_mm_deg",
            np.array(frameerr) * [1000, 180 / np.pi],
            "q_deg",
            np.round(np.rad2deg(np.array(frameq)[:, 5:]), 1),
            flush=True,
        )
np.savez_compressed(
    OUT / ("key-animation.npz" if args.keys else "human-animation.npz"),
    local=np.array(poses),
    world_transform=h.world,
    names=h.names,
    parents=h.parents,
    source_frame=np.array(samples),
    video_time_s=np.array(samples) / 15,
    wrist_targets=np.array(targets),
    arm_q=np.array(params),
    ik_errors=np.array(errors),
    camera_world_usd=np.array(cameras),
    elbows=np.array(elbows),
    feet=np.array(feet),
    hip_lean_rad=np.array([lean_at(i) for i in samples]),
    **{k: (v[samples] if k.endswith("_world") else v) for k, v in track.items()},
)
report = {
    "frames": len(samples),
    "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
    "max_wrist_position_error_m": float(np.max(np.array(errors)[:, :, 0])),
    "max_wrist_orientation_error_deg": float(np.max(np.array(errors)[:, :, 1]) * 180 / np.pi),
    "joint_limits_degrees": {
        "elbow": [np.rad2deg(lo[5]), np.rad2deg(hi[5])],
        "pronation": [-97.4, 97.4],
        "wrist_deviation": [-22.92, 22.92],
        "wrist_flexion": [-54.43, 54.43],
    },
    "source_rig_twist": "UpperarmTwist01/02 = -/+ half humerus axial twist; Forearm is pure elbow hinge, ForearmTwist01 zero and Twist02 half hand pronation, matching supplied mocap conventions",
    "body": "Pelvis lowered 1 cm instead of 21 cm, fixed planted feet, phase-smooth hip hinge",
    "fits": {s: fits[s][2] for s in fits},
    "tray_fits": {s: trayfits[s][2] for s in trayfits},
}
(OUT / ("key-report.json" if args.keys else "retarget-report.json")).write_text(
    json.dumps(report, indent=2)
)
print(
    "OPTIMIZATION_DONE",
    report["max_wrist_position_error_m"],
    report["max_wrist_orientation_error_deg"],
    flush=True,
)
