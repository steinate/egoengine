import json, os, urllib.request, urllib.parse
from pathlib import Path

base = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
if not token:
    for p in [
        Path.home() / ".cache/huggingface/token",
        Path("/vepfs/public/pengjiaqi/cache/huggingface/token"),
        Path("/vepfs/public/pengjiaqi/data/hf_cache/token"),
    ]:
        if p.is_file():
            token = p.read_text().strip()
            break
headers = {"Authorization": "Bearer " + token} if token else {}
prefixes = [
    "InternDataAssets/assets/pick_and_place/pre-train-pick/assets/omniobject3d-bottle/google_scan-bottle_0011"
]
all_files = []
for prefix in prefixes:
    url = (
        "https://huggingface.co/api/datasets/InternRobotics/InternData-A1/tree/main/"
        + urllib.parse.quote(prefix, safe="/")
        + "?recursive=true&limit=1000"
    )
    files = []
    try:
        while url:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=headers), timeout=45
            ) as r:
                items = json.load(r)
                link = r.headers.get("Link", "")
            files.extend(x for x in items if x["type"] == "file")
            url = link.split(">")[0].lstrip("<") if 'rel="next"' in link else None
        if prefix.endswith(
            ("table_textures", "floor_textures", "background_textures", "envmap_lib")
        ):
            files = [x for x in files if not "/." in x["path"]][:2]
        all_files.extend(files)
        print(
            prefix,
            len(files),
            sum(x["size"] for x in files),
            [x["path"] for x in files[:3]],
            flush=True,
        )
    except Exception as e:
        print(prefix, type(e).__name__, str(e), flush=True)
(base / "assets/bottle-manifest.json").write_text(json.dumps(all_files, indent=2))
