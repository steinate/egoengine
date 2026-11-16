"""Fit native Amber fingers to task geometry and follow episode contact events.

No previous human animation or robot joint-angle retargeting is used. The rigid
object arrays are read-only; these contacts drive a visual human replay.
"""

import json
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation, Slerp
from rig_model import Hand


def axis_rotation(axis, angle):
    v = np.zeros(3)
    v[axis] = angle
    return Rotation.from_rotvec(v).as_matrix()


def smooth(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * u * (10 + u * (-15 + 6 * u))


def handpoints(hand, q, H):
    joints, tips = hand.fk(q)
    tips = tips @ H[:3, :3].T + H[:3, 3]
    nodes = joints[:, :, :3, 3] @ H[:3, :3].T + H[:3, 3]
    samples = []
    for f in range(5):
        points = np.concatenate([nodes[f], tips[f : f + 1]], axis=0)
        for a, b in zip(points[:-1], points[1:]):
            samples.extend(a + (b - a) * u for u in [0.0, 0.33, 0.66, 1.0])
    return tips, np.asarray(samples)


def fit_cube(hand):
    side = hand.side
    s = 1 if side == "R" else -1
    R = (
        axis_rotation(2, s * 0.35)
        @ axis_rotation(0, -0.50)
        @ np.array([[0, 0, -s], [0, 1, 0], [s, 0, 0.0]])
    )
    targets = np.array(
        [
            [-0.036, -0.008, 0.002],
            [-0.018, 0.036, 0.001],
            [0.004, 0.036, -0.003],
            [0.023, 0.034, -0.001],
            [0.034, 0.022, 0.004],
        ]
    )
    targets[:, 0] *= s
    targets = targets @ axis_rotation(2, s * 0.35).T
    targets[:, :2] *= (0.036 / np.max(np.abs(targets[:, :2]), axis=1))[:, None]
    f0 = np.r_[0.0, 0.25, 0.35, 0.6, 0.5, np.tile([0.0, 0.65, 1.0], 4)]
    origin = np.array([s * 0.025, -0.080, 0.110])
    lo = np.r_[
        [-0.065, -0.14, 0.045],
        [-0.3, -0.3, -0.3],
        [-1.0, -1.3, -1.0, 0, 0],
        np.tile([-0.4, 0, 0], 4),
    ]
    hi = np.r_[
        [0.065, -0.015, 0.14],
        [0.3, 0.3, 0.3],
        [1.0, 1.3, 1.5, 1.6, 1.5],
        np.tile([0.4, 1.7, 1.9], 4),
    ]

    def unpack(x):
        H = np.eye(4)
        H[:3, :3] = R @ Rotation.from_rotvec(x[3:6]).as_matrix()
        H[:3, 3] = x[:3]
        return H

    def residual(x):
        tips, pts = handpoints(hand, x[6:], unpack(x))
        q = np.abs(pts) - 0.029
        sdf = np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(1), 0)
        return np.r_[
            (tips - targets).ravel() * 250,
            np.maximum(0.006 - sdf, 0) * 190,
            np.maximum(-0.021 - pts[:, 2], 0) * 200,
            (x[:3] - origin) * 4,
            x[3:6] * 0.2,
            (x[6:] - f0) * 0.12,
        ]

    lo[6:] = hand.lo
    hi[6:] = hand.hi
    f0 = np.clip(f0, hand.lo + 1e-6, hand.hi - 1e-6)
    best = least_squares(residual, np.r_[origin, [0, 0, 0], f0], bounds=(lo, hi), max_nfev=320)
    H = unpack(best.x)
    tips, pts = handpoints(hand, best.x[6:], H)
    print(
        "CUBE_FIT",
        side,
        "wrist",
        H[:3, 3],
        "tiperr",
        np.linalg.norm(tips - targets, axis=1),
        flush=True,
    )
    return (
        H,
        best.x[6:],
        {"tip_error_m": np.linalg.norm(tips - targets, axis=1).tolist(), "wrist": H.tolist()},
    )


