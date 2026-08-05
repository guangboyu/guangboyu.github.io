#!/usr/bin/env python3
"""
Regenerate the publications list from BibTeX.

Edit publications.bib, then run:

    python3 scripts/build-pubs.py

It rewrites only the block between the PUBS:START and PUBS:END markers in
publications.html. Everything else on that page — the sidebar, the intro, the
"Also" section — stays hand-edited and is never touched.

Entries are grouped by year, newest first, with anything carrying a `status`
field (e.g. "Under review") placed above the dated ones. Your position in the
author list is detected automatically, so a first-author paper gets its badge
without you flagging it.

No third-party packages. Standard library only.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIB = ROOT / "publications.bib"
PAGE = ROOT / "publications.html"

START = "<!-- PUBS:START -->"
END = "<!-- PUBS:END -->"

# Who to highlight, and whose author position decides the "First author" badge.
ME_LAST = "Yu"
ME_INITIALS = ("G",)

INDENT = " " * 6


# ---------- BibTeX parsing ----------

def read_value(text: str, pos: int) -> tuple[str, int]:
    """Read one field value starting at pos. Handles {braced}, "quoted" and bare."""
    if pos >= len(text):
        return "", pos
    if text[pos] == "{":
        depth, start = 0, pos
        while pos < len(text):
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                depth -= 1
                if depth == 0:
                    return text[start + 1:pos], pos + 1
            pos += 1
        return text[start + 1:], pos
    if text[pos] == '"':
        start = pos + 1
        pos += 1
        while pos < len(text) and text[pos] != '"':
            pos += 1
        return text[start:pos], pos + 1
    start = pos
    while pos < len(text) and text[pos] not in ",}\n":
        pos += 1
    return text[start:pos].strip(), pos


def parse_bib(text: str) -> list[dict]:
    # Drop whole-line comments; % inside a value is left alone.
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("%"))

    entries: list[dict] = []
    i = 0
    while True:
        at = text.find("@", i)
        if at == -1:
            break
        head = re.match(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text[at:])
        if not head:
            i = at + 1
            continue

        entry = {"_type": head.group(1).lower(), "_key": head.group(2)}
        pos = at + head.end()

        while pos < len(text):
            while pos < len(text) and text[pos] in " \t\r\n,":
                pos += 1
            if pos < len(text) and text[pos] == "}":
                pos += 1
                break
            field = re.match(r"(\w+)\s*=\s*", text[pos:])
            if not field:
                pos += 1
                continue
            pos += field.end()
            value, pos = read_value(text, pos)
            entry[field.group(1).lower()] = " ".join(value.split())

        entries.append(entry)
        i = pos

    return entries


# ---------- Formatting ----------

def esc(text: str) -> str:
    """Escape for HTML, convert BibTeX -- ranges, turn *italics* into <i> tags."""
    out = html.escape(text, quote=False)
    out = out.replace("--", "–")          # 12--18 becomes 12–18
    return re.sub(r"\*([^*]+)\*", r"<i>\1</i>", out)


def split_authors(raw: str) -> list[str]:
    return [a.strip() for a in re.split(r"\s+and\s+", raw) if a.strip()]


def short_name(author: str) -> tuple[str, str]:
    """Return (surname, initials) for 'Yu, Guangbo' or 'Guangbo Yu'."""
    if "," in author:
        last, first = author.split(",", 1)
    else:
        parts = author.split()
        last, first = (parts[-1], " ".join(parts[:-1])) if len(parts) > 1 else (author, "")
    initials = "".join(p[0].upper() for p in first.replace(".", " ").split() if p)
    return last.strip(), initials


def is_me(author: str) -> bool:
    last, initials = short_name(author)
    return last == ME_LAST and (not initials or initials[0] in ME_INITIALS)


def render_authors(raw: str) -> tuple[str, int]:
    """Render the author line, highlighting me. Returns (html, my index or -1)."""
    pieces, my_index = [], -1
    for i, author in enumerate(split_authors(raw)):
        if author.lower() in ("others", "et al", "et al."):
            pieces.append("et al.")
            continue
        last, initials = short_name(author)
        name = esc(f"{last} {initials}".strip())
        if is_me(author):
            my_index = i
            pieces.append(f'<span class="me">{name}</span>')
        else:
            pieces.append(name)
    return ", ".join(pieces), my_index


def render_venue(entry: dict) -> str:
    if entry.get("venue"):
        return esc(entry["venue"])

    name = entry.get("journal") or entry.get("booktitle")
    if not name:
        return ""

    out = f"<i>{esc(name)}</i>"
    volume, number, pages = entry.get("volume"), entry.get("number"), entry.get("pages")
    if volume:
        out += f" {esc(volume)}"
        if number:
            out += f"({esc(number)})"
        if pages:
            out += f":{esc(pages)}"
    elif pages:
        out += f" {esc(pages)}"
    return out


def badge(entry: dict, my_index: int) -> str:
    role = (entry.get("role") or "").lower()
    if role in ("co-first", "cofirst", "equal"):
        return "Co-first author"
    if role == "first" or my_index == 0:
        return "First author"
    if role:
        return entry["role"]
    return ""


def link_for(entry: dict) -> str:
    if entry.get("doi"):
        doi = entry["doi"].replace("https://doi.org/", "")
        return f"https://doi.org/{doi}"
    return entry.get("url", "")


def render_entry(entry: dict) -> str:
    title = esc(entry.get("title", "Untitled"))
    href = link_for(entry)
    title_html = f'<a href="{html.escape(href, quote=True)}">{title}</a>' if href else title

    lines = [f'{INDENT}<article class="card">',
             f'{INDENT}  <h3 class="card__title">{title_html}</h3>']

    authors, my_index = render_authors(entry.get("author", ""))
    stamp = badge(entry, my_index)
    if authors or stamp:
        meta = authors if authors.endswith(".") else f"{authors}."
        if stamp:
            meta += f'{" &nbsp;" if authors else ""}<span class="stamp">{esc(stamp)}</span>'
        lines.append(f'{INDENT}  <p class="card__meta">{meta}</p>')

    venue = render_venue(entry)
    if venue:
        lines.append(f'{INDENT}  <p class="card__venue">{venue}</p>')

    if entry.get("summary"):
        lines.append(f'{INDENT}  <p class="card__body">{esc(entry["summary"])}</p>')

    if entry.get("code"):
        url = html.escape(entry["code"], quote=True)
        lines.append(f'{INDENT}  <p class="links"><a href="{url}">Code</a></p>')

    lines.append(f"{INDENT}</article>")
    return "\n".join(lines)


def group_key(entry: dict) -> tuple[int, str]:
    """Undated entries (status set) sort above everything, then year descending."""
    if entry.get("status"):
        return (0, entry["status"])
    return (1, entry.get("year", "0000"))


def render_all(entries: list[dict]) -> str:
    ordered = sorted(
        entries,
        key=lambda e: (0, 0) if e.get("status") else (1, -int(e.get("year") or 0)),
    )

    out, current = [], None
    for entry in ordered:
        heading = entry.get("status") or entry.get("year", "Undated")
        if heading != current:
            out.append(f'{INDENT}<p class="year-head">{esc(heading)}</p>')
            current = heading
        out.append(render_entry(entry))
    return "\n\n".join(out)


# ---------- Page rewrite ----------

def main() -> None:
    if not BIB.exists():
        sys.exit(f"error: {BIB.name} not found.")
    if not PAGE.exists():
        sys.exit(f"error: {PAGE.name} not found.")

    entries = parse_bib(BIB.read_text(encoding="utf-8"))
    if not entries:
        sys.exit(f"error: no entries parsed from {BIB.name}.")

    page = PAGE.read_text(encoding="utf-8")
    if START not in page or END not in page:
        sys.exit(
            f"error: {PAGE.name} is missing the {START} / {END} markers.\n"
            "Put them around the block this script should own."
        )

    before, rest = page.split(START, 1)
    _, after = rest.split(END, 1)
    page = f"{before}{START}\n{render_all(entries)}\n{INDENT}{END}{after}"
    PAGE.write_text(page, encoding="utf-8")

    first = sum(1 for e in entries if badge(e, render_authors(e.get("author", ""))[1]))
    years = sorted({e.get("year") for e in entries if e.get("year")}, reverse=True)
    print(f"Wrote {PAGE.name}: {len(entries)} entries, {first} first or co-first author.")
    print(f"Years: {', '.join(years)}")


if __name__ == "__main__":
    main()
