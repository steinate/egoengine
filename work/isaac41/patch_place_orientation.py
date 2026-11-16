"""Optional carry-and-place orientation preservation for a tabletop task."""

from pathlib import Path

root = Path(__file__).resolve().parent
p = root / "src/InternDataEngine41/workflows/simbox/core/skills/place.py"
s = p.read_text()
old = """    def generate_constrained_rotation_batch(self, batch_size=3000):
        filter_conditions = {"""
new = """    def generate_constrained_rotation_batch(self, batch_size=3000):
        if self.skill_cfg.get("keep_grasp_orientation", False):
            # Keep the carried object orientation while translating across the table.
            R_base_ee = (self.T_base_world @ self.T_world_ee)[:3, :3]
            return np.repeat(R_base_ee[None], CUROBO_BATCH_SIZE, axis=0)
        filter_conditions = {"""
if old in s:
    p.write_text(s.replace(old, new))
elif new not in s:
    raise RuntimeError("Unexpected Place implementation")
print("Added opt-in keep_grasp_orientation for tabletop placement")
