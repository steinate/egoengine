"""Official plan_with_render workflow with a task-local stable placement skill.

No object poses, contacts, collision flags or physics constraints are overwritten.
"""

import sys, argparse, json
from pathlib import Path

ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
BASE = ROOT / "robot-stack-v2"
p = argparse.ArgumentParser()
p.add_argument("--trial", default="trial01")
p.add_argument("--seed", type=int, default=42)
a = p.parse_args()
OUT = BASE / a.trial
OUT.mkdir(exist_ok=True)
sys.argv = [
    sys.argv[0],
    "--allow-root",
    "--portable-root",
    str(ROOT / "cache41/kit"),
    f"--/log/file={OUT}/kit.log",
]
from nimbus.utils.utils import init_env

init_env()
import workflows

original_import = workflows.import_extensions


def install(kind):
    original_import(kind)
    import numpy as np
    from scipy.spatial.transform import Rotation as R
    from pxr import UsdGeom, Usd
    from core.skills.place import Place
    from core.skills.base_skill import register_skill
    from core.utils.constants import CUROBO_BATCH_SIZE
    from omni.isaac.core.utils.transformations import tf_matrix_from_pose
    from workflows.base import NimbusWorkFlow

    @register_skill
    class StablePlace(Place):
        def generate_constrained_rotation_batch(self, batch_size=3000):
            # Exact upright object orientations, sorted around its present yaw.
            # Official Place still performs reachability/collision planning.
            objR = self.T_world_obj[:3, :3]
            yaw = np.arctan2(objR[1, 0], objR[0, 0])
            if "left1" in self.place_obj.name:
                cR = self.T_world_container[:3, :3]
                yaw = np.arctan2(cR[1, 0], cR[0, 0])
            offsets = np.deg2rad(
                [
                    0,
                    90,
                    -90,
                    180,
                    5,
                    -5,
                    85,
                    95,
                    -85,
                    -95,
                    175,
                    -175,
                    10,
                    -10,
                    80,
                    100,
                    -80,
                    -100,
                    170,
                    -170,
                ]
            )
            desired = R.from_euler("z", yaw + offsets[:CUROBO_BATCH_SIZE]).as_matrix()
            return self.T_base_world[:3, :3] @ desired @ self.T_obj_ee[:3, :3]

        def sample_gripper_place_traj(self):
            result = super().sample_gripper_place_traj()
            # Retract in world +Z, regardless of sampled gripper orientation.
            result[2][0] = result[1][0] + self.T_base_world[:3, :3] @ np.array([0.0, 0.0, 0.14])
            print(
                "STABLE_PLACE_TARGET",
                self.pick_obj.name,
                self.place_obj.name,
                "release",
                result[1][0].tolist(),
                "up",
                result[2][0].tolist(),
                flush=True,
            )
            return result

        def simple_generate_manip_cmds(self):
            self.controller.plan_config.time_dilation_factor = float(
                self.skill_cfg.get("slow_factor", 0.45)
            )
            super().simple_generate_manip_cmds()

        def is_done(self):
            # These commands execute once and do not plan a motion to their pose.
            if self.manip_list and self.manip_list[0][2] in (
                "update_pose_cost_metric",
                "update_specific",
                "detach_obj",
            ):
                self.manip_list.pop(0)
                done = not self.manip_list
            else:
                done = super().is_done()
            if done:
                self.controller.plan_config.time_dilation_factor = 1.0
            return done

        def is_success(self, th=0.0):
            if "left1" not in self.place_obj.name:
                return super().is_success(th)
            upper = np.asarray(self.pick_obj.get_local_pose()[0])
            lower = np.asarray(self.place_obj.get_local_pose()[0])
            delta = upper - lower
            ok = bool(np.linalg.norm(delta[:2]) < 0.015 and 0.045 < delta[2] < 0.07)
            print("STACK_AFTER_RETRACT", ok, "delta", delta.tolist(), flush=True)
            return ok

    WF = NimbusWorkFlow.workflows[kind]
    old_record = WF._record_rgb_depth

    def record(self, step_idx):
        old_record(self, step_idx)
        if not hasattr(self, "_stack_rows"):
            return
        data = {}
        for name, obj in self.task.objects.items():
            if name not in ["place_object", "pick_object_left1", "pick_object_right1"]:
                continue
            pos, quat = obj.get_local_pose()
            data[name] = np.r_[pos, quat]
        data["step"] = step_idx
        self._stack_rows.append(data)
        phase = []
        if self.skills:
            for robot, seq in self.skills[0].items():
                if seq:
                    for arm in seq[0]:
                        if arm:
                            s = arm[0]
                            phase.append(
                                f"{s.controller.lr_name}:{s.__class__.__name__}:{s.manip_list[0][2] if s.manip_list else 'done'}"
                            )
        phase = " ".join(phase)
        if phase != getattr(self, "_last_stack_phase", None):
            self._stack_events.append(
                {"frame": len(self._stack_rows) - 1, "step": step_idx, "phase": phase}
            )
            self._last_stack_phase = phase
            print("PHASE", step_idx, phase, flush=True)
        if step_idx % 40 == 0:
            import cv2

            cam = self.task.cameras["split_aloha_head"]
            rgb = cam.get_observations()["color_image"]
            cv2.imwrite(str(OUT / f"head-{step_idx:04d}.jpg"), rgb[:, :, :3][:, :, ::-1])

    WF._record_rgb_depth = record
    old_run = WF.plan_with_render

    def run(self):
        self._stack_rows = []
        self._stack_events = []
        self.stage.Export(str(OUT / "initial-scene.usdc"))
        try:
            n = old_run(self)
            print("OFFICIAL_WORKFLOW_FRAMES", n, flush=True)
            (OUT / "result.json").write_text(
                json.dumps({"official_workflow_frames": n, "seed": a.seed}, indent=2)
            )
            return n
        finally:
            rows = self._stack_rows
            if rows:
                np.savez_compressed(
                    OUT / "diagnostic-tracks.npz",
                    **{k: np.array([r[k] for r in rows]) for k in rows[0]},
                )
            (OUT / "events.json").write_text(json.dumps(self._stack_events, indent=2))
            # Preserve failures separately; only upstream writer output is accepted.
            if len(rows) > 2 and (
                not (OUT / "result.json").exists()
                or not json.loads((OUT / "result.json").read_text())["official_workflow_frames"]
            ):
                self.logger.save(str(OUT / "diagnostic-failed"), "failed", save_img=True)

    WF.plan_with_render = run


workflows.import_extensions = install
from nimbus.utils.flags import set_debug_mode, set_random_seed
from nimbus.utils.config_processor import ConfigProcessor
from nimbus import run_data_engine

set_debug_mode(True)
set_random_seed(a.seed)
config = ConfigProcessor().process_config(str(BASE / "pipeline.yaml"), cli_args=[])
run_data_engine(config, a.seed)
