"""Refit finger closure around each cube with a neutral-wrist palm frame."""

from arm_model import *

a = np.load(OUT / "human-animation.npz")
h.world = a["world_transform"]
result = {}
report = {}
for si, side in enumerate(["L", "R"]):
    t = timing["left" if side == "L" else "right"]
    frames = np.linspace(t["grasp"] + 10, t["release"] - 10, 12, dtype=int)
    relative = []
    for i in frames:
        p = a["local"][i].copy()
        q = a["arm_q"][i, si].copy()
        q[7] = 0.0
        q[8] *= 0.65
        hand = h.idx(side + "_Hand")
        p[hand, :3, :3] = h.rest[hand, :3, :3] @ rot(1, q[6]) @ rot(0, q[7]) @ rot(2, q[8])
        g = h.fk(p)
        relative.append(np.linalg.inv(track[t["object"] + "_world"][i]) @ g[hand])
    preferred_R = Rotation.from_matrix(np.array(relative)[:, :3, :3]).mean().as_matrix()
    oldH, oldf, _ = fits[side]
    tips, _ = handpoints(side, oldf, oldH)
    origin = oldH[:3, 3]

    def unpack(x):
        H = np.eye(4)
        H[:3, :3] = preferred_R @ Rotation.from_rotvec(x[3:6]).as_matrix()
        H[:3, 3] = x[:3]
        return H

    def residual(x):
        current, points = handpoints(side, x[6:], unpack(x))
        q = np.abs(points) - 0.029
        sdf = np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(1), 0)
        return np.r_[
            (current - tips).ravel() * 350,
            np.maximum(0.005 - sdf, 0) * 180,
            np.maximum(-0.020 - points[:, 2], 0) * 200,
            (x[:3] - origin) * 3,
            x[3:6] * 3,
            (x[6:] - oldf) * 0.20,
        ]

    lower = np.r_[
        [-0.10, -0.15, 0.035], [-0.22, -0.22, -0.22], [-1, -1.3, -1, 0, 0], np.tile([-0.4, 0, 0], 4)
    ]
    upper = np.r_[
        [0.10, 0.035, 0.15],
        [0.22, 0.22, 0.22],
        [1, 1.3, 1.5, 1.6, 1.5],
        np.tile([0.4, 1.7, 1.9], 4),
    ]
    fit = least_squares(
        residual, np.r_[origin, [0, 0, 0], oldf], bounds=(lower, upper), max_nfev=450
    )
    H = unpack(fit.x)
    result[side + "_H"] = H
    result[side + "_f"] = fit.x[6:]
    newtips, _ = handpoints(side, fit.x[6:], H)
    report[side] = {
        "wrist_relative_m": H[:3, 3].tolist(),
        "max_fingertip_error_m": float(np.linalg.norm(newtips - tips, axis=1).max()),
        "palm_change_deg": float(
            np.rad2deg(Rotation.from_matrix(oldH[:3, :3].T @ H[:3, :3]).magnitude())
        ),
    }
    print("REFIT", side, report[side], flush=True)
np.savez_compressed(OUT / "grasp-refit.npz", **result)
(OUT / "grasp-refit.json").write_text(json.dumps(report, indent=2))
