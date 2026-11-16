"""Controlled contact experiment: replay saved controls with chosen physics dt.

This is a diagnostic, not an official pipeline reproduction or accepted episode.
The same robot/object assets and initial robot/object state are used; decorative
distractors are omitted. Control/video rate stays 30 Hz across physics substeps.
"""

import argparse, sys, json, pickle
from pathlib import Path
import numpy as np
import lmdb
from scipy.spatial.transform import Rotation

p = argparse.ArgumentParser()
p.add_argument("--substeps", type=int, default=1)
p.add_argument("--force", type=float)
p.add_argument("--output", required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[3]
out = Path(a.output)
out.mkdir(parents=True, exist_ok=False)
episode = (
    root
    / "outputs41/official-single-pick/BananaBaseTask/franka/single_pick/omniobject3d-bottle/2026-11-12_09_05_07_712695"
)
env = lmdb.open(str(episode / "lmdb"), readonly=True, lock=False)
with env.begin() as tx:

    def get(k):
        return np.asarray(pickle.loads(tx.get(k.encode())))

    arm = get("master_actions.joint.position")
    gripper = get("master_actions.gripper.openness").reshape(-1)
    initial_arm = get("states.joint.position")[0]
    initial_width = get("states.gripper.position")[0][0]
    base = get("T_world_base")[0]
    initial_p = get("pick_object_left/translation")[0]
    initial_q = get("pick_object_left/orientation")[0]
    scale = get("pick_object_left/scale")[0]
sys.argv = [
    sys.argv[0],
    "--allow-root",
    "--portable-root",
    str(root / "cache41/kit"),
    f"--/log/file={out}/kit.log",
]
from nimbus.utils.utils import init_env

init_env()
import workflows

original_import = workflows.import_extensions


def import_extensions(kind):
    original_import(kind)
    from workflows.base import NimbusWorkFlow

    cls = NimbusWorkFlow.workflows[kind]

    def experiment(self):
        import imageio.v2 as imageio
        from omni.isaac.sensor import Camera
        from omni.isaac.core.utils.xforms import get_world_pose

        r = self.task.robots["franka"]
        o = self.task.objects["pick_object_left"]
        world = self.world
        world.set_simulation_dt(physics_dt=1 / (30 * a.substeps), rendering_dt=1 / 30)
        r.set_world_pose(base[:3, 3], Rotation.from_matrix(base[:3, :3]).as_quat()[[3, 0, 1, 2]])
        joints = np.r_[initial_arm, initial_width / 2, initial_width / 2]
        r.set_joint_positions(joints)
        r.set_joint_velocities(np.zeros(9))
        r.apply_action(joints[:8], np.arange(8))
        o.set_local_pose(initial_p, initial_q)
        o.set_local_scale(scale)
        o.set_linear_velocity(np.zeros(3))
        o.set_angular_velocity(np.zeros(3))
        if a.force is not None:
            r._articulation_view.set_max_efforts(
                np.array([[a.force]], dtype=np.float32), joint_indices=np.array([7])
            )
        actual_force = float(
            r._articulation_view.get_max_efforts(joint_indices=np.array([7]))[0, 0]
        )
        eye = np.array([0.45, 0.5, 1.15])
        target = np.array([0.08, 0.05, 0.86])
        z = eye - target
        z /= np.linalg.norm(z)
        x = np.cross([0, 0, 1.0], z)
        x /= np.linalg.norm(x)
        y = np.cross(z, x)
        camera = Camera("/World/ContactAuditCamera", resolution=(1280, 720), frequency=30)
        camera.set_world_pose(
            eye,
            Rotation.from_matrix(np.stack([x, y, z], axis=1)).as_quat()[[3, 0, 1, 2]],
            camera_axes="usd",
        )
        camera.set_clipping_range(0.01, 100)
        camera.initialize()
        self.stage.GetPrimAtPath("/World/ContactAuditCamera").GetAttribute("focalLength").Set(26.0)
        for _ in range(15):
            world.render()
        rows = {
            "object_translation": [],
            "object_orientation": [],
            "object_scale": [],
            "T_world_hand": [],
            "joint_state": [],
            "gripper_contact_force": [],
        }

        def transform(p, q):
            t = np.eye(4)
            t[:3, 3] = p
            t[:3, :3] = Rotation.from_quat(np.asarray(q)[[1, 2, 3, 0]]).as_matrix()
            return t

        with imageio.get_writer(out / "contact.mp4", fps=30, codec="libx264", quality=8) as writer:
            for i in range(len(arm)):
                op, oq = o.get_world_pose()
                hp, hq = get_world_pose(r.fl_ee_path)
                rows["object_translation"].append(op)
                rows["object_orientation"].append(oq)
                rows["object_scale"].append(o.get_local_scale())
                rows["T_world_hand"].append(transform(hp, hq))
                rows["joint_state"].append(r.get_joint_positions())
                rows["gripper_contact_force"].append(
                    np.asarray(
                        self.task.pickcontact_views["franka"]["left"][
                            "pick_object_left"
                        ].get_contact_force_matrix()
                    )
                )
                rgb = camera.get_rgba()[:, :, :3].astype(np.uint8)
                writer.append_data(rgb)
                if i in [0, 70, 95, 129]:
                    imageio.imwrite(out / f"frame-{i:03d}.png", rgb)
                r.apply_action(np.r_[arm[i], 0.04 if gripper[i] > 0.5 else 0.0], np.arange(8))
                for _ in range(a.substeps):
                    world.step(render=False)
                world.render()
        np.savez_compressed(
            out / "contact-tracks.npz",
            **{k: np.asarray(v) for k, v in rows.items()},
            control_dt=1 / 30,
            physics_dt=1 / (30 * a.substeps),
        )
        xyz = np.asarray(rows["object_translation"])
        result = {
            "diagnostic_only": True,
            "substeps": a.substeps,
            "physics_dt": world.get_physics_dt(),
            "actual_gripper_max_force_N": actual_force,
            "frames": len(arm),
            "max_lift_m": float(xyz[:, 2].max() - xyz[0, 2]),
            "final_lift_m": float(xyz[-1, 2] - xyz[0, 2]),
            "source_episode": str(episode),
        }
        (out / "result.json").write_text(json.dumps(result, indent=2))
        print("CONTACT_REPLAY_DONE", json.dumps(result), flush=True)
        return []

    cls.generate_seq = experiment


workflows.import_extensions = import_extensions
from nimbus.utils.config_processor import ConfigProcessor
from nimbus.utils.flags import set_debug_mode, set_random_seed
from nimbus import run_data_engine

set_debug_mode(True)
set_random_seed(42)
config = ConfigProcessor().process_config("human_pair/configs/plan.yaml", cli_args=[])
run_data_engine(config, 42)
