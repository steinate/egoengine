"""A timed-out shell must not leave its SIGTERM-ignoring simulator child running."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from process_control import terminate_group


@unittest.skipUnless(os.name == "posix", "process groups require POSIX")
class ProcessGroupTest(unittest.TestCase):
    def test_child_is_killed_even_when_leader_exits_on_term(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = "import signal,time,pathlib,sys;signal.signal(signal.SIGTERM,signal.SIG_IGN);p=pathlib.Path(sys.argv[1]);(p/'ready').touch();time.sleep(1.5);(p/'escaped').touch();time.sleep(30)"
            leader = "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]]);time.sleep(30)"
            proc = subprocess.Popen(
                [sys.executable, "-c", leader, child, tmp], start_new_session=True
            )
            try:
                deadline = time.monotonic() + 5
                while not (root / "ready").exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue((root / "ready").exists())
                terminate_group(proc, grace_seconds=0.1)
                time.sleep(1.6)
                self.assertFalse(
                    (root / "escaped").exists(),
                    "SIGTERM-ignoring child escaped after leader exited",
                )
            finally:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()


if __name__ == "__main__":
    unittest.main()
