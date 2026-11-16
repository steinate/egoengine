"""Import the unmodified Bilibili PMX release and audit its native rig/UVs."""

import bpy, sys, json
from pathlib import Path
import numpy as np

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "tools/python-deps"))
sys.path.insert(0, str(BASE / "tools/blender_mmd_tools"))
import mmd_tools

mmd_tools.register()
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mmd_tools.import_model(
    filepath=str(next((BASE / "assets/amber").rglob("*.pmx"))),
    scale=0.1,
    types={"MESH", "ARMATURE"},
    clean_model=True,
    remove_doubles=False,
)
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
rig.name = "AmberRig"
# Explicitly disable MMD control constraints: later motion uses a character-sized
# solved deform skeleton, not PMX leg IK or inherited append transforms.
for p in rig.pose.bones:
    for c in list(p.constraints):
        p.constraints.remove(c)
bones = list(rig.data.bones)
names = [b.name for b in bones]
audit = {
    "model": "Amber / 安柏2.0",
    "copyright": "miHoYo",
    "model_editor": "神帝宇",
    "download": "https://activity.hdslb.com/blackboard/static/20210316/4d40bc4f98f94fbc71c235832ce3efd4/ApoSncaZI8.zip",
    "bones": [
        {
            "name": b.name,
            "jp": rig.pose.bones[b.name].mmd_bone.name_j,
            "parent": b.parent.name if b.parent else None,
            "head": list(b.head_local),
            "tail": list(b.tail_local),
        }
        for b in bones
    ],
    "meshes": [],
}
for o in bpy.data.objects:
    if o.type != "MESH":
        continue
    audit["meshes"].append(
        {
            "name": o.name,
            "vertices": len(o.data.vertices),
            "faces": len(o.data.polygons),
            "materials": [m.name for m in o.data.materials],
        }
    )
    for m in o.data.materials:
        if not m:
            continue
        # Keep the model's original texture and UV. Rebuild portable PBR materials
        # because MMD shader node groups do not transfer to USD/Isaac.
        imgs = [n.image for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image]
        diffuse = next(
            (im for im in imgs if "toon" not in im.name.lower() and "mc3" not in im.name.lower()),
            None,
        )
        rgba = tuple(m.diffuse_color)
        m.node_tree.nodes.clear()
        nodes = m.node_tree.nodes
        links = m.node_tree.links
        out = nodes.new("ShaderNodeOutputMaterial")
        p = nodes.new("ShaderNodeBsdfPrincipled")
        links.new(p.outputs["BSDF"], out.inputs["Surface"])
        p.inputs["Roughness"].default_value = 0.8
        p.inputs["Base Color"].default_value = rgba
        p.inputs["Specular IOR Level"].default_value = 0.15
        if diffuse:
            t = nodes.new("ShaderNodeTexImage")
            t.image = diffuse
            links.new(t.outputs["Color"], p.inputs["Base Color"])
            links.new(t.outputs["Alpha"], p.inputs["Alpha"])
            p.inputs["Emission Strength"].default_value = 0.15
            links.new(t.outputs["Color"], p.inputs["Emission Color"])
        else:
            p.inputs["Alpha"].default_value = rgba[3]
        m.use_backface_culling = False
np.savez_compressed(
    BASE / "amber-rig.npz",
    names=names,
    jp=[rig.pose.bones[b.name].mmd_bone.name_j for b in bones],
    parents=[names.index(b.parent.name) if b.parent else -1 for b in bones],
    rest=np.array([b.matrix_local for b in bones]),
    heads=np.array([b.head_local for b in bones]),
    tails=np.array([b.tail_local for b in bones]),
)
(BASE / "asset-audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(BASE / "amber-native.blend"))
print(
    "ASSET_AUDIT", json.dumps({"bones": len(bones), "meshes": audit["meshes"]}, ensure_ascii=False)
)
