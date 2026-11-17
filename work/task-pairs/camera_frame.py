"""A level, table-facing native eye camera referenced to the robot head camera."""

import numpy as np
from scipy.spatial.transform import Rotation


def reference_pitch(camera):
    forward = -np.asarray(camera)[:3, 2]
    return float(np.rad2deg(np.arctan2(-forward[2], np.linalg.norm(forward[:2]))))


def pose_head(h, local, pitch_deg):
    pose = local.copy()
    neck, head = h.idx("NeckTwist01"), h.idx("Head")
    for j in [neck, h.idx("NeckTwist02"), head]:
        pose[j] = h.rest[j]
    pitch = np.deg2rad(pitch_deg)
    direction = np.array([0.0, np.cos(pitch), -np.sin(pitch)])
    rv = Rotation.align_vectors([direction], [-h.world[:3, 1]])[0].as_rotvec()
    for j, fraction in [(neck, 0.35), (head, 0.65)]:
        g = h.fk(pose)
        desired = Rotation.from_rotvec(rv * fraction).as_matrix() @ g[j, :3, :3]
        pose[j, :3, :3] = g[h.parents[j], :3, :3].T @ desired
    return pose


def eye_camera(h, pose, pitch_deg):
    pitch = np.deg2rad(pitch_deg)
    forward = np.array([0.0, np.cos(pitch), -np.sin(pitch)])
    g = h.fk(pose)
    eye = g[[h.idx("L_Eye"), h.idx("R_Eye")], :3, 3].mean(0)
    camera = np.eye(4)
    camera[:3, :3] = np.stack([[1, 0, 0], np.cross(-forward, [1, 0, 0]), -forward], axis=1)
    camera[:3, 3] = eye + forward * 0.018
    return camera
