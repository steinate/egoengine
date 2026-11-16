"""Native PMX bone lengths, bounded fingers and analytic humanoid limb IK."""

from pathlib import Path
import os
import numpy as np
from scipy.spatial.transform import Rotation

B = Path(os.environ.get("EGO_AVATAR_DIR", Path(__file__).resolve().parent)).resolve()
SCALE = 1.10


def unit(v):
    return v / max(np.linalg.norm(v), 1e-12)


def rot(v):
    return Rotation.from_rotvec(v).as_matrix()


def align(a, b):
    a, b = unit(a), unit(b)
    v = np.cross(a, b)
    c = a @ b
    if c < -0.99999:
        return rot(unit(np.cross(a, [0.1, 0.3, 1])) * np.pi)
    V = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + V + V @ V / (1 + c)


def transform(R, t):
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


def look(eye, target):
    z = unit(eye - target)
    x = unit(np.cross([0, 0, 1], z))
    return transform(np.stack([x, np.cross(z, x), z], 1), eye)


class Rig:
    def __init__(self):
        a = np.load(B / "amber-rig.npz")
        self.names = a["names"].tolist()
        self.parents = a["parents"]
        self.rest = a["rest"].astype(np.float64)
        self.rest[:, :3, 3] *= SCALE
        self.children = []
        for j in range(len(self.names)):
            children = {j}
            pending = True
            while pending:
                old = len(children)
                children.update(k for k, p in enumerate(self.parents) if p in children)
                pending = len(children) > old
            self.children.append(np.array(sorted(children)))

    def idx(self, n):
        return self.names.index(n)

    def set(self, G, n, R, t=None):
        j = self.idx(n)
        T = transform(R, G[j, :3, 3] if t is None else t)
        delta = T @ np.linalg.inv(G[j])
        ids = self.children[j]
        G[ids] = delta @ G[ids]

    def limb(self, G, ns, target, pole):
        ids = [self.idx(n) for n in ns]
        S, E, W = G[ids, :3, 3]
        l1 = np.linalg.norm(E - S)
        l2 = np.linalg.norm(W - E)
        u = unit(target - S)
        distance = np.linalg.norm(target - S)
        d = np.clip(distance, abs(l1 - l2) + 0.0001, l1 + l2 - 0.0001)
        x = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
        h = np.sqrt(max(l1 * l1 - x * x, 0))
        v = unit(pole - S - u * ((pole - S) @ u))
        elbow = S + x * u + h * v
        self.set(G, ns[0], align(E - S, elbow - S) @ G[ids[0], :3, :3])
        E, W = G[ids[1:], :3, 3]
        self.set(G, ns[1], align(W - E, S + d * u - E) @ G[ids[1], :3, :3])
        return abs(distance - d)


class Hand:
    """17 native-chain DOFs. Flexion axes derived from each native palm plane."""

    fingers = ["親指", "人指", "中指", "薬指", "小指"]

    def __init__(self, rig, side):
        self.rig = rig
        self.side = side
        self.wrist = rig.idx("手首." + side)
        self.ids = []
        self.rest = []
        self.tips = []
        for f in self.fingers:
            nums = ["０", "１", "２"] if f == "親指" else ["１", "２", "３"]
            ids = [rig.idx(f + n + "." + side) for n in nums]
            self.ids.append(ids)
            self.rest.append(rig.rest[ids])
            self.tips.append(rig.rest[rig.idx(f + "先." + side), :3, 3])
        self.ids = np.array(self.ids)
        self.rest = np.array(self.rest)
        self.tips = np.array(self.tips)
        wrist = rig.rest[self.wrist, :3, 3]
        y = unit(self.rest[2, 0, :3, 3] - wrist)
        z = unit(self.rest[1, 0, :3, 3] - self.rest[4, 0, :3, 3])
        z = unit(z - y * (z @ y))
        x = np.cross(y, z)
        # Canonical palm axes follow source human wrist: +Y fingers, +Z thumb.
        self.C = transform(np.stack([x, y, z], 1), wrist)
        inv = np.linalg.inv(self.C)
        self.rest = inv @ self.rest
        self.tips = (self.tips - wrist) @ self.C[:3, :3]
        self.offset = self.rest.copy()
        for f in range(5):
            for k in [2, 1]:
                self.offset[f, k] = np.linalg.inv(self.rest[f, k - 1]) @ self.rest[f, k]
        self.axes = np.zeros((5, 3, 3))
        self.spread = np.zeros((5, 3))
        # Thumb side is +Z. In canonical axes, native right palm faces -X,
        # left palm +X. All flexion parameters are positive towards the palm.
        palm = np.array([-1.0 if side == "R" else 1.0, 0, 0])
        for f in range(5):
            for k in range(3):
                d = (self.tips[f] if k == 2 else self.rest[f, k + 1, :3, 3]) - self.rest[
                    f, k, :3, 3
                ]
                self.axes[f, k] = self.rest[f, k, :3, :3].T @ unit(np.cross(unit(d), palm))
            self.spread[f] = self.rest[f, 0, :3, :3].T @ palm
        self.lo = np.r_[[-1.1, -1.1, -1.1, 0, 0], np.tile([-0.40, 0, 0], 4)]
        self.hi = np.r_[[1.1, 1.1, 1.1, 1.6, 1.6], np.tile([0.40, 1.65, 1.9], 4)]

    def fk(self, q):
        g = self.rest.copy()
        tip = []
        for f in range(5):
            if f == 0:
                Rs = [rot(q[:3]), rot(self.axes[f, 1] * q[3]), rot(self.axes[f, 2] * q[4])]
            else:
                ab, mp, pi = q[5 + 3 * (f - 1) : 8 + 3 * (f - 1)]
                Rs = [
                    rot(self.spread[f] * ab) @ rot(self.axes[f, 0] * mp),
                    rot(self.axes[f, 1] * pi),
                    rot(self.axes[f, 2] * (0.65 * pi)),
                ]
            for k in range(3):
                T = self.offset[f, k].copy()
                T[:3, :3] = T[:3, :3] @ Rs[k]
                g[f, k] = (g[f, k - 1] @ T) if k else T
            T = g[f, 2] @ np.linalg.inv(self.rest[f, 2])
            tip.append(T[:3, :3] @ self.tips[f] + T[:3, 3])
        return g, np.array(tip)
