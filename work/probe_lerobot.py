import json, urllib.request, urllib.parse
from pathlib import Path

base = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
token = None
for p in [
    Path.home() / ".cache/huggingface/token",
    Path("/vepfs/public/pengjiaqi/cache/huggingface/token"),
    Path("/vepfs/public/pengjiaqi/data/hf_cache/token"),
]:
    if p.is_file():
        token = p.read_text().strip()
        break
headers = {"Authorization": "Bearer " + token} if token else {}


def read(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as r:
        return r.read()


def tree(path):
    return json.loads(
        read(
            "https://huggingface.co/api/datasets/InternRobotics/InternData-A1/tree/main/"
            + path
            + "?limit=1000"
        )
    )


path = "sim_updated"
for level in range(6):
    items = tree(path)
    names = [x["path"] for x in items]
    print(path, names[:20], flush=True)
    if any(x.endswith("/meta") for x in names):
        info_path = path + "/meta/info.json"
        data = read(
            "https://huggingface.co/datasets/InternRobotics/InternData-A1/resolve/main/" + info_path
        )
        (base / "outputs/lerobot-info.json").write_bytes(data)
        d = json.loads(data)
        print("FEATURES", list(d["features"]), flush=True)
        (base / "outputs/lerobot-source.txt").write_text(info_path + "\n")
        break
    dirs = [x["path"] for x in items if x["type"] == "directory"]
    preferences = ["pick_and_place_tasks", "franka", "single_pick", "omniobject3d-bottle"]
    preferred = [x for key in preferences for x in dirs if x.split("/")[-1] == key]
    if not dirs:
        break
    path = preferred[0] if preferred else dirs[0]
