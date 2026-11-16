"""Run one task, fail closed on missing plans, export/validate/render its replay."""

import argparse, json, subprocess, time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--existing-plan")
p.add_argument("--output-dir")
p.add_argument("--seed", type=int, default=42)
a = p.parse_args()
root = Path(__file__).resolve().parents[3]
launcher = root / "run_env41.sh"
out = (
    Path(a.output_dir)
    if a.output_dir
    else root / "outputs41" / ("verified-" + time.strftime("%Y%m%d-%H%M%S"))
)
out.mkdir(parents=True, exist_ok=False)


def run(name, module, *args):
    print("RUN", name, flush=True)
    with (out / (name + ".log")).open("w") as log:
        subprocess.run(
            [str(launcher), "-m", module, *map(str, args)],
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )


if a.existing_plan:
    plan = Path(a.existing_plan).resolve()
else:
    before = set((root / "outputs41/plan").rglob("*.pkl"))
    run("configure", "human_pair.make_task")
    run(
        "plan",
        "human_pair.engine_job",
        "--config",
        "human_pair/configs/plan.yaml",
        "--seed",
        a.seed,
        "--diagnostics",
    )
    new = set((root / "outputs41/plan").rglob("*.pkl")) - before
    if len(new) != 1:
        raise RuntimeError(f"Expected one newly saved successful plan, got {len(new)}")
    plan = new.pop()
for suffix in [".pkl", ".meta.json", ".scene.usdc"]:
    if not plan.with_suffix(suffix).is_file():
        raise FileNotFoundError(plan.with_suffix(suffix))
(out / "source-plan.txt").write_text(str(plan) + "\n")
tracks = out / "tracks.npz"
run("export", "human_pair.export_tracks", plan, "--output", tracks)
run(
    "validate",
    "human_pair.validate_episode",
    tracks,
    "--output",
    out / "trajectory-validation.json",
)
run(
    "render-overview",
    "human_pair.replay_scene",
    "--plan",
    plan,
    "--output",
    out / "overview.mp4",
    "--eye",
    1.1,
    -1.2,
    1.8,
    "--target",
    0,
    -0.18,
    1.05,
)
run("inspect-overview", "human_pair.inspect_video", out / "overview.mp4", tracks)
replay = json.loads((out / "overview.json").read_text())
validation = json.loads((out / "trajectory-validation.json").read_text())
assert replay["frames"] == validation["frames"]
assert replay["max_object_position_error_m"] < 1e-5
assert replay["max_object_rotation_error_deg"] < 0.01
(out / "pipeline-result.json").write_text(
    json.dumps(
        {
            "passed": True,
            "source_plan": str(plan),
            "output_directory": str(out),
            "trajectory": validation,
            "replay": replay,
        },
        indent=2,
    )
)
print("PIPELINE_OK", str(out), flush=True)
