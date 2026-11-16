import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

base = Path("/vepfs/public/pengjiaqi/interndata-human-pair/human-natural-v4")
out = base / "delivery"
stats = {}
samples = [0, 137, 258, 433, 500, 780, 1000, 1044, 1191, 1331, 1431, 1506]
for view in ["ego", "front"]:
    folder = base / "render" / view
    assert sorted(int(p.stem) for p in folder.glob("*.png")) == list(range(1507))
    stats[view] = {}
    grid = Image.new("RGB", (1600, 747), "#111827")
    for j, i in enumerate(samples):
        im = Image.open(folder / f"{i:04d}.png")
        assert im.size == (1280, 720)
        x = j % 4 * 400
        y = j // 4 * 249
        grid.paste(im.resize((400, 225)), (x, y + 24))
        ImageDraw.Draw(grid).text(
            (x + 8, y + 5), f"{view} | frame {i} | {i / 15:.2f}s", fill="white"
        )
    grid.save(out / f"{view}-complete-contact-sheet.jpg", quality=92)
    for seam in [500, 1000]:
        ims = [
            np.asarray(Image.open(folder / f"{i:04d}.png"), dtype=float)
            for i in range(seam - 2, seam + 2)
        ]
        mad = [float(np.abs(b - a).mean()) for a, b in zip(ims[:-1], ims[1:])]
        stats[view][str(seam)] = {
            "neighbor_and_seam_mean_pixel_changes": mad,
            "ratio_to_neighbors": mad[1] / max(0.1, (mad[0] + mad[2]) / 2),
        }
        # Investigate any gross flash; detailed review also uses the contact sheet.
        assert mad[1] < max(12.0, 5 * (mad[0] + mad[2]) / 2)
        strip = Image.new("RGB", (1600, 249), "#111827")
        for j, i in enumerate(range(seam - 2, seam + 2)):
            strip.paste(Image.open(folder / f"{i:04d}.png").resize((400, 225)), (j * 400, 24))
            ImageDraw.Draw(strip).text((j * 400 + 8, 5), f"{view} frame {i}", fill="white")
        strip.save(out / f"{view}-seam-{seam}.jpg", quality=92)
(out / "encoded-frame-verification.json").write_text(json.dumps(stats, indent=2))
print("FRAME_QA_DONE", stats)
