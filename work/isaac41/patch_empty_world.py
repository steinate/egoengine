"""Clear stale CuRobo obstacles before replacing the full collision world.

The bundled WorldMeshCollision.load_collision_model and WorldPrimitiveCollision
._load_collision_model_in_cache leave old GPU entries enabled for empty lists.
clear_world_cache zeros existing tensors in place, preserving CUDA graph pointers.
"""

from pathlib import Path

root = Path(__file__).resolve().parent
p = root / "src/InternDataEngine41/workflows/simbox/core/controllers/template_controller.py"
s = p.read_text()
old = """        if self.motion_gen is not None:
            self.motion_gen.update_world(obstacles)"""
new = """        if self.motion_gen is not None:
            # Bundled CuRobo retains old GPU obstacles when a new list is empty.
            # This is a complete world replacement, including removed objects.
            self.motion_gen.clear_world_cache()
            self.motion_gen.update_world(obstacles)"""
if old in s:
    assert s.count(old) == 2
    p.write_text(s.replace(old, new))
elif s.count(new) != 2:
    raise RuntimeError("Unexpected controller version")
print("Patched complete collision-world replacements in update/update_specific")
