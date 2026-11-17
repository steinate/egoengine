"""Native Worker arm and finger kinematics, independent of robot joint angles."""

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


def rot(axis, angle):
    v = np.zeros(3)
    v[axis] = angle
    return Rotation.from_rotvec(v).as_matrix()


def smooth(value):
    x = np.clip(value, 0, 1)
    return x**3 * (10 - 15 * x + 6 * x * x)


IDLE = np.r_[0.0, 0.1, 0.2, 0.25, 0.2, np.tile([0.0, 0.30, 0.38], 4)]
CLOSED = np.r_[0.0, 0.25, 0.35, 0.6, 0.5, np.tile([0.0, 0.65, 1.0], 4)]
FINGER_LOW = np.r_[[-1.0, -1.3, -1.0, 0.0, 0.0], np.tile([-0.4, 0.0, 0.0], 4)]
FINGER_HIGH = np.r_[[1.0, 1.3, 1.5, 1.6, 1.5], np.tile([0.4, 1.7, 1.9], 4)]
ARM_LOW = np.r_[[-0.15, -0.40], [-2.7, -2.7, -2.7], 0.10, -1.65, -0.40, -0.85]
ARM_HIGH = np.r_[[0.65, 0.40], [2.7, 2.7, 2.7], 2.45, 1.65, 0.40, 0.85]


def fingers(h, side, values, pose):
    p = pose.copy()
    sign = 1 if side == "R" else -1
    f = values
    for k in (1, 2, 3):
        j = h.idx(side + "_Thumb" + str(k))
        d = (
            rot(0, f[0]) @ rot(1, sign * f[1]) @ rot(2, sign * f[2])
            if k == 1
            else rot(2, sign * f[k + 1])
        )
        p[j, :3, :3] = h.rest[j, :3, :3] @ d
    for k, name in enumerate(("Index", "Mid", "Ring", "Pinky")):
        ab, mp, pi = f[5 + 3 * k : 8 + 3 * k]
        for n, d in [
            (1, rot(0, ab) @ rot(2, sign * mp)),
            (2, rot(2, sign * pi)),
            (3, rot(2, sign * 0.65 * pi)),
        ]:
            j = h.idx(side + "_" + name + str(n))
            p[j, :3, :3] = h.rest[j, :3, :3] @ d
    return p


def tip_local(h, side, values):
    g = h.fk(fingers(h, side, values, h.rest))
    inv = np.linalg.inv(g[h.idx(side + "_Hand")])
    tips = []
    for name in h.fingers:
        j = h.idx(side + "_" + name + "3")
        world = g[j, :3, 3] + g[j, :3, 1] * h.tip_length[name]
        tips.append(inv[:3, :3] @ world + inv[:3, 3])
    return np.asarray(tips)


