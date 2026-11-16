"""Require a complete cache tied to one immutable animation and source episode."""

from pathlib import Path
import numpy as np, json, hashlib

B = Path("/vepfs/public/pengjiaqi/interndata-human-pair/human-scan-v5")
N = 1507
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
contract = json.loads((B / "replay-contract.json").read_text())
for name, value in contract["source_hashes"].items():
    assert sha(B / "source" / name) == value, name
animation_hash = sha(B / "scan-animation.npz")
weights_hash = sha(B / "heat-weights.npz")
deformer_hash = sha(B / "hand_model.py")
parts = [
    json.loads((B / "scan-cache" / f"manifest-{start}-{stop}.json").read_text())
    for start, stop in [(0, 503), (503, 1006), (1006, 1507)]
]
assert sorted(i for part in parts for i in part["frames"]) == list(range(N))
assert all(part["animation_sha256"] == animation_hash for part in parts)
previous = {}
max_motion = {s: 0.0 for s in ["L", "R"]}
maximum_normal_error = 0.0
for i in range(N):
    with np.load(B / "scan-cache" / f"{i:04d}.npz") as data:
        assert int(data["source_frame"]) == i and str(data["animation_sha256"]) == animation_hash, i
        assert (
            str(data["weights_sha256"]) == weights_hash
            and str(data["deformer_sha256"]) == deformer_hash
        ), i
        for side in ["L", "R"]:
            points = data[side + "_points"]
            normals = data[side + "_normals"]
            assert (
                points.shape == normals.shape
                and np.isfinite(points).all()
                and np.isfinite(normals).all()
            )
            if side in previous:
                max_motion[side] = max(
                    max_motion[side], float(np.linalg.norm(points - previous[side], axis=1).max())
                )
            previous[side] = points.copy()
            maximum_normal_error = max(
                maximum_normal_error, float(np.max(abs(np.linalg.norm(normals, axis=1) - 1)))
            )
    if i % 300 == 0:
        print("VERIFIED_CACHE", i, flush=True)
report = {
    "frames": N,
    "fps": 15,
    "duration_s": N / 15,
    "animation_sha256": animation_hash,
    "source_hashes": contract["source_hashes"],
    "source_unchanged": True,
    "all_frames_present": True,
    "all_cache_animation_hashes_match": True,
    "max_vertex_step_m": max_motion,
    "max_normal_length_error": maximum_normal_error,
    "heat_weights_sha256": sha(B / "heat-weights.npz"),
    "caveat": "Visual replay of original robot object motion, not a new physical human grasp rollout",
}
(B / "cache-verification.json").write_text(json.dumps(report, indent=2))
print("CACHE_VERIFIED", json.dumps(report), flush=True)
