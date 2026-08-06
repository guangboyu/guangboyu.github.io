#!/usr/bin/env python3
"""
Regenerate the photo gallery from your Lightroom export.

Point it at a folder of folders, one per place:

    assets/Export/Alaska/Bear 1.jpg
    assets/Export/Utah/Delicate_Arch_2024.jpg
    ...

then run

    python3 scripts/build-photos.py

Each folder becomes a section in the gallery, and the folder name becomes the
default location shown under every photo in it. For each image this writes a
2000px display copy and a 900px thumbnail, both as WebP and JPEG, strips EXIF
including GPS, and rebuilds assets/js/photos.js.

Titles and other details are optional and live in assets/photos/captions.txt,
keyed by the path inside the export folder:

    Utah/Delicate_Arch_2024.jpg | Delicate Arch | Arches National Park, Utah | 2024 | feature

Fields after the filename are all optional. `feature` makes a photo span the
full width of its section. Filenames that are only a camera serial (DSC04249)
get no title, just the place, which reads better than "Dsc04249".

Re-running is cheap: renditions that are already current are skipped, and your
captions are never touched.

Requires ImageMagick. No Python packages.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "Export"
LARGE = ROOT / "assets" / "photos" / "large"
THUMB = ROOT / "assets" / "photos" / "thumb"
CAPTIONS = ROOT / "assets" / "photos" / "captions.txt"
OUT_JS = ROOT / "assets" / "js" / "photos.js"

LARGE_EDGE, LARGE_JPG_Q, LARGE_WEBP_Q = 2000, 80, 78
THUMB_EDGE, THUMB_JPG_Q, THUMB_WEBP_Q = 900, 78, 72

SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}



def need(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        sys.exit(f"error: `{binary}` not found. Install ImageMagick:\n"
                 f"  sudo apt install imagemagick")
    return path


def slugify(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return re.sub(r"-{2,}", "-", text) or "photo"


def render(src: Path, dst: Path, edge: int, quality: int) -> bool:
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    args = [
        need("convert"), str(src),
        "-auto-orient",
        "-strip",
        "-resize", f"{edge}x{edge}>",
        "-quality", str(quality),
        "-colorspace", "sRGB",
    ]
    args += ["-define", "webp:method=6"] if dst.suffix == ".webp" else ["-interlace", "Plane"]
    subprocess.run(args + [str(dst)], check=True)
    return True


def dimensions(path: Path) -> tuple[int, int]:
    out = subprocess.run([need("identify"), "-format", "%w %h", str(path)],
                         check=True, capture_output=True, text=True).stdout.split()
    return int(out[0]), int(out[1])


def load_captions() -> dict[str, dict]:
    meta: dict[str, dict] = {}
    if not CAPTIONS.exists():
        return meta
    for raw in CAPTIONS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        meta[parts[0].replace("\\", "/").lower()] = {
            "title": parts[1] if len(parts) > 1 else None,
            "place": parts[2] if len(parts) > 2 else None,
            "year": parts[3] if len(parts) > 3 else "",
            "feature": len(parts) > 4 and parts[4].lower() == "feature",
        }
    return meta


def main() -> None:
    if not SOURCE.exists():
        sys.exit(f"error: {SOURCE.relative_to(ROOT)} does not exist. Put one folder "
                 f"per place inside it.")

    captions = load_captions()
    sections: dict[str, list[dict]] = {}
    keep: set[str] = set()
    built = 0

    for folder in sorted(p for p in SOURCE.iterdir() if p.is_dir()):
        place = folder.name
        images = sorted(p for p in folder.iterdir()
                        if p.is_file() and p.suffix.lower() in SUFFIXES)
        if not images:
            continue
        print(f"{place} ({len(images)})")

        for src in images:
            stem = f"{slugify(place)}-{slugify(src.stem)}"
            thumb = THUMB / f"{stem}.jpg"
            for dst, edge, q in (
                (LARGE / f"{stem}.jpg",  LARGE_EDGE, LARGE_JPG_Q),
                (LARGE / f"{stem}.webp", LARGE_EDGE, LARGE_WEBP_Q),
                (thumb,                  THUMB_EDGE, THUMB_JPG_Q),
                (THUMB / f"{stem}.webp", THUMB_EDGE, THUMB_WEBP_Q),
            ):
                built += render(src, dst, edge, q)
                keep.add(str(dst.relative_to(ROOT)))

            w, h = dimensions(thumb)
            key = f"{place}/{src.name}".lower()
            meta = captions.get(key, {})

            sections.setdefault(place, []).append({
                "src": f"assets/photos/large/{stem}.jpg",
                "srcWebp": f"assets/photos/large/{stem}.webp",
                "thumb": f"assets/photos/thumb/{stem}.jpg",
                "thumbWebp": f"assets/photos/thumb/{stem}.webp",
                "w": w,
                "h": h,
                "group": place,
                "title": meta.get("title") or "",
                "place": meta.get("place") or "",
                "year": meta.get("year", ""),
                "feature": bool(meta.get("feature")),
            })

    if not sections:
        sys.exit("error: no images found.")

    # Drop renditions whose source is gone, so removing a photo from Export/ is
    # enough to remove it from the site.
    pruned = 0
    for folder in (LARGE, THUMB):
        for f in sorted(folder.iterdir()):
            if f.is_file() and str(f.relative_to(ROOT)) not in keep:
                f.unlink()
                pruned += 1
                print(f"  pruned {f.relative_to(ROOT)}")

    # Biggest bodies of work first; a section of one photo reads as an afterthought.
    photos = [p for place in sorted(sections, key=lambda k: (-len(sections[k]), k))
              for p in sections[place]]

    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text(
        "/* Generated by scripts/build-photos.py — edit captions.txt, not this file. */\n"
        f"const PHOTOS = {json.dumps(photos, indent=2, ensure_ascii=False)};\n",
        encoding="utf-8",
    )

    shipped = sum(f.stat().st_size for d in (LARGE, THUMB) for f in d.iterdir())
    print(f"\n{len(photos)} photos in {len(sections)} sections, "
          f"{built} renditions built, {pruned} pruned.")
    print(f"Shipped weight: {shipped / 1048576:.0f} MB")
    print(f"Wrote {OUT_JS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
