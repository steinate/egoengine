import bpy, json, numpy as np
from pathlib import Path

B = Path("/vepfs/public/pengjiaqi/interndata-human-pair/avatar-assets-v1")
out = B / "converted"
out.mkdir(exist_ok=True)
reports = []
for folder in sorted((B / "assets/renderpeople").glob("*_FBX")):
    # Vendor archives contain Windows backslashes on two assets.
    for p in list(folder.iterdir()):
        if "\\" in p.name:
            dest = folder / Path(p.name.replace("\\", "/"))
            dest.parent.mkdir(exist_ok=True, parents=True)
            p.rename(dest)
    f = next(folder.glob("*_zup_a.fbx"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(f), use_anim=False, automatic_bone_orientation=False)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    bones = [
        {
            "name": b.name,
            "parent": b.parent.name if b.parent else None,
            "head_world": list(arm.matrix_world @ b.head_local),
            "tail_world": list(arm.matrix_world @ b.tail_local),
            "length_m": float((arm.matrix_world.to_3x3() @ (b.tail_local - b.head_local)).length),
        }
        for b in arm.data.bones
    ]
    imgs = []
    for p in sorted((folder / "tex").glob("*")):
        im = bpy.data.images.load(str(p), check_existing=True)
        imgs.append({"file": str(p), "size": list(im.size)})
    coords = np.array([list(o.matrix_world @ v.co) for o in meshes for v in o.data.vertices])
    name = f.name.replace("_zup_a.fbx", "")
    report = {
        "name": name,
        "source": str(f),
        "bone_count": len(bones),
        "bones": bones,
        "meshes": [
            {
                "name": o.name,
                "vertices": len(o.data.vertices),
                "faces": len(o.data.polygons),
                "vertex_groups": len(o.vertex_groups),
                "armature_modifiers": [
                    m.object.name for m in o.modifiers if m.type == "ARMATURE" and m.object
                ],
            }
            for o in meshes
        ],
        "bounds_m": [coords.min(0).tolist(), coords.max(0).tolist()],
        "textures": imgs,
    }
    reports.append(report)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{name}.blend"))
    print("ASSET", name, "BONES", len(bones), "NAMES", [b["name"] for b in bones], flush=True)
(B / "scan-inspection.json").write_text(json.dumps(reports, indent=2))
print("SCAN_INSPECTION_DONE", flush=True)
