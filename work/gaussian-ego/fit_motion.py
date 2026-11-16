"""Fit GHOST MANO driver to contact-consistent templates, keep official object poses."""

from ghost_adapter import *
from scipy.spatial.transform import Rotation
import json

torch.autograd.set_detect_anomaly(False)
ROOT = HERE.parent
data = dict(np.load(ROOT / "outputs41/human-ego/world-tracks.npz"))
human = dict(np.load(ROOT / "outputs41/human-ego/human-animation.npz"))
sys.path.insert(0, str(ROOT / "outputs41/human-ego"))
import make_human as old

out = HERE / "output"
out.mkdir(exist_ok=True)
g = avatar()
layer = g.mano_layer
targets = []
for name in ["template_open", "template_cube"]:
    v, j = old.hand(human[name])
    t = [j[0]]
    for k, b in enumerate([2, 5, 8, 11, 14]):
        t.extend([j[b], j[b + 1], j[b + 2], v[old.tips[k]].mean(0)])
    targets.append(t)
target = torch.tensor(np.array(targets), device="cuda", dtype=torch.float32)
with torch.no_grad():
    vv, jj = layer(torch.zeros(1, 48, device="cuda"))
    jj = jj[0].cpu().numpy() / 1000
idx = [0, 5, 9, 13, 17]
a = jj[idx] - jj[idx].mean(0)
b = np.array(targets)[0, idx] - np.array(targets)[0, idx].mean(0)
u, _, vt = np.linalg.svd(a.T @ b)
R = vt.T @ u.T
if np.linalg.det(R) < 0:
    vt[-1] *= -1
    R = vt.T @ u.T
pose = torch.zeros(2, 48, device="cuda")
pose[:, :3] = torch.tensor(Rotation.from_matrix(R).as_rotvec(), device="cuda")
pose.requires_grad_()
trans = torch.tensor(
    np.tile(np.array(targets)[0, 0] - R @ jj[0], (2, 1)),
    device="cuda",
    dtype=torch.float32,
    requires_grad=True,
)
optimizer = torch.optim.Adam([pose, trans], lr=0.015)
H = human["right_wrist_T"][470]
T = data["pick_object_right1_world"][470]
object_local = np.linalg.inv(H) @ T
Oc = torch.tensor(object_local[:3, 3], dtype=torch.float32, device="cuda")
Or = torch.tensor(object_local[:3, :3], dtype=torch.float32, device="cuda")
half = torch.tensor(
    np.max(np.abs(data["pick_object_right1_mesh_vertices"]), axis=0),
    device="cuda",
    dtype=torch.float32,
)
for it in range(900):
    optimizer.zero_grad()
    v, j = layer(pose)
    v = v / 1000 + trans[:, None, :]
    j = j / 1000 + trans[:, None, :]
    weights = torch.ones(21, device="cuda")
    weights[[4, 8, 12]] = 3
    loss = ((j - target).square().sum(-1) * weights).mean() * 1e4
    loc = (v[1] - Oc) @ Or
    penetration = torch.relu((half - loc.abs()).min(-1).values)
    loss = loss + penetration.square().mean() * 2e5 + pose[:, 3:].square().mean() * 0.025
    loss.backward()
    optimizer.step()
    if it == 500:
        for q in optimizer.param_groups:
            q["lr"] = 0.003
    if it % 150 == 0:
        print("FIT", it, float(loss), float(penetration.max()), flush=True)
with torch.no_grad():
    v, j = layer(pose)
    v = v / 1000 + trans[:, None, :]
    j = j / 1000 + trans[:, None, :]
    template_pose = pose.detach().cpu().numpy()
    template_translation = trans.detach().cpu().numpy()
    template_rmse = ((j - target).square().mean(dim=(1, 2)).sqrt()).cpu().numpy().tolist()
    np.savez(
        out / "templates.npz",
        pose=template_pose,
        translation=template_translation,
        target=target.cpu().numpy(),
        vertices=v.cpu().numpy(),
        joints=j.cpu().numpy(),
        faces=g.faces.cpu().numpy(),
    )
ids = np.arange(420, 511)
vertices = []
joints = []
poses = []
translations = []
for i in ids:
    close = float(
        np.clip(
            (human["right_pose"][i, 10] - human["template_open"][10])
            / (human["template_cube"][10] - human["template_open"][10]),
            0,
            1,
        )
    )
    p = template_pose[0] * (1 - close) + template_pose[1] * close
    t = template_translation[0] * (1 - close) + template_translation[1] * close
    with torch.no_grad():
        v, j = layer(torch.tensor(p[None], device="cuda"))
    v = v[0].cpu().numpy() / 1000 + t
    j = j[0].cpu().numpy() / 1000 + t
    H = human["right_wrist_T"][i]
    vertices.append(v @ H[:3, :3].T + H[:3, 3])
    joints.append(j @ H[:3, :3].T + H[:3, 3])
    poses.append(p)
    translations.append(t)
np.savez_compressed(
    out / "motion.npz",
    source_frames=ids,
    vertices=vertices,
    joints=joints,
    mano_pose_local=poses,
    mano_translation_local=translations,
    wrist_world=human["right_wrist_T"][ids],
    arm=human["right_arm"][ids],
    faces=g.faces.cpu().numpy(),
    object_world=data["pick_object_right1_world"][ids],
)
report = {
    "frames": len(ids),
    "source_start": int(ids[0]),
    "source_end": int(ids[-1]),
    "template_joint_rmse_m": template_rmse,
    "method": "MANO fitted to prior contact template; official object trajectory unchanged",
}
(out / "motion-info.json").write_text(json.dumps(report, indent=2))
print("FIT_DONE", report, flush=True)