class Arm:
    def __init__(self, h, side, body, orientation_weight=35.0):
        self.h, self.side = h, side
        self.orientation_weight = orientation_weight
        self.sign = 1 if side == "R" else -1
        self.ids = [h.idx(side + "_" + n) for n in ("Clavicle", "Upperarm", "Forearm", "Hand")]
        g = h.fk(body)
        self.parent = g[h.parents[self.ids[0]]]
        self.parts = [body[self.ids[0]].copy()] + [h.rest[j].copy() for j in self.ids[1:]]
        self.right, self.forward = -h.world[:3, 0], -h.world[:3, 1]
        self.lengths = [np.linalg.norm(self.parts[k][:3, 3]) for k in (2, 3)]
        self.priors = np.asarray([self.q_from_pose(p) for p in h.priors])

    def q_from_pose(self, pose):
        def delta(name):
            j = self.h.idx(self.side + "_" + name)
            return self.h.rest[j, :3, :3].T @ pose[j, :3, :3]

        q = np.r_[
            0.0,
            0.0,
            Rotation.from_matrix(delta("Upperarm")).as_rotvec(),
            Rotation.from_matrix(delta("Forearm")).as_rotvec()[0],
            Rotation.from_matrix(delta("Hand")).as_euler("YXZ"),
        ]
        return np.clip(q, ARM_LOW + 1e-5, ARM_HIGH - 1e-5)

    def fk(self, q):
        p = [x.copy() for x in self.parts]
        for v, d in zip(
            p,
            [
                rot(0, q[0]) @ rot(2, q[1]),
                Rotation.from_rotvec(q[2:5]).as_matrix(),
                rot(0, q[5]),
                rot(1, q[6]) @ rot(0, q[7]) @ rot(2, q[8]),
            ],
        ):
            v[:3, :3] = v[:3, :3] @ d
        g, t = [], self.parent
        for v in p:
            t = t @ v
            g.append(t)
        return p, np.asarray(g)

    def solve(self, target, previous=None, previous2=None):
        candidates = self.priors
        rank = (
            np.argsort(
                [np.linalg.norm(self.fk(q)[1][-1, :3, 3] - target[:3, 3]) for q in candidates]
            )
            if previous is None
            else None
        )
        prior = candidates[rank[0]] if previous is None else previous

        def residual(q):
            _, g = self.fk(q)
            shoulder, elbow, wrist = g[1, :3, 3], g[2, :3, 3], g[3]
            d = target[:3, 3] - shoulder
            dist = max(np.linalg.norm(d), 1e-7)
            u = d / dist
            l1, l2 = self.lengths
            dc = np.clip(dist, abs(l1 - l2) + 0.001, l1 + l2 - 0.001)
            along = (l1 * l1 - l2 * l2 + dc * dc) / (2 * dc)
            pole = self.sign * 0.8 * self.right + 0.12 * self.forward + [0, 0, -0.68]
            pole -= u * np.dot(u, pole)
            goal = (
                shoulder
                + u * along
                + pole / max(np.linalg.norm(pole), 1e-7) * np.sqrt(max(l1 * l1 - along * along, 0))
            )
            result = [
                (wrist[:3, 3] - target[:3, 3]) * 1500,
                Rotation.from_matrix(target[:3, :3].T @ wrist[:3, :3]).as_rotvec()
                * self.orientation_weight,
                (elbow - goal) * 18,
                [max(0.0, 0.01 - self.sign * np.dot(elbow - shoulder, self.right)) * 1000],
                [max(0.0, -np.dot(elbow - shoulder, self.forward) - 0.005) * 180],
                (q - prior) * (0.8 if previous is None else 8.0),
                q[7:9] * 1.2,
            ]
            if previous2 is not None:
                result.append((q - 2 * previous + previous2) * 6.0)
            return np.concatenate(result)

        seeds = [prior] if previous is not None else list(candidates[rank[:4]])
        low = ARM_LOW if previous is None else np.maximum(ARM_LOW, previous - 0.12)
        high = ARM_HIGH if previous is None else np.minimum(ARM_HIGH, previous + 0.12)
        solutions = [
            least_squares(
                residual,
                np.clip(q, low + 1e-6, high - 1e-6),
                bounds=(low, high),
                max_nfev=55,
            )
            for q in seeds
        ]
        best = min(solutions, key=lambda r: r.cost)
        return best.x, self.fk(best.x)

    def apply(self, q, pose):
        p = pose.copy()
        local, _ = self.fk(q)
        for j, t in zip(self.ids, local):
            p[j] = t
        upper_q = Rotation.from_rotvec(q[2:5]).as_quat()
        twist = 2 * np.arctan2(upper_q[1], upper_q[3])
        for name, angle in [
            ("UpperarmTwist01", -0.5 * twist),
            ("UpperarmTwist02", 0.5 * twist),
            ("ForearmTwist01", 0.0),
            ("ForearmTwist02", 0.5 * q[6]),
        ]:
            j = self.h.idx(self.side + "_" + name)
            p[j, :3, :3] = self.h.rest[j, :3, :3] @ rot(1, angle)
        return p