def fit_tray(hand):
    side = hand.side
    s = 1 if side == "R" else -1
    R = (
        axis_rotation(2, s * np.pi / 4)
        @ axis_rotation(0, -0.50)
        @ np.array([[0, 0, -s], [0, 1, 0], [s, 0, 0.0]])
    )
    targets = np.array(
        [
            [0.165, -0.028, 0.010],
            [0.136, -0.025, 0.008],
            [0.136, 0, 0.008],
            [0.136, 0.024, 0.008],
            [0.137, 0.042, 0.008],
        ]
    )
    targets[:, 0] *= s
    origin = np.array([s * 0.215, -0.065, 0.105])
    f0 = np.r_[0.0, 0.25, 0.35, 0.6, 0.5, np.tile([0.0, 0.8, 1.1], 4)]
    lo = np.r_[
        [min(s * 0.18, s * 0.29), -0.125, 0.035],
        [-0.35, -0.35, -0.35],
        [-1.0, -1.3, -1.0, 0, 0],
        np.tile([-0.4, 0, 0], 4),
    ]
    hi = np.r_[
        [max(s * 0.18, s * 0.29), 0.025, 0.15],
        [0.35, 0.35, 0.35],
        [1.0, 1.3, 1.5, 1.6, 1.5],
        np.tile([0.4, 1.7, 1.9], 4),
    ]
    boxes = [
        (np.array([0, 0, -0.024]), np.array([0.153, 0.076, 0.004])),
        (np.array([0.149, 0, 0]), np.array([0.005, 0.076, 0.027])),
        (np.array([-0.149, 0, 0]), np.array([0.005, 0.076, 0.027])),
        (np.array([0, 0.072, 0]), np.array([0.153, 0.004, 0.027])),
        (np.array([0, -0.072, 0]), np.array([0.153, 0.004, 0.027])),
    ]

    def unpack(x):
        H = np.eye(4)
        H[:3, :3] = R @ Rotation.from_rotvec(x[3:6]).as_matrix()
        H[:3, 3] = x[:3]
        return H

    def residual(x):
        tips, pts = handpoints(hand, x[6:], unpack(x))
        ds = []
        for center, half in boxes:
            q = np.abs(pts - center) - half
            ds.append(np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(1), 0))
        sdf = np.min(ds, axis=0)
        return np.r_[
            (tips - targets).ravel() * 300,
            np.maximum(0.006 - sdf, 0) * 210,
            np.maximum(-0.020 - pts[:, 2], 0) * 220,
            (x[:3] - origin) * 4,
            x[3:6] * 0.2,
            (x[6:] - f0) * 0.12,
        ]

    lo[6:] = hand.lo
    hi[6:] = hand.hi
    f0 = np.clip(f0, hand.lo + 1e-6, hand.hi - 1e-6)
    best = least_squares(residual, np.r_[origin, [0, 0, 0], f0], bounds=(lo, hi), max_nfev=350)
    H = unpack(best.x)
    tips, pts = handpoints(hand, best.x[6:], H)
    print(
        "TRAY_FIT",
        side,
        "wrist",
        H[:3, 3],
        "tiperr",
        np.linalg.norm(tips - targets, axis=1),
        flush=True,
    )
    return (
        H,
        best.x[6:],
        {
            "tip_error_m": np.linalg.norm(tips - targets, axis=1).tolist(),
            "wrist": H.tolist(),
            "type": "Thumb outside and four fingers inside the original tray end rim",
        },
    )


def mix(A, B, u):
    u = float(np.clip(u, 0, 1))
    T = np.eye(4)
    T[:3, 3] = (1 - u) * A[:3, 3] + u * B[:3, 3]
    T[:3, :3] = Slerp([0, 1], Rotation.from_matrix(np.array([A[:3, :3], B[:3, :3]])))(u).as_matrix()
    return T


