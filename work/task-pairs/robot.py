"""Run upstream planning and record an immutable, task-independent paired source."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("episode", type=Path)
a = p.parse_args()
OUT = a.episode.resolve()
PROVENANCE = json.loads((OUT / "task-provenance.json").read_text())
sys.argv = [
    sys.argv[0],
    "--allow-root",
    "--/app/useFabricSceneDelegate=false",
    "--/app/hydraEngine/waitIdle=true",
    f"--/log/file={OUT}/kit.log",
]
from nimbus.utils.utils import init_env

init_env()
import workflows

original_import = workflows.import_extensions


def install(kind):
    original_import(kind)
    import numpy as np
    import cv2
    from pxr import Usd, UsdGeom
    from workflows.base import NimbusWorkFlow
    from omni.isaac.core.articulations import Articulation

    WF = NimbusWorkFlow.workflows[kind]
    old_run = WF.plan_with_render

    def run(self):
        started = time.perf_counter()
        # Reapply the configured cadence after asset loading resets the Kit timeline.
        dt = self.world.get_physics_dt()
        self.world.set_simulation_dt(physics_dt=dt, rendering_dt=dt)
        stage = self.stage
        # Imported robot USD carries an unused second PhysicsScene. Isaac's
        # time callback counts once per scene, duplicating time/step counters.
        # Bodies have no explicit simulationOwner: they use the main scene.
        main_scene = self.world.get_physics_context().prim_path
        disabled_scenes = []
        for pr in list(stage.Traverse()):
            if pr.GetTypeName() == "PhysicsScene" and str(pr.GetPath()) != main_scene:
                path = str(pr.GetPath())
                assert not any(
                    path in [str(v) for v in rel.GetTargets()]
                    for obj in stage.Traverse()
                    for rel in obj.GetRelationships()
                    if "simulationOwner" in rel.GetName()
                ), path
                pr.SetActive(False)
                disabled_scenes.append(path)
        print("DISABLED_UNUSED_PHYSICS_SCENES", disabled_scenes, flush=True)
        source = OUT / "source"
        source.mkdir(exist_ok=True)
        stage.Export(str(source / "scene.usdc"))
        (source / "resolved-task.json").write_text(
            json.dumps(
                self.task_cfg,
                indent=2,
                default=lambda v: v.tolist() if hasattr(v, "tolist") else str(v),
            )
        )
        prims = self.world_recorder.xform_prims
        paths = [str(pr.GetPath()) for pr in prims]
        robot = self.task.robots["split_aloha"]
        camera = self.task.cameras["split_aloha_head"]
        objects = {}
        for name, obj in self.task.objects.items():
            objects[name] = {
                "prim_path": obj.prim_path,
                "articulated": isinstance(obj, Articulation),
            }
            for attr in (
                "object_link_path",
                "object_base_path",
                "object_keypoints",
                "object_joint_index",
            ):
                if hasattr(obj, attr):
                    objects[name][attr] = getattr(obj, attr)
        meta = {
            "objects": objects,
            "prim_paths": paths,
            "robot_root": robot.prim_path,
            "camera_path": camera.prim_path,
            "physics_dt": self.world.get_physics_dt(),
            "head_resolution": list(camera.get_resolution()),
            "tcp_offset": robot.tcp_offset,
            "disabled_unused_physics_scenes": disabled_scenes,
            "clock": "Count explicit PhysX simulate(dt) calls; retain Isaac callback counters separately; assert rendering does not advance physics",
        }
        (source / "scene-meta.json").write_text(
            json.dumps(
                meta, indent=2, default=lambda v: v.tolist() if hasattr(v, "tolist") else str(v)
            )
        )
        rows, events = [], []
        video = cv2.VideoWriter(
            str(source / "robot-raw.mp4"),
            cv2.VideoWriter_fourcc(*"mp4v"),
            1 / self.world.get_physics_dt(),
            camera.get_resolution(),
        )
        assert video.isOpened()
        last_time = None
        explicit_steps = 0

        def matrix(path):
            return np.asarray(
                UsdGeom.Xformable(stage.GetPrimAtPath(path)).ComputeLocalToWorldTransform(
                    Usd.TimeCode.Default()
                )
            ).T

        def phase():
            result = []
            if self.skills:
                for sequences in self.skills[0].values():
                    if sequences:
                        for arm in sequences[0]:
                            if arm:
                                skill = arm[0]
                                result.append(
                                    {
                                        "side": skill.controller.lr_name,
                                        "skill": type(skill).__name__,
                                        "command": str(skill.manip_list[0][2])
                                        if skill.manip_list
                                        else "done",
                                        "objects": list(skill.skill_cfg.get("objects", [])),
                                    }
                                )
            return result

        def capture():
            nonlocal last_time
            t = explicit_steps * dt
            if last_time is not None and t <= last_time + 1e-8:
                return
            last_time = t
            poses = np.stack([matrix(x) for x in paths])
            row = {
                "time_s": t,
                "physics_step": explicit_steps,
                "isaac_callback_step": self.world.current_time_step_index,
                "isaac_callback_time_s": float(self.world.current_time),
                "prim_world": poses,
                "camera_world": matrix(camera.prim_path),
                "robot_q": robot.get_joint_positions().copy(),
            }
            for side, ee in [("L", robot.fl_ee_path), ("R", robot.fr_ee_path)]:
                row[side + "_ee_world"] = matrix(ee)
                row[side + "_tcp_world"] = matrix(ee) @ np.array(
                    [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, robot.tcp_offset], [0, 0, 0, 1]]
                )
            for name, obj in self.task.objects.items():
                row[name + "_world"] = matrix(obj.prim_path)
                if isinstance(obj, Articulation):
                    row[name + "_joints"] = obj.get_joint_positions().copy()
            row["gripper_width"] = (
                np.array(
                    [
                        robot.get_joint_positions()[robot.cfg["left_gripper_indices"]][0],
                        robot.get_joint_positions()[robot.cfg["right_gripper_indices"]][0],
                    ]
                )
                if hasattr(robot, "cfg")
                else np.zeros(2)
            )
            rgb = camera.get_observations()["color_image"][:, :, :3]
            assert rgb.shape[:2] == (360, 640)
            video.write(np.ascontiguousarray(rgb[:, :, ::-1]))
            current = phase()
            if not events or current != events[-1]["phase"]:
                events.append({"frame": len(rows), "time_s": t, "phase": current})
                print("PHASE", len(rows), current, flush=True)
            rows.append(row)
            if len(rows) == 20:
                elapsed = rows[-1]["time_s"] - rows[0]["time_s"]
                steps = rows[-1]["physics_step"] - rows[0]["physics_step"]
                print("CADENCE_CHECK", elapsed, steps, "expected", 19 * dt, 19, flush=True)
                assert abs(elapsed - 19 * dt) < 1e-6 and steps == 19, (
                    "Unexpected simulation cadence"
                )
            if len(rows) % 100 == 0:
                print(
                    "RECORDED",
                    len(rows),
                    "wall_seconds",
                    round(time.perf_counter() - started, 1),
                    flush=True,
                )

        # Observe physics after it advances; no robot or object poses are changed.
        old_step = self.world.step

        def step(*args, **kwargs):
            nonlocal explicit_steps
            # Exactly one explicit PhysX simulate(dt) call. Pause the timeline
            # around rendering to prevent app.update from simulating again.
            before = self.world.current_time
            self.world._timeline.pause()
            result = old_step(render=False, step_sim=False)
            self.world.get_physics_context()._step(current_time=explicit_steps * dt)
            after_physics = self.world.current_time
            assert after_physics > before + 1e-8, "PhysX did not advance"
            explicit_steps += 1
            if kwargs.get("render", args[0] if args else True):
                self.world.render()
            after_render = self.world.current_time
            if explicit_steps <= 3:
                print("STEP_TIMING", before, after_physics, after_render, flush=True)
            assert abs(after_render - after_physics) < 1e-8, "Rendering advanced physics"
            capture()
            return result

        self.world.step = step
        n, error = 0, None
        try:
            n = old_run(self)
            if n:
                for _ in range(30):
                    self.world.step(render=True)
            return n
        except BaseException as exc:
            error = repr(exc)
            raise
        finally:
            self.world.step = old_step
            video.release()
            if rows:
                data = {k: np.asarray([row[k] for row in rows]) for k in rows[0]}
                data["absolute_sim_time_s"] = data["time_s"].copy()
                data["time_s"] -= data["time_s"][0]
                data["frame_index"] = np.arange(len(rows))
                np.savez_compressed(source / "world-tracks.npz", **data)
                cadence_valid = bool(
                    np.allclose(np.diff(data["time_s"]), dt, atol=1e-7)
                    and np.all(np.diff(data["physics_step"]) == 1)
                )
            if rows:
                for event in events:
                    event["absolute_sim_time_s"] = event["time_s"]
                    event["time_s"] -= rows[0]["time_s"]
            (source / "events.json").write_text(json.dumps(events, indent=2))
            result = {
                "official_success": bool(n),
                "cadence_valid": cadence_valid if rows else False,
                "official_return_steps": n,
                "frames": len(rows),
                "fps": 1 / self.world.get_physics_dt(),
                "wall_seconds": time.perf_counter() - started,
                "error": error,
                "seed": PROVENANCE["seed"],
                "geometry_replay_only_after_success": True,
            }
            if rows:
                result["source_sha256"] = hashlib.sha256(
                    (source / "world-tracks.npz").read_bytes()
                ).hexdigest()
            (OUT / "result.json").write_text(json.dumps(result, indent=2))
            print("ROBOT_RESULT", json.dumps(result), flush=True)

    WF.plan_with_render = run


workflows.import_extensions = install
from nimbus.utils.flags import set_debug_mode, set_random_seed
from nimbus.utils.config_processor import ConfigProcessor
from nimbus import run_data_engine

set_debug_mode(True)
set_random_seed(PROVENANCE["seed"])
config = ConfigProcessor().process_config(str(OUT / "pipeline.yaml"), cli_args=[])
run_data_engine(config, PROVENANCE["seed"])
