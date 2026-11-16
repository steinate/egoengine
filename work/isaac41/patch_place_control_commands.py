"""Advance executed control-only Place commands without waiting for an old pose.

Controller.forward(skip_plan=True) applies these commands without a trajectory.
Waiting for its snapshot EE pose can stall forever while physics is still moving:
the fallback holds the current joint positions, and num_last_cmd never increments.
"""

from pathlib import Path

root = Path(__file__).resolve().parent
p = root / "src/InternDataEngine41/workflows/simbox/core/skills/place.py"
s = p.read_text()
old = """    def is_done(self):
        if len(self.manip_list) == 0:
            return True
        if self.is_subtask_done"""
new = """    def is_done(self):
        if len(self.manip_list) == 0:
            return True
        if self.manip_list[0][2] in ("update_pose_cost_metric", "update_specific", "detach_obj"):
            # update_skill_states calls this after forward has executed the command.
            self.manip_list.pop(0)
            return len(self.manip_list) == 0
        if self.is_subtask_done"""
if old in s:
    p.write_text(s.replace(old, new))
elif new not in s:
    raise RuntimeError("Unexpected Place implementation")
print("Fixed completion of already-executed Place control commands")
