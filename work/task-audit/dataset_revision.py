"""Pin metadata and downloads to one dataset commit within each audit workspace."""

import datetime
import json
from pathlib import Path
import re
import urllib.request


def pinned_revision(hf_directory: Path, token: str):
    hf_directory.mkdir(parents=True, exist_ok=True)
    receipt = hf_directory / "repository-revision.json"
    if receipt.exists():
        data = json.loads(receipt.read_text())
    else:
        req = urllib.request.Request(
            "https://hf-mirror.com/api/datasets/InternRobotics/InternData-A1"
        )
        req.add_unredirected_header("Authorization", "Bearer " + token)
        with urllib.request.urlopen(req, timeout=30) as response:
            info = json.load(response)
        data = dict(
            repository="InternRobotics/InternData-A1",
            revision=info["sha"],
            last_modified=info.get("lastModified"),
            observed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        receipt.write_text(json.dumps(data, indent=2))
    assert re.fullmatch(r"[0-9a-f]{40}", data["revision"])
    return data["revision"]
