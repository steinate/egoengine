import concurrent.futures, hashlib, json, os, shutil, signal, subprocess, urllib.request
from pathlib import Path

r = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
os.environ["TMPDIR"] = str(r / "tmp/apt")
pid = 3625679
proc = Path(f"/proc/{pid}/cmdline")
if (
    proc.exists()
    and b"apt-get" in proc.read_bytes()
    and str(r / "cache41/apt").encode() in proc.read_bytes()
):
    os.kill(pid, signal.SIGTERM)
opts = [
    "-o",
    "Dir::State::lists=" + str(r / "cache41/apt/lists"),
    "-o",
    "Dir::Cache=" + str(r / "cache41/apt"),
    "-o",
    "Dir::Etc::parts=-",
]
names = ["gcc-11", "g++-11", "cpp-11", "libgcc-11-dev", "libstdc++-11-dev"]
ver = "11.5.0-1ubuntu1~24.04.1"
raw = subprocess.check_output(
    ["apt-cache", *opts, "show", *[n + "=" + ver for n in names]], text=True
)
items = {}
for block in raw.split("\n\n"):
    d = {}
    for line in block.splitlines():
        if line and line[0] != " " and ": " in line:
            k, v = line.split(": ", 1)
            d[k] = v
    if d.get("Package") in names and d.get("Version") == ver:
        items[d["Package"]] = d
assert len(items) == len(names), items.keys()
dest = r / "downloads/gcc11-verified"
dest.mkdir(exist_ok=True)


def fetch(d):
    p = dest / Path(d["Filename"]).name
    old = r / "downloads/gcc11" / p.name
    if (
        old.exists()
        and old.stat().st_size == int(d["Size"])
        and hashlib.sha256(old.read_bytes()).hexdigest() == d["SHA256"]
    ):
        shutil.copy2(old, p)
    else:
        url = "https://mirrors.edge.kernel.org/ubuntu/" + d["Filename"]
        with urllib.request.urlopen(url, timeout=90) as response, p.open("wb") as f:
            shutil.copyfileobj(response, f)
    assert (
        p.stat().st_size == int(d["Size"])
        and hashlib.sha256(p.read_bytes()).hexdigest() == d["SHA256"]
    ), p
    print("Verified", p.name, flush=True)
    return p


with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    files = list(pool.map(fetch, items.values()))
for p in files:
    subprocess.run(["dpkg-deb", "-x", str(p), str(r / "env/gcc11")], check=True)
lib = r / "env/gcc11/usr/lib/x86_64-linux-gnu"
lib.mkdir(parents=True, exist_ok=True)
link = lib / "libstdc++.so.6"
if not link.exists():
    link.symlink_to("/usr/lib/x86_64-linux-gnu/libstdc++.so.6")
(r / "logs41/gcc11-manifest.json").write_text(json.dumps(items, indent=2))
subprocess.run([str(r / "env/gcc11/usr/bin/g++-11"), "--version"], check=True)
