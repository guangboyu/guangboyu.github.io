#!/usr/bin/env python3
"""
Bring new or updated LeetCode tutorials from inbox/ into the site.

Dump files into inbox/: the whole tutorials folder as it is, or just the .md
files and the assets they use. Then run

    python3 scripts/import-leetcode.py

For every tutorial in the dump (any .md with a "# Title" line, other than a
README) it

  - copies the Markdown to blog/leetcode/<Name>.md, replacing an older copy,
  - copies the images it references into blog/leetcode/, keeping their
    relative paths (assets/<pattern>/...),

then refreshes the study route (blog/leetcode/route.md) from a README status
table if the dump has one, deletes assets that no tutorial references any more,
rebuilds the blog, and empties inbox/. Everything else in the dump (the
animation generator, fonts, notes) is deleted with it.

    --dry-run   say what would happen and change nothing
    --keep      leave inbox/ as it is afterwards
"""

from __future__ import annotations

import argparse
import posixpath
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"
LEETCODE = ROOT / "blog" / "leetcode"
SITE_FILES = {"index.md", "route.md", "readme.md"}   # in blog/leetcode, never tutorials

IMAGE_REFS = re.compile(r'!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)|<img[^>]+src="([^"]+)"')
STATUS = re.compile(r"<!-- tutorials:status -->(.*?)<!-- /tutorials:status -->", re.S)

ROUTE_HEADER = """<!-- The study route, in order, as the LeetCode index shows it. Refreshed from
     the tutorials README by scripts/import-leetcode.py; editing it by hand is fine.
     A row whose last cell links a .md file is a written tutorial. -->

"""


def is_local(ref: str) -> bool:
    return not re.match(r"[a-z][a-z0-9+.-]*:|/|#", ref)


def image_refs(md: str) -> list[str]:
    return [a or b for a, b in IMAGE_REFS.findall(md) if is_local(a or b)]


def tutorials_in(folder: Path) -> list[Path]:
    found = []
    for p in sorted(folder.rglob("*.md")):
        rel = p.relative_to(folder).parts
        if p.name.lower() in SITE_FILES or any(part.startswith(".") for part in rel):
            continue
        if re.search(r"^# \S", p.read_text(encoding="utf-8"), flags=re.M):
            found.append(p)
    return found


def published() -> list[Path]:
    return sorted(p for p in LEETCODE.glob("*.md") if p.name.lower() not in SITE_FILES)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)
    dry = args.dry_run

    def do(msg: str, action=None) -> None:
        print(("would " if dry else "") + msg)
        if not dry and action:
            action()

    sources = tutorials_in(INBOX) if INBOX.is_dir() else []
    if not sources:
        sys.exit("Nothing to import: no tutorial .md files in inbox/.")
    LEETCODE.mkdir(parents=True, exist_ok=True)

    # Tutorials and the images they use.
    missing = []
    for src in sources:
        text = src.read_text(encoding="utf-8")
        for ref in dict.fromkeys(image_refs(text)):
            rel = posixpath.normpath(ref)
            if rel.startswith(".."):                # outside the dump's folder: re-home it
                parts = Path(rel).parts
                rel = posixpath.join("assets", *parts[-2:])
                text = text.replace(f"]({ref}", f"]({rel}").replace(f'src="{ref}"', f'src="{rel}"')
            found = (src.parent / ref).resolve()
            dest = LEETCODE / rel
            if found.is_file():
                if not dest.exists() or dest.read_bytes() != found.read_bytes():
                    do(f"copy {rel}", lambda f=found, d=dest: (d.parent.mkdir(parents=True, exist_ok=True),
                                                              shutil.copy2(f, d)))
            elif not dest.exists():
                missing.append(f"{src.name}: {ref}")
        dest = LEETCODE / src.name
        verb = "update" if dest.exists() else "add"
        if not dest.exists() or dest.read_text(encoding="utf-8") != text:
            do(f"{verb} blog/leetcode/{src.name}", lambda d=dest, t=text: d.write_text(t, encoding="utf-8"))
        else:
            print(f"unchanged blog/leetcode/{src.name}")

    if missing:
        sys.exit("error: these images are referenced but are neither in the dump nor on the site:\n  "
                 + "\n  ".join(missing))

    # The study route.
    for readme in sorted(INBOX.rglob("README.md")):
        m = STATUS.search(readme.read_text(encoding="utf-8"))
        if m:
            table = "\n".join(l for l in m.group(1).strip().splitlines() if l.lstrip().startswith("|"))
            route = ROUTE_HEADER + table + "\n"
            target = LEETCODE / "route.md"
            if not target.exists() or target.read_text(encoding="utf-8") != route:
                do("refresh blog/leetcode/route.md from the README status table",
                   lambda: target.write_text(route, encoding="utf-8"))
            break

    # Assets nothing points at any more.
    if not dry:
        used = {posixpath.normpath(r) for p in published()
                for r in image_refs(p.read_text(encoding="utf-8"))}
        assets = LEETCODE / "assets"
        for f in sorted(assets.rglob("*")) if assets.is_dir() else []:
            if f.is_file() and f.relative_to(LEETCODE).as_posix() not in used:
                print(f"delete unused {f.relative_to(LEETCODE).as_posix()}")
                f.unlink()
        for d in sorted(assets.rglob("*"), reverse=True) if assets.is_dir() else []:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()

    if dry:
        return
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build-blog.py")], check=True)

    if not args.keep:
        for item in INBOX.iterdir():
            if item.name == "README.md":
                continue
            shutil.rmtree(item) if item.is_dir() and not item.is_symlink() else item.unlink()
        print("Emptied inbox/.")


if __name__ == "__main__":
    main()
