import bpy, sys, json, addon_utils
from pathlib import Path

B = Path("/vepfs/public/pengjiaqi/interndata-human-pair/avatar-assets-v1")
assets = B / "assets/makehuman"
out = B / "converted"
out.mkdir(exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
addon_utils.enable("bl_ext.user_default.mpfb", default_set=True)
from bl_ext.user_default.mpfb.services.humanservice import HumanService
from bl_ext.user_default.mpfb.services.targetservice import TargetService
from bl_ext.user_default.mpfb.services.exportservice import ExportService
from bl_ext.user_default.mpfb.services.objectservice import ObjectService
from bl_ext.user_default.mpfb.entities.objectproperties import HumanObjectProperties

h = HumanService.create_human()
for k, v in [
    ("gender", 1.0),
    ("age", 0.40),
    ("muscle", 0.55),
    ("weight", 0.50),
    ("height", 0.5),
    ("asian", 1.0),
    ("caucasian", 0.0),
    ("african", 0.0),
]:
    HumanObjectProperties.set_value(k, v, entity_reference=h)
TargetService.reapply_macro_details(h)
skin = next(assets.rglob("middleage_asian_male.mhmat"))
HumanService.set_character_skin(str(skin), h, skin_type="GAMEENGINE")
rig = HumanService.add_builtin_rig(h, "mixamo")
used = []
for fname, kind in [
    ("high-poly.mhclo", "Eyes"),
    ("eyebrow001.mhclo", "Eyebrows"),
    ("eyelashes01.mhclo", "Eyelashes"),
    ("teeth_base.mhclo", "Teeth"),
    ("short02.mhclo", "Hair"),
    ("male_casualsuit01.mhclo", "Clothes"),
    ("shoes01.mhclo", "Clothes"),
]:
    f = next(assets.rglob(fname))
    HumanService.add_mhclo_asset(str(f), h, asset_type=kind, material_type="GAMEENGINE")
    used.append(str(f))
# Bake helper masks into actual export geometry, keeping armature deformation live.
ExportService.bake_modifiers_remove_helpers(
    h, bake_masks=True, bake_subdiv=True, remove_helpers=True, also_proxy=True
)
for obj in bpy.data.objects:
    if obj.type == "MESH":
        for face in obj.data.polygons:
            face.use_smooth = True
bpy.ops.wm.save_as_mainfile(filepath=str(out / "mpfb_cc0_adult_male.blend"))
r = {
    "name": "mpfb_cc0_adult_male",
    "license": "CC0 assets and generated output",
    "source_code_license": "GPLv3",
    "skin": str(skin),
    "assets": used,
    "bone_count": len(rig.data.bones),
    "bones": [
        {
            "name": b.name,
            "parent": b.parent.name if b.parent else None,
            "head_world": list(rig.matrix_world @ b.head_local),
            "tail_world": list(rig.matrix_world @ b.tail_local),
        }
        for b in rig.data.bones
    ],
}
(B / "mpfb-inspection.json").write_text(json.dumps(r, indent=2))
print("MPFB_CREATED", r["bone_count"], [b["name"] for b in r["bones"]], flush=True)
