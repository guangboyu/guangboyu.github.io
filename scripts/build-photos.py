#!/usr/bin/env python3
"""
Regenerate the photo gallery.

Drop full-resolution files into  assets/photos/originals/
then run                        python3 scripts/build-photos.py

For each original this writes a display-size copy to assets/photos/large/,
a smaller one to assets/photos/thumb/, and rebuilds assets/js/photos.js,
which is what photography.html reads.

Captions live in assets/photos/captions.txt, one pipe-separated line per file:

    delicate-arch.jpg | Delicate Arch | Arches National Park, Utah | 2024 | feature

Fields after the filename are optional. The trailing `feature` flag makes a
photo span the full width of the gallery instead of sitting in a column.
Editing captions.txt and re-running is safe — nothing here is clobbered.

Requires ImageMagick (`convert` and `identify`). No Python packages needed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORIGINALS = ROOT / "assets" / "photos" / "originals"
LARGE = ROOT / "assets" / "photos" / "large"
THUMB = ROOT / "assets" / "photos" / "thumb"
CAPTIONS = ROOT / "assets" / "photos" / "captions.txt"
OUT_JS = ROOT / "assets" / "js" / "photos.js"

# Long-edge pixels and quality for each rendition. WebP is what browsers actually
# load; the JPEG is a fallback for anything that cannot read it.
LARGE_EDGE, LARGE_JPG_Q, LARGE_WEBP_Q = 2000, 80, 78
THUMB_EDGE, THUMB_JPG_Q, THUMB_WEBP_Q = 900, 78, 72

SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}


def need(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        sys.exit(
            f"error: `{binary}` not found. Install ImageMagick first:\n"
            f"  sudo apt install imagemagick"
        )
    return path


def render(src: Path, dst: Path, edge: int, quality: int) -> None:
    """Resize src into dst, but only when dst is missing or stale."""
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    args = [
        need("convert"), str(src),
        "-auto-orient",          # respect the EXIF rotation flag
        "-strip",                # drop EXIF, including GPS coordinates
        "-resize", f"{edge}x{edge}>",   # never upscale
        "-quality", str(quality),
        "-colorspace", "sRGB",
    ]
    if dst.suffix == ".webp":
        args += ["-define", "webp:method=6"]
    else:
        args += ["-interlace", "Plane"]   # progressive JPEG
    subprocess.run(args + [str(dst)], check=True)
    print(f"  rendered {dst.relative_to(ROOT)}")


def dimensions(path: Path) -> tuple[int, int]:
    out = subprocess.run(
        [need("identify"), "-format", "%w %h", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout.split()
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
        key = parts[0]
        meta[key] = {
            "title": parts[1] if len(parts) > 1 else "",
            "place": parts[2] if len(parts) > 2 else "",
            "year": parts[3] if len(parts) > 3 else "",
            "feature": len(parts) > 4 and parts[4].lower() == "feature",
        }
    return meta


def titleize(stem: str) -> str:
    return stem.replace("-", " ").replace("_", " ").strip().title()


def main() -> None:
    if not ORIGINALS.exists():
        sys.exit(f"error: {ORIGINALS.relative_to(ROOT)} does not exist.")

    originals = sorted(
        p for p in ORIGINALS.iterdir()
        if p.is_file() and p.suffix.lower() in SUFFIXES
    )
    if not originals:
        print(f"No photos in {ORIGINALS.relative_to(ROOT)} — writing an empty gallery.")

    captions = load_captions()
    photos = []

    for src in originals:
        print(f"{src.name}")
        stem = src.stem
        thumb = THUMB / f"{stem}.jpg"
        render(src, LARGE / f"{stem}.jpg",  LARGE_EDGE, LARGE_JPG_Q)
        render(src, LARGE / f"{stem}.webp", LARGE_EDGE, LARGE_WEBP_Q)
        render(src, thumb,                  THUMB_EDGE, THUMB_JPG_Q)
        render(src, THUMB / f"{stem}.webp", THUMB_EDGE, THUMB_WEBP_Q)

        w, h = dimensions(thumb)
        meta = captions.get(src.name) or captions.get(f"{stem}.jpg") or {}
        photos.append({
            "src": f"assets/photos/large/{stem}.jpg",
            "srcWebp": f"assets/photos/large/{stem}.webp",
            "thumb": f"assets/photos/thumb/{stem}.jpg",
            "thumbWebp": f"assets/photos/thumb/{stem}.webp",
            "w": w,
            "h": h,
            "title": meta.get("title") or titleize(stem),
            "place": meta.get("place", ""),
            "year": meta.get("year", ""),
            "feature": bool(meta.get("feature")),
        })

    body = json.dumps(photos, indent=2, ensure_ascii=False)
    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text(
        "/* Generated by scripts/build-photos.py — edit captions.txt, not this file. */\n"
        f"const PHOTOS = {body};\n",
        encoding="utf-8",
    )
    print(f"\nWrote {OUT_JS.relative_to(ROOT)} — {len(photos)} photo(s).")


if __name__ == "__main__":
    main()