def generate(rig, track, timing):
    """Return native wrist/finger targets for this stack-and-lift episode only."""
    N = len(track["place_object_world"])
    assert timing["frames"] == N and timing["fps"] == 15
    hands = {s: Hand(rig, s) for s in ["L", "R"]}
    fits = {s: fit_cube(hand) for s, hand in hands.items()}
    trayfits = {s: fit_tray(hand) for s, hand in hands.items()}
    report = {
        "method": "Native PMX FK fit to cube faces and tray rim; object-relative contacts, quintic approach/retract; no prior human animation",
        "cube": {s: fits[s][2] for s in hands},
        "tray": {s: trayfits[s][2] for s in hands},
    }
    results = {}
    for side, sign in [("L", -1), ("R", 1)]:
        hand = hands[side]
        t = timing["left" if side == "L" else "right"]
        obj = t["object"]
        begin, grasp, release = [t[k] for k in ["begin", "grasp", "release"]]
        tray_begin, tray_grasp = [timing["tray"][k] for k in ["begin", "grasp"]]
        assert 0 <= begin < grasp < release < tray_begin < tray_grasp < N
        lock = fits[side][0].copy()
        lock[:3, 3] += track[obj + "_world"][grasp, :3, 3]
        lock = np.linalg.inv(track[obj + "_world"][grasp]) @ lock
        traylock = trayfits[side][0].copy()
        traylock[:3, 3] += track["place_object_world"][tray_grasp, :3, 3]
        traylock = np.linalg.inv(track["place_object_world"][tray_grasp]) @ traylock
        rest = fits[side][0].copy()
        rest[:3, 3] = [sign * 0.26, -0.43, 0.93]
        fopen = np.r_[0.0, 0.05, 0.10, 0.12, 0.10, np.tile([0.0, 0.12, 0.12], 4)]
        closed = fits[side][1]
        # Allocate release/retract/recovery within the actual interval available.
        retract_end = release + min(60, max(2, (tray_begin - release) // 2))
        recovery_end = min(tray_begin, retract_end + 50)
        poses, angles, finger_world = [], [], []
        for i in range(N):
            H, q = rest.copy(), fopen.copy()
            locked = track[obj + "_world"][i] @ lock
            if begin <= i < grasp:
                pre = locked.copy()
                pre[:3, 3] += [0, -0.035, 0.085]
                mid = max(begin + 1, grasp - 36)
                H = (
                    mix(rest, pre, smooth((i - begin) / max(mid - begin, 1)))
                    if i < mid
                    else mix(pre, locked, smooth((i - mid) / max(grasp - mid, 1)))
                )
                q = fopen + (closed - fopen) * smooth(
                    (i - max(begin, grasp - 24)) / min(grasp - begin, 24)
                )
            elif grasp <= i <= release:
                H, q = locked, closed.copy()
            elif release < i < tray_begin:
                start = track[obj + "_world"][release] @ lock
                lifted = start.copy()
                lifted[:3, 3] += [0, -0.065, 0.12]
                if i < retract_end:
                    H = mix(start, lifted, smooth((i - release) / (retract_end - release)))
                else:
                    H = mix(
                        lifted, rest, smooth((i - retract_end) / max(recovery_end - retract_end, 1))
                    )
                q = closed + (fopen - closed) * smooth(
                    (i - release) / min(20, retract_end - release)
                )
            if i >= tray_begin:
                target = track["place_object_world"][i] @ traylock
                pre = target.copy()
                pre[:3, 3] += [0, -0.02, 0.07]
                arrive = max(tray_begin + 1, tray_grasp - 25)
                if i < arrive:
                    H = mix(rest, pre, smooth((i - tray_begin) / max(arrive - tray_begin, 1)))
                elif i < tray_grasp:
                    H = mix(pre, target, smooth((i - arrive) / max(tray_grasp - arrive, 1)))
                else:
                    H = target
                q = fopen + (trayfits[side][1] - fopen) * smooth(
                    (i - arrive) / max(tray_grasp - arrive, 1)
                )
            q = np.clip(q, hand.lo, hand.hi)
            g, _ = hand.fk(q)
            poses.append(H)
            angles.append(q)
            finger_world.append(H @ g)
        results[side + "_canonical_wrist_world"] = np.asarray(poses)
        results[side + "_q"] = np.asarray(angles)
        results[side + "_finger_world"] = np.asarray(finger_world)
    return results, report
