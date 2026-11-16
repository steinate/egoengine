"""Inspect and reduce the vendor's dense scan while retaining its own UVs."""

import bpy, json, numpy as np
from pathlib import Path
from mathutils import Vector

B = Path("/vepfs/public/pengjiaqi/interndata-human-pair/human-scan-v5")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=str(B / "assets/Sample_Hand_CleanScan.OBJ"))
o = next(o for o in bpy.data.objects if o.type == "MESH")
bpy.context.view_layer.objects.active = o
o.select_set(True)
# OBJ is a ZBrush Y-up source: undo Blender's default OBJ axis conversion
# by inspecting in imported world axes, then save those coordinates explicitly.
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
v = np.empty(len(o.data.vertices) * 3, dtype=np.float32)
o.data.vertices.foreach_get("co", v)
v = v.reshape(-1, 3)
report = {
    "source_vertices": len(v),
    "source_faces": len(o.data.polygons),
    "bounds": [v.min(0).tolist(), v.max(0).tolist()],
}
print("SOURCE", report, flush=True)
dec = o.modifiers.new("ScanResolution", "DECIMATE")
dec.decimate_type = "UNSUBDIV"
dec.iterations = 6
bpy.ops.object.modifier_apply(modifier=dec.name)
for f in o.data.polygons:
    f.use_smooth = True
v = np.empty(len(o.data.vertices) * 3, dtype=np.float32)
o.data.vertices.foreach_get("co", v)
v = v.reshape(-1, 3)
report.update(vertices=len(v), faces=len(o.data.polygons), uv_layers=len(o.data.uv_layers))
print("REDUCED", report, flush=True)
mat = bpy.data.materials.new("ScannedSkin")
mat.use_nodes = True
n = mat.node_tree.nodes
l = mat.node_tree.links
p = n.get("Principled BSDF")
p.inputs["Roughness"].default_value = 0.48
p.inputs["Subsurface Weight"].default_value = 0.12
tex = n.new("ShaderNodeTexImage")
tex.image = bpy.data.images.load(str(B / "assets/Sample_Hand_Diffuse.png"))
l.new(tex.outputs["Color"], p.inputs["Base Color"])
report["diffuse_size"] = list(tex.image.size)
o.data.materials.clear()
o.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=str(B / "scan-reduced.blend"))
np.savez_compressed(B / "scan-points.npz", points=v)
(B / "scan-inspection.json").write_text(json.dumps(report, indent=2))
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 12
scene.render.resolution_x = 1000
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.world = bpy.data.worlds.new("World")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.25, 0.25, 0.25, 1)
center = Vector((v.min(0) + v.max(0)) / 2)
span = float(np.max(v.max(0) - v.min(0)))
for idx, direction in enumerate([(0, -1, 0), (0, 1, 0), (1, 0, 0)]):
    d = Vector(direction)
    bpy.ops.object.camera_add(location=center + d * span * 2)
    cam = bpy.context.object
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = span * 1.15
    scene.camera = cam
    bpy.ops.object.light_add(
        type="AREA", location=center + d * span + Vector((span * 0.3, 0, span * 0.4))
    )
    lamp = bpy.context.object
    lamp.rotation_euler = (center - lamp.location).to_track_quat("-Z", "Y").to_euler()
    lamp.data.energy = span * span * 80
    lamp.data.shape = "DISK"
    lamp.data.size = span
    scene.render.filepath = str(B / f"scan-view-{idx}.png")
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(lamp, do_unlink=True)
    bpy.data.objects.remove(cam, do_unlink=True)
print("SCAN_INSPECT_DONE", report, flush=True)
