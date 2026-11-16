"""Exercise the official planning API for one unmodified task config, with explicit result stages."""

import argparse, json, time, traceback, sys, hashlib, subprocess
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("config", type=Path)
p.add_argument("output", type=Path)
p.add_argument("--seed", type=int, default=43)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
report = dict(
    config=str(a.config),
    config_sha256=hashlib.sha256(a.config.read_bytes()).hexdigest(),
    runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    engine_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    seed=a.seed,
    status="initializing",
    stages=[],
)
started = time.monotonic()


def save():
    report["wall_seconds"] = time.monotonic() - started
    (a.output / "result.json").write_text(json.dumps(report, indent=2))


def phase(name):
    report["stages"].append(name)
    save()
    print("AUDIT_STAGE", name, flush=True)


sys.argv = [sys.argv[0], "--allow-root", f"--/log/file={a.output}/kit.log"]
from nimbus.utils.utils import init_env

init_env()
from omni.isaac.kit import SimulationApp

app = SimulationApp(
    dict(
        headless=True,
        multi_gpu=False,
        width=320,
        height=180,
        renderer="RayTracedLighting",
        anti_aliasing=0,
    )
)
try:
    from omni.isaac.core import World
    from nimbus.utils.flags import set_random_seed
    from workflows import import_extensions
    from workflows.base import create_workflow

    set_random_seed(a.seed)
    world = World(physics_dt=1 / 30, rendering_dt=1 / 30, stage_units_in_meters=1.0)
    import_extensions("SimBoxDualWorkFlow")
    phase("parse_config")
    wf = create_workflow("SimBoxDualWorkFlow", world, str(a.config), random_seed=a.seed)
    phase("initialize_scene")
    wf.init_task(0, need_preload=False)
    phase("randomize_layout")
    if not wf.randomization():
        report["status"] = "layout_failed"
    else:
        (a.output / "resolved-task.json").write_text(
            json.dumps(
                wf.task_cfg,
                indent=2,
                default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x),
            )
        )
        report["mode"] = "plan_with_render" if wf.task_cfg.get("fluid") else "generate_seq"
        phase("official_" + report["mode"])
        generated = (
            wf.plan_with_render() if report["mode"] == "plan_with_render" else wf.generate_seq()
        )
        report["frames"] = int(generated) if isinstance(generated, int) else len(generated)
        report["recorded_prim_frames"] = wf.world_recorder.get_total_steps()
        report["status"] = "planning_succeeded" if report["frames"] > 0 else "planning_failed"
        if report["frames"] > 0:
            # Raw official plan contains resolved layout, world poses and logger.
            (a.output / "official-plan.pkl").write_bytes(wf.dump_plan_info())
            wf.stage.Export(str(a.output / "scene.usdc"))
            report["plan_bytes"] = (a.output / "official-plan.pkl").stat().st_size
except Exception as error:
    report["status"] = "runtime_error"
    report["error"] = repr(error)
    report["traceback"] = traceback.format_exc()
    traceback.print_exc()
finally:
    save()
    print("AUDIT_RESULT", json.dumps(report), flush=True)
    app.close()
