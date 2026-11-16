"""Terminate the complete isolated simulator process group, including surviving Kit children."""

import os
import signal
import subprocess
import time


def terminate_group(process, grace_seconds=10):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass
    # The shell leader can exit before an Isaac child that ignores SIGTERM.
    # Kill remaining group members even when wait() above returned normally.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()
    time.sleep(0.2)  # allow killed descendants to release GPU handles before the lock is released
