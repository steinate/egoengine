"""Regression checks for real preflight pitfalls: randomized defaults and dexterous annotations."""

import json, subprocess, sys, tempfile, unittest
from pathlib import Path
import yaml


class InventoryTest(unittest.TestCase):
    def check_case(
        self, kind, randomized, expected, arena=None, texture=False, incomplete_robot=False
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfgroot = root / "workflows/simbox/core/configs/tasks/basic/split_aloha/sample"
            cfgroot.mkdir(parents=True)
            skills = root / "workflows/simbox/core/skills"
            skills.mkdir(parents=True)
            (skills / "example.py").write_text(
                "@register_skill\nclass Pick: pass\n@register_skill\nclass Dexpick: pass\n"
            )
            model = root / "workflows/simbox/assets/category/existing"
            model.mkdir(parents=True)
            (model / "Aligned_obj.usd").touch()
            (
                model / ("dexpick_pose.yaml" if kind == "dexpick" else "Aligned_grasp_sparse.npy")
            ).touch()
            task = dict(
                asset_root="workflows/simbox/assets",
                objects=[
                    dict(
                        name="object",
                        path="category/nonexistent/Aligned_obj.usd"
                        if randomized
                        else "category/existing/Aligned_obj.usd",
                        target_class="RigidObject",
                        apply_randomization=randomized,
                    )
                ],
                skills=[dict(robot=[dict(left=[dict(name=kind, objects=["object"])])])],
            )
            if texture:
                task["objects"][0]["texture"] = dict(
                    texture_lib="missing_colors", apply_randomization=True, texture_id=0
                )
            if incomplete_robot:
                task["robots"] = [dict(name="second_robot_without_type")]
            if arena:
                task["arena_file"] = arena
            (cfgroot / "sample.yaml").write_text(yaml.safe_dump(dict(tasks=[task])))
            output = root / "result.json"
            subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("inventory.py")),
                    str(root),
                    str(output),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            row = json.loads(output.read_text())["rows"][0]
            self.assertEqual(row["status"], expected, row)

    def test_randomized_missing_default_uses_existing_pool(self):
        self.check_case("pick", True, "ready_for_runtime")

    def test_dexpick_uses_pose_yaml_not_sparse_npy(self):
        self.check_case("dexpick", False, "ready_for_runtime")

    def test_texture_pool_checked_before_randomized_object_shortcut(self):
        self.check_case("pick", True, "blocked_assets", texture=True)

    def test_missing_second_robot_declaration_is_source_block(self):
        self.check_case("pick", False, "blocked_source", incomplete_robot=True)

    def test_missing_arena_is_source_block(self):
        self.check_case("pick", False, "blocked_source", arena="missing.yaml")


if __name__ == "__main__":
    unittest.main()
