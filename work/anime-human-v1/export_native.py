import bpy, numpy as np, json, shutil
from pathlib import Path

B = Path(__file__).resolve().parent
import sys

sys.path.insert(0, str(B / "tools/python-deps"))
sys.path.insert(0, str(B / "tools/blender_mmd_tools"))
import mmd_tools

mmd_tools.register()
bpy.ops.wm.open_mainfile(filepath=str(B / "amber-native.blend"))
rig = bpy.data.objects["AmberRig"]
bones = list(rig.data.bones)
names = [b.name for b in bones]
o = next(o for o in bpy.data.objects if o.type == "MESH")
m = o.data
m.calc_loop_triangles()
v = np.array([x.co for x in m.vertices])
faces = np.array([t.vertices for t in m.loop_triangles])
uv = np.array([[m.uv_layers.active.data[j].uv[:] for j in t.loops] for t in m.loop_triangles])
mat = np.array([t.material_index for t in m.loop_triangles])
ids = np.zeros((len(v), 4), int)
w = np.zeros((len(v), 4))
for i, vert in enumerate(m.vertices):
    groups = sorted(
        [
            (names.index(o.vertex_groups[g.group].name), g.weight)
            for g in vert.groups
            if o.vertex_groups[g.group].name in names and g.weight > 0
        ],
        key=lambda x: -x[1],
    )[:4]
    for k, (j, a) in enumerate(groups):
        ids[i, k] = j
        w[i, k] = a
    if w[i].sum() == 0:
        w[i, 0] = 1
    w[i] /= w[i].sum()
# Omit the actor's own head/hair from first person, via original skin weights.
head = names.index("頭")
desc = {head}
for j, b in enumerate(bones):
    if b.parent and names.index(b.parent.name) in desc:
        desc.add(j)
head_weight = np.sum(w * np.isin(ids, list(desc)), axis=1)
ego_keep = np.all(head_weight[faces] < 0.1, axis=1)
np.savez_compressed(
    B / "amber-mesh.npz",
    points=v,
    faces=faces,
    uv=uv,
    material=mat,
    ids=ids,
    weights=w,
    ego_keep=ego_keep,
)
materials = []
(B / "textures").mkdir(exist_ok=True)
for i, m in enumerate(o.data.materials):
    imgs = [n.image for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image]
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    d = {
        "name": m.name,
        "rgba": list(p.inputs["Base Color"].default_value),
        "alpha": float(m.mmd_material.alpha),
    }
    if imgs:
        src = Path(bpy.path.abspath(imgs[0].filepath))
        dest = B / "textures" / f"material-{i}{src.suffix}"
        shutil.copy2(src, dest)
        d["texture"] = "textures/" + dest.name
    materials.append(d)
(B / "materials.json").write_text(json.dumps(materials, ensure_ascii=False, indent=2))
print("EXPORTED", len(v), len(faces), "ego faces", int(ego_keep.sum()), materials)
