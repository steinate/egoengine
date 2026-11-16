"""Minimal compatibility fix for the bundled CuRobo on Python 3.11."""

from pathlib import Path

root = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
for base in [root / "assets/InternDataAssets/curobo/src", root / "env/curobo-built"]:
    p = base / "curobo/rollout/rollout_base.py"
    s = p.read_text()
    if "goal_pose: Pose = Pose()" not in s:
        assert "goal_pose: Pose = field(default_factory=Pose)" in s
        continue
    s = s.replace("from dataclasses import dataclass", "from dataclasses import dataclass, field")
    s = s.replace("goal_pose: Pose = Pose()", "goal_pose: Pose = field(default_factory=Pose)")
    p.write_text(s)
    print("Patched", p)

for base in [root / "assets/InternDataAssets/curobo/src", root / "env/curobo-built"]:
    p = base / "curobo/util/sample_lib.py"
    s = p.read_text()
    old = "[n_samples], device=self.tensor_args.device, dtype=self.tensor_args.dtype"
    if old in s:
        s = s.replace(old, "[n_samples]")
        p.write_text(s)
        print("Fixed torch.Size arguments", p)
