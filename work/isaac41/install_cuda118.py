import hashlib, json, shutil, tarfile, urllib.request
from pathlib import Path

r = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
base = "https://developer.download.nvidia.com/compute/cuda/redist/"
meta = json.load(urllib.request.urlopen(base + "redistrib_11.8.0.json"))
dst = r / "env/cuda-11.8"
dst.mkdir(parents=True, exist_ok=True)
cache = r / "downloads/cuda118"
cache.mkdir(parents=True, exist_ok=True)
record = {}
for key in ["cuda_nvcc", "cuda_cudart", "cuda_cccl"]:
    info = meta[key]["linux-x86_64"]
    p = cache / Path(info["relative_path"]).name
    if not p.exists():
        urllib.request.urlretrieve(base + info["relative_path"], p)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest == info["sha256"], key
    print(key, p.stat().st_size, digest, flush=True)
    with tarfile.open(p) as t:
        top = t.getnames()[0].split("/")[0]
        t.extractall(cache, filter="data")
    shutil.copytree(cache / top, dst, dirs_exist_ok=True, symlinks=True)
    record[key] = info
if (dst / "lib").is_dir() and not (dst / "lib64").exists():
    (dst / "lib64").symlink_to("lib")
(r / "logs41/cuda118-manifest.json").write_text(json.dumps(record, indent=2))
