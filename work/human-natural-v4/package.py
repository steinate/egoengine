import zipfile, shutil, json, hashlib
from pathlib import Path

root = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
base = root / "human-natural-v4"
out = base / "delivery"
for name in [
    "human-animation.npz",
    "grasp-refit.npz",
    "grasp-refit.json",
    "motion-comparison.json",
    "finger-contact-refinement.json",
    "camera-continuity.json",
    "README.txt",
]:
    shutil.copy(base / name, out / name)
for name in ["contact-schedule.json", "robot-stack-validation.json"]:
    shutil.copy(base / "source" / name, out / name)
with zipfile.ZipFile(out / "complete-pair-data-and-code.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(out.iterdir()):
        if p.suffix in [".npz", ".json", ".txt"]:
            z.write(p, "data/" + p.name)
    for p in sorted(base.iterdir()):
        if p.suffix in [".py", ".sh"]:
            z.write(p, "code/" + p.name)
checks = {
    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in out.iterdir()
    if p.is_file() and p.name != "checksums.json"
}
(out / "checksums.json").write_text(json.dumps(checks, indent=2))
print("PACKAGE_DONE", len(checks))
