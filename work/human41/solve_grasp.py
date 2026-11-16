import json
from human_control import *

h = Human()
H, f, report = h.solve_grasp([0.25, 0.36, 1.031])
q, p, err = h.solve_arm(H, multistart=True)
np.savez(BASE / "output/grasp-solution.npz", H=H, fingers=f, arm_q=q, local=h.finger_pose(f, p))
result = {"grasp": report, "wrist_position_error_m": err, "arm_q": q.tolist()}
(BASE / "output/grasp-solution.json").write_text(json.dumps(result, indent=2))
print("GRASP_SOLVED", result, flush=True)
