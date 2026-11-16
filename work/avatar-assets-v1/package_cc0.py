import sys, json, shutil, zipfile, hashlib
from pathlib import Path

sys.path.insert(0, "/vepfs/public/pengjiaqi/interndata-human-pair/runtime41/kit/exts/omni.usd.libs")
from pxr import Usd, Sdf

B = Path("/vepfs/public/pengjiaqi/interndata-human-pair/avatar-assets-v1")
src = B / "usd/mpfb_cc0_adult_male"
out = B / "delivery"
dst = out / "cc0-avatar"
dst.mkdir(parents=True, exist_ok=True)
shutil.copytree(src / "textures", dst / "textures", dirs_exist_ok=True)
shutil.copy(src / "rigged.usdc", dst / "rigged.usdc")
stage = Usd.Stage.Open(str(dst / "rigged.usdc"))
rewritten = []
for p in stage.Traverse():
    for a in p.GetAttributes():
        v = a.Get()
        if isinstance(v, Sdf.AssetPath) and v.path:
            f = Path(v.path).name
            if (dst / "textures" / f).exists():
                a.Set(Sdf.AssetPath("textures/" + f))
                rewritten.append(f)
stage.GetRootLayer().Save()
shutil.copy(B / "mpfb2/LICENSE.ASSETS.md", dst / "LICENSE-CC0.txt")
shutil.copy(B / "README.txt", dst / "README.txt")
with zipfile.ZipFile(out / "mpfb-cc0-rigged-usd.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for p in dst.rglob("*"):
        if p.is_file():
            z.write(p, p.relative_to(dst))
print(
    "CC0_USD_PACKAGED",
    len(rewritten),
    "textures",
    hashlib.sha256((out / "mpfb-cc0-rigged-usd.zip").read_bytes()).hexdigest(),
    flush=True,
)
