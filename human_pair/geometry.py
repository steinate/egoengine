"""Metric world-space utilities; transforms multiply column vectors."""
import numpy as np


def two_bone_ik(shoulder, wrist, upper_length, fore_length, pole):
    """Return elbow; reject unreachable targets instead of stretching limbs.

    pole is a world-space elbow hint, not a direction. For sequences, use a
    consistent anatomical pole and check elbow continuity after solving.
    """
    s, w, p = (np.asarray(x, dtype=float) for x in (shoulder, wrist, pole))
    d = np.linalg.norm(w-s)
    if not np.isfinite([*s,*w,*p,upper_length,fore_length]).all():
        raise ValueError('Non-finite IK input')
    if min(upper_length,fore_length) <= 0 or d < 1e-8:
        raise ValueError('Degenerate arm')
    if d > upper_length+fore_length+1e-8 or d < abs(upper_length-fore_length)-1e-8:
        raise ValueError('Unreachable wrist: change shoulder/stance or reject episode')
    axis = (w-s)/d
    bend = p-s-np.dot(p-s,axis)*axis
    if np.linalg.norm(bend) < 1e-7:
        raise ValueError('Pole is collinear: choose a stable anatomical pole')
    bend /= np.linalg.norm(bend)
    along = (upper_length**2-fore_length**2+d*d)/(2*d)
    height = np.sqrt(max(upper_length**2-along**2,0.0))
    return s+along*axis+height*bend


def locked_grasp(object_T, object_to_wrist):
    """Only for a stable, non-sliding rigid grasp interval."""
    return np.asarray(object_T) @ np.asarray(object_to_wrist)


def center_mano_vertices(vertices, joints, wrist_T):
    """MANO vertices are not wrist-centered; explicitly subtract joint 0."""
    local = np.asarray(vertices)-np.asarray(joints)[:, :1, :]
    T = np.asarray(wrist_T)
    return np.einsum('tij,tvj->tvi',T[:,:3,:3],local)+T[:,None,:3,3]
