"""A scan-sized 17-DOF hand and smooth dual-quaternion skinning.

Joint landmarks are estimated inside the actual scan; this is an approximate
anatomical rig, not measured joint centres or a contact dynamics model.
"""

import numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation

FINGERS = ["Thumb", "Index", "Mid", "Ring", "Pinky"]
# Landmark X,Z coordinates in the imported scan's centimetre coordinates.
LANDMARKS = np.array(
    [
        [[8.3, 36.0], [12.0, 38.7], [14.6, 41.0], [16.8, 42.2]],
        [[10.2, 42.6], [10.6, 46.4], [10.7, 49.0], [10.65, 51.3]],
        [[7.6, 43.0], [7.5, 47.4], [7.4, 50.0], [7.35, 52.05]],
        [[5.1, 42.7], [4.7, 46.8], [4.3, 49.35], [4.15, 51.3]],
        [[3.45, 41.9], [2.05, 44.65], [1.05, 46.4], [0.4, 47.95]],
    ]
)


def unit(v):
    return v / max(np.linalg.norm(v), 1e-12)


def rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rz(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


class Hand:
    def __init__(self, mesh, side):
        self.side = side
        self.sign = 1 if side == "R" else -1
        raw = mesh["points_cm"]
        joints = []
        for chain in LANDMARKS:
            points = []
            for x, z in chain:
                dist = np.linalg.norm(raw[:, [0, 2]] - [x, z], axis=1)
                nearest = raw[np.argsort(dist)[:180], 1]
                points.append([x, (np.percentile(nearest, 5) + np.percentile(nearest, 95)) / 2, z])
            joints.append(points)

        def local(v):
            v = np.asarray(v) - [6.6, 0.45, 33.6]
            return np.stack([-self.sign * v[..., 1], v[..., 2], v[..., 0] + 1.2], axis=-1) * 0.01

        self.v = local(raw)
        self.landmarks = local(joints)
        self.rest = np.repeat(np.eye(4)[None], 16, axis=0)
        self.parents = np.array([-1] + [0 if j % 3 == 0 else j for j in range(15)])
        for f in range(5):
            for k in range(3):
                index = 1 + f * 3 + k
                p = self.landmarks[f, k]
                y = unit(self.landmarks[f, k + 1] - p)
                x = unit(np.array([1.0, 0, 0]) - y * y[0])
                z = np.cross(x, y)
                self.rest[index, :3, :3] = np.stack([x, y, z], axis=1)
                self.rest[index, :3, 3] = p
        self.local = self.rest.copy()
        for j in range(1, 16):
            self.local[j] = np.linalg.inv(self.rest[self.parents[j]]) @ self.rest[j]
        self.inverse = np.linalg.inv(self.rest)
        self.lo = np.r_[[-1.2, -1.2, -1.2, 0, 0], np.tile([-0.65, -0.15, 0], 4)]
        self.hi = np.r_[[1.2, 1.2, 1.2, 1.8, 1.8], np.tile([0.65, 1.9, 2.0], 4)]
        self.ids, self.weights = self.skin_weights()
        heat = Path(__file__).with_name("heat-weights.npz")
        if heat.exists():
            w = np.load(heat)["weights"]
            assert len(w) == len(self.v)
            self.ids = np.argsort(-w, axis=1)[:, :6]
            self.weights = np.take_along_axis(w, self.ids, axis=1)
            self.weights /= self.weights.sum(1, keepdims=True)

    def fk(self, q):
        g = np.repeat(np.eye(4)[None], 16, axis=0)
        for f in range(5):
            if f == 0:
                rotations = [
                    Rotation.from_rotvec(q[:3]).as_matrix(),
                    rz(self.sign * q[3]),
                    rz(self.sign * q[4]),
                ]
            else:
                ab, mp, pi = q[5 + 3 * (f - 1) : 8 + 3 * (f - 1)]
                rotations = [
                    rx(ab) @ rz(self.sign * mp),
                    rz(self.sign * pi),
                    rz(self.sign * 0.65 * pi),
                ]
            for k, R in enumerate(rotations):
                j = 1 + f * 3 + k
                T = self.local[j].copy()
                T[:3, :3] = T[:3, :3] @ R
                g[j] = g[self.parents[j]] @ T
        return g

    def tips(self, q):
        g = self.fk(q)
        out = []
        for f in range(5):
            j = 3 + f * 3
            T = g[j] @ self.inverse[j]
            out.append(T[:3, :3] @ self.landmarks[f, 3] + T[:3, 3])
        return np.array(out)

    def skin_weights(self):
        v = self.v
        all_dist = []
        all_s = []
        lengths = []
        for f in range(5):
            p = self.landmarks[f]
            lens = np.linalg.norm(np.diff(p, axis=0), axis=1)
            lengths.append(lens)
            ds = []
            ss = []
            for k in range(3):
                direction = (p[k + 1] - p[k]) / lens[k]
                t = (v - p[k]) @ direction
                closest = p[k] + np.clip(t, 0, lens[k])[:, None] * direction
                ds.append(np.linalg.norm(v - closest, axis=1))
                ss.append(lens[:k].sum() + t)
            ds = np.stack(ds, 1)
            near = ds.argmin(1)
            all_dist.append(ds[np.arange(len(v)), near])
            all_s.append(np.stack(ss, 1)[np.arange(len(v)), near])
        chosen = np.stack(all_dist, 1).argmin(1)
        arc = np.stack(all_s, 1)[np.arange(len(v)), chosen]
        lengths = np.array(lengths)[chosen]
        a = smooth((arc + 0.014) / 0.025)
        b = smooth((arc - lengths[:, 0] + 0.006) / 0.012)
        c = smooth((arc - lengths[:, :2].sum(1) + 0.004) / 0.008)
        weights = np.stack([1 - a, a - b, b - c, c], 1)
        weights = np.maximum(weights, 0)
        weights /= weights.sum(1, keepdims=True)
        ids = np.stack([np.zeros(len(v), int), 1 + chosen * 3, 2 + chosen * 3, 3 + chosen * 3], 1)
        # Blend the proximal cuff into the FOREARM, rather than rotating it as a hand.
        fore = 1 - smooth((v[:, 1] + 0.018) / 0.030)
        weights *= 1 - fore[:, None]
        return np.c_[ids, np.full(len(v), 16)], np.c_[weights, fore]

    def deform(self, q, forearm_relative, indices=None):
        transforms = np.concatenate([self.fk(q) @ self.inverse, forearm_relative[None]], axis=0)
        qr = Rotation.from_matrix(transforms[:, :3, :3]).as_quat()
        qr *= np.where(qr[:, 3] < 0, -1.0, 1.0)[:, None]
        trans = transforms[:, :3, 3]
        qd = np.c_[
            0.5 * (qr[:, 3, None] * trans + np.cross(trans, qr[:, :3])),
            -0.5 * np.sum(trans * qr[:, :3], axis=1),
        ]
        ids = self.ids if indices is None else self.ids[indices]
        weights = self.weights if indices is None else self.weights[indices]
        r = (qr[ids] * weights[..., None]).sum(1)
        d = (qd[ids] * weights[..., None]).sum(1)
        norm = np.linalg.norm(r, axis=1, keepdims=True)
        r /= norm
        d /= norm
        d -= r * np.sum(r * d, axis=1, keepdims=True)
        t = 2 * (
            -d[:, 3, None] * r[:, :3] + r[:, 3, None] * d[:, :3] + np.cross(r[:, :3], d[:, :3])
        )
        v = self.v if indices is None else self.v[indices]
        return v + 2 * np.cross(r[:, :3], np.cross(r[:, :3], v) + r[:, 3, None] * v) + t


def normals(v, faces):
    n = np.zeros_like(v)
    f = np.cross(v[faces[:, 1]] - v[faces[:, 0]], v[faces[:, 2]] - v[faces[:, 0]])
    for k in range(3):
        np.add.at(n, faces[:, k], f)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
