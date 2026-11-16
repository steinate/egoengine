"""Compatibility entry point for the shared verified robot episode exporter."""

from pathlib import Path
import runpy

runpy.run_path(
    str(Path(__file__).resolve().parent.parent / "robot-stack-v2/export_episode.py"),
    run_name="__main__",
)
