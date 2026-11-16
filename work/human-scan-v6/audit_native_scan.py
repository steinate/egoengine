"""Render undeformed supplier scan with old/corrected UV in neutral lighting."""

import bpy, numpy as np
from pathlib import Path
from mathutils import Vector

R = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
B = R / "human-scan-v6"
OLD = R / "human-scan-v5"
bpy.ops.wm.open_mainfile(filepath=str(OLD / "scan-reduced.blend"))
obj = next(o for o in bpy.data.objects if o.type == "MESH")
mesh = obj.data
obj.scale = (0.01,) * 3
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
original = np.array([list(v.uv) for v in mesh.uv_layers.active.data])
mat = obj.data.materials[0]
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Subsurface Weight"].default_value = 0
bsdf.inputs["Roughness"].default_value = 0.6
tex = next(n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE")
em = mat.node_tree.nodes.new("ShaderNodeEmission")
mat.node_tree.links.new(tex.outputs["Color"], em.inputs["Color"])
mat.node_tree.links.new(em.outputs[0], mat.node_tree.nodes.get("Material Output").inputs["Surface"])
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 24
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "Medium High Contrast" if False else "None"
scene.render.resolution_x = 800
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.world = bpy.data.worlds.new("Neutral")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.25, 0.25, 0.25, 1)
center = Vector((0.071, 0, 0.429))
for side, sign in [("minus_y", -1), ("plus_y", 1)]:
    bpy.ops.object.camera_add(location=center + Vector((0, sign * 0.6, 0)))
    camera = bpy.context.object
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 0.225
    scene.camera = camera
    bpy.ops.object.light_add(type="AREA", location=center + Vector((-0.1, sign * 0.35, 0.13)))
    light = bpy.context.object
    light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
    light.data.energy = 8
    light.data.size = 0.35
    for name, flip in [("previous", False), ("native_fixed", True)]:
        uv = original.copy()
        if flip:
            uv[:, 1] = 1 - uv[:, 1]
        mesh.uv_layers.active.data.foreach_set("uv", uv.ravel())
        mesh.update()
        scene.render.filepath = str(B / f"audit-{side}-{name}.png")
        bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(light, do_unlink=True)
    bpy.data.objects.remove(camera, do_unlink=True)
print("NATIVE_SCAN_AUDIT_DONE", flush=True)
