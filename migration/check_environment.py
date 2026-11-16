"""Start Kit before importing the compiled planner; no task assets or downloads."""

import sys
import os

sys.argv = [
    sys.argv[0],
    "--allow-root",
    "--portable-root",
    os.path.join(os.environ["XDG_CACHE_HOME"], "environment-check"),
]
from omni.isaac.kit import SimulationApp

app = SimulationApp({"headless": True, "multi_gpu": False, "width": 64, "height": 64})
try:
    import json
    import numpy as np
    import torch
    from curobo.wrap.reacher.motion_gen import MotionGen
    from curobo.curobolib import kinematics_fused_cu

    print("ENVIRONMENT_VERSIONS", sys.version, torch.__version__, np.__version__, flush=True)
    assert sys.version_info[:2] == (3, 10), sys.version
    assert torch.__version__ == "2.2.2+cu118", torch.__version__
    # Kit can preload its bundled 1.26.0 despite the extra dependency target
    # containing 1.26.4. Record the actual import instead of assuming precedence.
    assert np.__version__ in {"1.26.0", "1.26.4"}, np.__version__
    assert torch.cuda.is_available()
    x = torch.ones(1, device="cuda")
    assert x.cpu().item() == 1
    print(
        "ENVIRONMENT_OK",
        json.dumps(
            {
                "torch": torch.__version__,
                "numpy": np.__version__,
                "numpy_file": np.__file__,
                "gpu": torch.cuda.get_device_name(),
                "capability": torch.cuda.get_device_capability(),
                "planner": MotionGen.__module__,
                "extension": kinematics_fused_cu.__file__,
            }
        ),
        flush=True,
    )
except BaseException:
    import traceback

    traceback.print_exc()
    sys.stdout.flush()
    sys.stderr.flush()
    # Kit plugin teardown can terminate the interpreter before Python reports
    # an exception. Preserve a nonzero status for this short-lived smoke test.
    os._exit(1)
else:
    app.close()
