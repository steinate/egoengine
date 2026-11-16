from pathlib import Path

root = Path(__file__).resolve().parent
p = root / "src/InternDataEngine41/workflows/simbox/core/skills/place.py"
s = p.read_text()
needle = "        ee2o_distance = np.linalg.norm(self.T_obj_ee[0:3, 3])"
extra = """        print("PLACE_TRANSFORMS", {"object": self.T_world_obj.tolist(), "ee": self.T_world_ee.tolist(), "base_world": self.T_base_world.tolist(), "obj_ee": self.T_obj_ee.tolist(), "object_mass": float(self.pick_obj.get_mass()), "object_velocity": self.pick_obj.get_linear_velocity().tolist()}, flush=True)
"""
if "PLACE_TRANSFORMS" not in s:
    p.write_text(s.replace(needle, extra + needle))
p = root / "src/InternDataEngine41/human_pair/diagnostics.py"
s = p.read_text()
old = "            return original(self)"
new = """            try:
                return original(self)
            finally:
                # Diagnostic plans may be failures: never put them in accepted output.
                self.save_seq(str(out/'diagnostic-episode'))"""
if old in s:
    p.write_text(s.replace(old, new))
print("Enabled phase transforms and clearly separated diagnostic episode recording")
