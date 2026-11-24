#!/usr/bin/env python3
"""
Render the blog from Markdown.

    python3 scripts/build-blog.py

Re-running is safe: unchanged sources produce identical pages.

Posts
-----
Write a post as blog/<slug>.md. For every post the script writes
blog/<slug>.html, rewrites the list between the POSTS:START and POSTS:END
markers in blog.html, and adds the post to sitemap.xml if it is missing.

A post starts with a small front-matter block:

    ---
    title: What are you rewarding? A practical guide to ...
    summary: One sentence, shown under the title and in the post list.
    date: 2026-11-02
    topic: Reward design in medical imaging      (optional)
    ---

The body is ordinary Markdown: $...$ and $$...$$ for math (rendered as MathML,
no JavaScript), pipe tables, fenced code, and images written as

    ![Alt text](img/<slug>-figure.webp)
    *Figure 1. Caption.*

which become a figure with a caption. Put images in blog/img/.

LeetCode patterns
-----------------
Tutorials are written for GitHub and arrive through inbox/ (see
scripts/import-leetcode.py, which also runs this script). They live as

    blog/leetcode/<Pattern>.md      one per pattern, e.g. SlidingWindow.md
    blog/leetcode/assets/           the GIFs and figures they reference
    blog/leetcode/route.md          the study route, a Pattern | Status | Tutorial table
    blog/leetcode/index.md          intro and colour key for the index page

Each tutorial becomes blog/leetcode/<pattern>.html (sliding-window.html), next
to its source, so image paths work unchanged. No front matter is needed: the
"# Title" line is the title, the paragraph under it is the summary, a
"## Contents" list becomes the contents box, and the date is the last commit
that touched the file. blog/leetcode/index.html is built from route.md and
index.md, and the section between LEETCODE:START and LEETCODE:END in blog.html
is rewritten too.

```mermaid blocks are drawn with mermaid-cli (through npx, so Node is needed)
and saved as SVG in blog/leetcode/img/, named by a hash of their source. Later
builds reuse the SVG, so Node only matters when a diagram changes.

Requires pandoc. The generated pages are plain HTML and need nothing at runtime.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "blog"
INDEX = ROOT / "blog.html"
SITEMAP = ROOT / "sitemap.xml"
SITE = "https://guangboyu.github.io/"
AUTHOR = "Guangbo Yu"

START, END = "<!-- POSTS:START -->", "<!-- POSTS:END -->"
WORDS_PER_MINUTE = 230

LEETCODE = BLOG / "leetcode"
LC_ROUTE = LEETCODE / "route.md"
LC_SITE_FILES = {"index.md", "route.md", "readme.md"}     # in blog/leetcode, not tutorials
LC_INTRO = LEETCODE / "index.md"
LC_IMG = LEETCODE / "img"
LC_START, LC_END = "<!-- LEETCODE:START -->", "<!-- LEETCODE:END -->"
LC_NAME = "LeetCode patterns"

e = lambda s: html.escape(s, quote=True)


# ---------- Reading a post ----------

def read_post(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, flags=re.S)
    if not m:
        sys.exit(f"error: {path.name} has no front-matter block.")
    meta = parse_front_matter(m.group(1))
    for key in ("title", "summary", "date"):
        if not meta.get(key):
            sys.exit(f"error: {path.name} is missing '{key}' in its front matter.")
    meta["slug"] = path.stem
    meta["date_obj"] = dt.date.fromisoformat(meta["date"])
    meta["body_md"] = text[m.end():]
    return meta


def parse_front_matter(block: str) -> dict:
    meta = {}
    for line in block.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip().lower()] = value.strip()
    return meta


def reading_minutes(md: str) -> int:
    prose = re.sub(r"```.*?```", " ", md, flags=re.S)       # code blocks
    prose = re.sub(r"\$\$.*?\$\$", " ", prose, flags=re.S)  # display math
    prose = re.sub(r"^\|.*\|$", " ", prose, flags=re.M)     # table rows
    prose = re.sub(r"\]\([^)]*\)", "]", prose)              # link targets
    return max(1, round(len(prose.split()) / WORDS_PER_MINUTE))


def long_date(d: dt.date) -> str:
    return f"{d.day} {d.strftime('%B')} {d.year}"


# ---------- Markdown to HTML ----------

def pandoc(md: str) -> str:
    return subprocess.run(
        ["pandoc", "-f", "markdown+tex_math_dollars", "-t", "html5",
         "--mathml", "--no-highlight", "--wrap=none", "--columns=10000"],
        input=md, capture_output=True, text=True, check=True,
    ).stdout


def image_size(src: str) -> tuple[int, int] | None:
    path = BLOG / src
    if not path.exists():
        sys.exit(f"error: image {src} not found in blog/.")
    if not shutil.which("identify"):
        return None
    out = subprocess.run(["identify", "-format", "%w %h", str(path)],
                         capture_output=True, text=True).stdout.split()
    return (int(out[0]), int(out[1])) if len(out) == 2 else None


def figures(body: str) -> str:
    """<p><img><em>Figure ...</em></p>  ->  <figure> with a caption."""
    def repl(m: re.Match) -> str:
        src, alt, caption = m.group(1), m.group(2), m.group(3)
        size = image_size(src)
        dims = f' width="{size[0]}" height="{size[1]}"' if size else ""
        return (f'<figure class="post-fig">\n'
                f'  <a href="{src}"><img src="{src}" alt="{alt}"{dims} loading="lazy"></a>\n'
                f'  <figcaption>{caption}</figcaption>\n'
                f'</figure>')
    return re.sub(
        r'<p><img src="([^"]+)" alt="([^"]*)"\s*/?>\s*<em>(.*?)</em></p>',
        repl, body, flags=re.S)


def tables(body: str) -> str:
    body = body.replace("<table>", '<div class="table-scroll"><table class="post-table">')
    return body.replace("</table>", "</table></div>")


def polish(body: str) -> str:
    body = tables(figures(body))
    # "What to do:" paragraphs close each section; give them a callout.
    body = body.replace("<p><strong>What to do:</strong>",
                        '<p class="takeaway"><strong>What to do:</strong>')
    # Everything after the closing rule is a note, not body text.
    body = body.replace("<hr />", '<hr class="post-end" />')
    return body


def contents(body: str) -> str:
    items = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body)
    if len(items) < 3:
        return ""
    lis = "\n".join(f'      <li><a href="#{i}">{t}</a></li>' for i, t in items)
    return ('    <nav class="post-toc post-toc--inline" aria-label="Contents">\n'
            '      <p>Contents</p>\n'
            f'      <ol>\n{lis}\n      </ol>\n'
            '    </nav>\n')


def outline(body: str) -> str:
    """Every h2 with the h3s under it, as a nested list. Empty for short pages."""
    heads = re.findall(r'<h([23]) id="([^"]+)">(.*?)</h\1>', body)
    if sum(1 for level, _, _ in heads if level == "2") < 3:
        return ""
    out, in_h2, in_sub = ["<ul>"], False, False
    for level, ident, text in heads:
        text = re.sub(r"</?a\b[^>]*>", "", text)
        if level == "2":
            if in_h2:
                out.append("</ul></li>" if in_sub else "</li>")
            out.append(f'<li><a href="#{ident}">{text}</a>')
            in_h2, in_sub = True, False
        elif in_h2:
            if not in_sub:
                out.append("<ul>")
                in_sub = True
            out.append(f'<li><a href="#{ident}">{text}</a></li>')
    out += ["</ul></li>" if in_sub else "</li>", "</ul>"]
    return "\n".join(out)


def side_toc(items: str) -> str:
    """The contents again, as a sticky column on the right of wide screens."""
    if not items:
        return ""
    return ('  <aside class="post-side">\n'
            '    <nav class="side-toc" aria-label="On this page">\n'
            '      <p>On this page</p>\n'
            f'{items}\n'
            '    </nav>\n'
            '  </aside>')


def with_side(main: str, side: str) -> str:
    if not side:
        return main
    return f'<div class="post-layout has-side">\n{main}\n{side}\n</div>'


def math_font(body: str) -> str:
    # MathML needs a font with a MATH table and the math-italic letters; not every
    # device has one (Android, most Linux), so load Noto Sans Math on pages with math.
    if "<math" not in body:
        return ""
    return ('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+Math&display=swap">\n')


# ---------- Page template ----------

def nav(prefix: str, current: str) -> str:
    links = [("index.html", "About"), ("publications.html", "Publications"),
             ("projects.html", "Projects"), ("blog.html", "Blog"),
             ("photography.html", "Photography")]
    out = []
    for href, label in links:
        cur = ' aria-current="page"' if label == current else ""
        out.append(f'      <a href="{prefix}{href}"{cur}>{label}</a>')
    return "\n".join(out)


def page(*, prefix: str, title: str, meta: str, fonts: str, ld: dict | None,
         source: str, main: str) -> str:
    """The chrome every generated page shares: head, top bar, footer."""
    ld_block = ('<script type="application/ld+json">\n'
                f'{json.dumps(ld, indent=2, ensure_ascii=False)}\n'
                '</script>\n') if ld else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{meta}<meta name="theme-color" content="#fefffe" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0f172a" media="(prefers-color-scheme: dark)">
{fonts}<link rel="stylesheet" href="{prefix}assets/css/style.css">
{ld_block}<script>
  try {{ var t = localStorage.getItem('theme');
        if (t) document.documentElement.setAttribute('data-theme', t); }} catch (e) {{}}
</script>
</head>
<body>

<!-- Generated by scripts/build-blog.py from {source}. Edit the Markdown, not this file. -->

<a class="skip-link" href="#main">Skip to content</a>

<header class="topbar">
  <div class="shell topbar__in">
    <a class="wordmark" href="{prefix}index.html">{AUTHOR}</a>
    <nav class="nav" aria-label="Primary">
{nav(prefix, "Blog")}
    </nav>
    <button class="icon-btn" type="button" data-theme-toggle aria-label="Switch colour theme">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
           stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="4" width="20" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>
      </svg>
    </button>
  </div>
</header>

<div class="shell">
{main}
</div>

<div class="shell">
  <footer class="site-foot">
    <span>Irvine, California</span>
    <span>Built as static HTML. <a href="https://github.com/guangboyu">Source</a></span>
  </footer>
</div>

<script src="{prefix}assets/js/site.js"></script>
</body>
</html>
"""


def first_image(body: str, base: str) -> str | None:
    m = re.search(r'<img src="([^"]+)"', body)
    return f"{base}{m.group(1)}" if m else None


def social_meta(*, kind: str, title: str, summary: str, url: str,
                image: str | None, extra: str = "") -> str:
    og_image = f'<meta property="og:image" content="{e(image)}">\n' if image else ""
    return (f'<meta name="description" content="{e(summary)}">\n'
            f'<meta name="author" content="{AUTHOR}">\n'
            f'<link rel="canonical" href="{url}">\n'
            f'<meta property="og:type" content="{kind}">\n'
            f'<meta property="og:title" content="{e(title)}">\n'
            f'<meta property="og:description" content="{e(summary)}">\n'
            f'<meta property="og:url" content="{url}">\n'
            f'{og_image}{extra}'
            '<meta name="twitter:card" content="summary_large_image">\n')


def render_post(post: dict) -> tuple[str, int]:
    body = polish(pandoc(post["body_md"]))
    url = f"{SITE}blog/{post['slug']}.html"
    title, summary = post["title"], post["summary"]
    minutes = reading_minutes(post["body_md"])
    image = first_image(body, f"{SITE}blog/")

    ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": summary,
        "datePublished": post["date"],
        "author": {"@type": "Person", "name": AUTHOR, "url": SITE},
        "mainEntityOfPage": url,
    }
    if image:
        ld["image"] = image

    topic = (f'      <p class="post-kicker">{e(post["topic"])}</p>\n'
             if post.get("topic") else "")
    main = f"""  <main id="main" class="post">
    <header class="post-head">
      <p class="post-back"><a href="../blog.html">&larr; Blog</a></p>
{topic}      <h1 class="post-title">{e(title)}</h1>
      <p class="post-dek">{e(summary)}</p>
      <p class="post-meta">{AUTHOR} &middot; <time datetime="{post['date']}">{long_date(post['date_obj'])}</time> &middot; {minutes} min read</p>
    </header>

{contents(body)}
    <article class="post-body">
{body}
    </article>
  </main>"""

    meta = social_meta(
        kind="article", title=title, summary=summary, url=url, image=image,
        extra=f'<meta property="article:published_time" content="{post["date"]}">\n')
    return page(prefix="../", title=f"{e(title)} — {AUTHOR}", meta=meta,
                fonts=math_font(body), ld=ld, source=f"blog/{post['slug']}.md",
                main=with_side(main, side_toc(outline(body)))), minutes


# ---------- LeetCode patterns: reading the tutorials ----------

def lc_slug(stem: str) -> str:
    """SlidingWindow -> sliding-window, Two_Pointers -> two-pointers."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", stem)
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def git_dates(path: Path) -> tuple[dt.date, dt.date]:
    """(first published, last updated), from the commits that touched the file.
    A file with uncommitted changes counts as updated today."""
    today = dt.date.today()
    rel = str(path.relative_to(ROOT))
    try:
        log = subprocess.run(["git", "log", "--follow", "--format=%cs", "--", rel],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", rel],
                               cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return today, today
    if not log:
        return today, today
    first = dt.date.fromisoformat(log[-1])
    return first, today if dirty else dt.date.fromisoformat(log[0])


def plain(md: str) -> str:
    """Markdown inline text -> plain text, for descriptions and cards."""
    s = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", md)
    s = re.sub(r"[`*_]", "", s)
    return " ".join(s.split())


def read_route() -> list[dict]:
    """The study route: the Pattern | Status | Tutorial table in route.md, in order."""
    if not LC_ROUTE.exists():
        return []
    route = []
    for line in LC_ROUTE.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0].lower() == "pattern" or not cells[0].strip("-: "):
            continue
        link = re.search(r"\(([^)\s]+\.md)\)", cells[2])
        route.append({"name": cells[0],
                      "status": cells[1].lstrip("✓ ").strip(),
                      "file": link.group(1) if link else None})
    return route


TOC_MARK = "CONTENTSBOXGOESHERE"


def split_contents(md: str) -> tuple[str, str]:
    """Pull out a hand-written '## Contents' list, and the rules around it. It
    becomes the contents box, in the same place."""
    m = re.search(r"(?:^---[ \t]*\n\s*)?^## Contents[ \t]*\n(.*?)(?:^---[ \t]*\n|(?=^## ))",
                  md, flags=re.S | re.M)
    if not m:
        return "", md
    return m.group(1).strip(), f"{md[:m.start()]}{TOC_MARK}\n\n{md[m.end():]}"


def study_minutes(md: str) -> int:
    """Tutorials are read with the code and the tables, not around them."""
    code = re.findall(r"^```[^\n]*\n(.*?)^```", md, flags=re.S | re.M)
    prose = re.sub(r"^```.*?^```", " ", md, flags=re.S | re.M)
    prose = re.sub(r"\]\([^)]*\)", "]", prose.replace("|", " "))
    code_lines = sum(c.count("\n") for c in code)
    return max(1, round(len(prose.split()) / WORDS_PER_MINUTE + code_lines / 30))


def read_tutorial(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meta = {}
    m = re.match(r"---\n(.*?)\n---\n", text, flags=re.S)
    if m:                                   # optional, overrides what is inferred
        meta, text = parse_front_matter(m.group(1)), text[m.end():]

    h1 = re.search(r"^# (.+?)[ \t]*$", text, flags=re.M)
    if not h1 and not meta.get("title"):
        sys.exit(f"error: {path.name} has no '# Title' line.")
    title = meta.get("title") or h1.group(1)
    body = text[h1.end():] if h1 else text

    # The paragraph under the title is the summary, shown as the dek.
    body = body.lstrip("\n")
    first, _, rest = body.partition("\n\n")
    dek_md = meta.get("summary", "")
    if not dek_md and first and not re.match(r"\s*(```|\||#|!\[|>|[-*] |\d+\. |---)", first):
        dek_md, body = first, rest

    toc_md, body = split_contents(body)
    created, updated = git_dates(path)
    return {
        "file": path.name, "slug": lc_slug(path.stem), "title": title,
        "dek_md": dek_md, "summary": plain(dek_md) or title,
        "toc_md": toc_md, "body_md": body,
        "created": created, "updated": updated,
        "minutes": study_minutes(body),
    }


# ---------- LeetCode patterns: Markdown to HTML ----------

def pandoc_gfm(md: str) -> str:
    """The tutorials are written for GitHub, so read them the way GitHub does."""
    return subprocess.run(
        ["pandoc", "-f", "gfm", "-t", "html5", "--mathml",
         "--highlight-style=pygments", "--wrap=none", "--columns=10000"],
        input=md, capture_output=True, text=True, check=True,
    ).stdout


def raster_size(path: Path) -> tuple[int, int] | None:
    if not shutil.which("identify"):
        return None
    out = subprocess.run(["identify", "-format", "%w %h", f"{path}[0]"],
                         capture_output=True, text=True).stdout.split()
    return (int(out[0]), int(out[1])) if len(out) == 2 else None


def svg_size(path: Path) -> tuple[int, int] | None:
    m = re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"', path.read_text(encoding="utf-8"))
    return (round(float(m.group(1))), round(float(m.group(2)))) if m else None


MERMAID_CLI = "@mermaid-js/mermaid-cli@11.4.2"
MERMAID_FONT = "Arial, Helvetica, sans-serif"   # same metrics on every OS, so labels fit
MERMAID_CONFIG = {
    "theme": "base",
    "fontFamily": MERMAID_FONT,
    "flowchart": {"htmlLabels": False, "curve": "basis", "padding": 12},
    "themeVariables": {"fontFamily": MERMAID_FONT, "fontSize": "15px",
                       "lineColor": "#7C90AE", "primaryTextColor": "#263449",
                       "edgeLabelBackground": "#ffffff"},
}
MERMAID_CSS = ".edgeLabel rect { opacity: 1 !important; }\n"


def mermaid_cli() -> list[str] | None:
    if shutil.which("mmdc"):
        return ["mmdc"]
    if shutil.which("npx"):
        return ["npx", "-y", "-p", MERMAID_CLI, "mmdc"]
    return None


def mermaid_svg(source: str, name: str) -> Path:
    """Draw a mermaid block once; later builds reuse the SVG."""
    key = hashlib.sha1(json.dumps([MERMAID_CLI, MERMAID_CONFIG, MERMAID_CSS, source],
                                  sort_keys=True).encode()).hexdigest()[:10]
    out = LC_IMG / f"{name}-{key}.svg"
    if out.exists():
        return out
    cli = mermaid_cli()
    if not cli:
        sys.exit(f"error: drawing {name} needs Node (npx) for mermaid-cli, "
                 "or install it once: npm install -g @mermaid-js/mermaid-cli")
    LC_IMG.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "in.mmd").write_text(source, encoding="utf-8")
        (t / "config.json").write_text(json.dumps(MERMAID_CONFIG), encoding="utf-8")
        (t / "style.css").write_text(MERMAID_CSS, encoding="utf-8")
        run = subprocess.run(cli + ["-q", "-i", "in.mmd", "-o", "out.svg", "-c", "config.json",
                                    "-C", "style.css", "-b", "white", "-I", name],
                             cwd=t, capture_output=True, text=True)
        if run.returncode != 0 or not (t / "out.svg").exists():
            sys.exit(f"error: mermaid-cli failed on {name}:\n{run.stderr[-2000:]}")
        svg = (t / "out.svg").read_text(encoding="utf-8")
    # Give the file a real size, so it opens at 1:1 on its own.
    vb = re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"', svg)
    if vb:
        w, h = round(float(vb.group(1))), round(float(vb.group(2)))
        svg = re.sub(r'<svg([^>]*?) width="100%"', rf'<svg\1 width="{w}" height="{h}"', svg, count=1)
        svg = re.sub(r'style="max-width: [\d.]+px; ', 'style="', svg, count=1)
    for stale in LC_IMG.glob(f"{name}-*.svg"):
        stale.unlink()
    out.write_text(svg, encoding="utf-8")
    print(f"Drew blog/leetcode/img/{out.name}")
    return out


def mermaid_alt(source: str) -> str:
    labels = re.findall(r'[\[{(]+"(.*?)"[\]})]+', source)
    labels = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split()) for s in labels]
    return "Flowchart. " + "; ".join(labels) + "." if labels else "Flowchart."


def lift_mermaid(md: str) -> tuple[str, list[str]]:
    """Swap each mermaid block for a placeholder paragraph pandoc leaves alone."""
    blocks: list[str] = []

    def repl(m: re.Match) -> str:
        blocks.append(m.group(1))
        return f"MERMAIDBLOCK{len(blocks) - 1}"
    md = re.sub(r"^```mermaid[^\n]*\n(.*?)^```[ \t]*$", repl, md, flags=re.S | re.M)
    return md, blocks


def wide_figure(src: str, alt: str, size: tuple[int, int] | None, scale: float,
                caption: str = "", extra_class: str = "") -> str:
    """A figure allowed to run wider than the text, up to its natural width."""
    dims = f' width="{size[0]}" height="{size[1]}"' if size else ""
    style = f' style="--fig-w: {round(size[0] / scale)}px"' if size else ""
    cap = f'\n  <figcaption>{caption}</figcaption>' if caption else ""
    return (f'<figure class="post-fig post-fig--wide{extra_class}"{style}>\n'
            f'  <a href="{src}"><img src="{src}" alt="{alt}"{dims} loading="lazy" decoding="async"></a>'
            f'{cap}\n</figure>')


def link_target(href: str, by_file: dict[str, dict], here: str) -> str | None:
    """Point a link at another tutorial at its page; leave the rest alone."""
    if re.match(r"[a-z][a-z0-9+.-]*:|#|/", href):
        return href
    path, _, frag = href.partition("#")
    frag = f"#{frag}" if frag else ""
    if path.endswith(".md"):
        name = Path(path).name
        if name in by_file:
            return f"{by_file[name]['slug']}.html{frag}"
        if name.lower() in LC_SITE_FILES:
            return f"index.html{frag}"
        print(f"  warning: {here} links to {path}, which is not published yet; "
              "the link is left out.")
        return None
    return href


HEAT = {1: "Asked sometimes", 2: "Asked often", 3: "Asked very often"}
LEVEL = {"Easy": "easy", "Med": "med", "Medium": "med", "Hard": "hard"}


def tutorial_html(t: dict, by_file: dict[str, dict]) -> str:
    md, blocks = lift_mermaid(t["body_md"])
    body = pandoc_gfm(md)

    # Highlighted code: drop pandoc's per-line anchors.
    body = re.sub(r'<a href="#cb\d+-\d+" aria-hidden="true" tabindex="-1"></a>', "", body)
    body = re.sub(r'<span id="cb\d+-\d+">', "<span>", body)
    body = re.sub(r'<div class="sourceCode" id="cb\d+">', '<div class="sourceCode">', body)

    # Links to other tutorials point at their pages.
    def fix_link(m: re.Match) -> str:
        href, text = html.unescape(m.group(1)), m.group(2)
        target = link_target(href, by_file, t["file"])
        if target is None:
            return text
        if text == Path(href.partition("#")[0]).name and target.split("#")[0] != href:
            text = e(by_file.get(text, {}).get("title", LC_NAME))   # "SlidingWindow.md"
        return f'<a href="{e(target)}">{text}</a>'
    body = re.sub(r'<a href="([^"]+)">(.*?)</a>', fix_link, body, flags=re.S)

    # An image alone in its paragraph, with an italic paragraph under it as the caption.
    def fig(m: re.Match) -> str:
        src, alt, caption = html.unescape(m.group(1)), m.group(2), m.group(3) or ""
        local = LEETCODE / src
        if not local.exists():
            sys.exit(f"error: {t['file']} uses {src}, which is not in blog/leetcode/.")
        # The animations and figures are exported at 2x, so half their pixels is their
        # design width.
        return wide_figure(e(link_target(src, by_file, t["file"])), alt,
                           raster_size(local), 2, caption)
    body = re.sub(r'<p><img src="([^"]+)" alt="([^"]*)" ?/?></p>'
                  r'(?:\s*<p><em>((?:(?!</p>).)*?)</em></p>)?', fig, body, flags=re.S)

    for i, source in enumerate(blocks):
        svg = mermaid_svg(source, f"{t['slug']}-diagram-{i + 1}")
        figure = wide_figure(f"img/{svg.name}", e(mermaid_alt(source)), svg_size(svg), 1,
                             extra_class=" post-fig--diagram")
        body = body.replace(f"<p>MERMAIDBLOCK{i}</p>", figure)

    # Tables: scroll sideways on phones; difficulty and frequency get a visual form.
    body = tables(body)
    body = re.sub(r"<td>(Easy|Med|Medium|Hard)</td>",
                  lambda m: f'<td><span class="lvl lvl--{LEVEL[m.group(1)]}">{m.group(1)}</span></td>',
                  body)

    def heat(m: re.Match) -> str:
        n = min(len(m.group(1)), 3)
        dots = "".join('<i class="on"></i>' if k < n else "<i></i>" for k in range(3))
        return (f'<td><span class="heat" role="img" aria-label="{HEAT[n]}" '
                f'title="{HEAT[n]}">{dots}</span></td>')
    body = re.sub(r"<td>(🔥+)</td>", heat, body)

    # Sections get a rule of their own, so the --- lines before them go.
    body = re.sub(r"(?:<hr />\s*)+(?=<h2)", "", body)
    return body


def toc_items(t: dict, body: str) -> str:
    """The tutorial's own contents list if it has one, else its h2s and h3s."""
    return pandoc_gfm(t["toc_md"]).strip() if t["toc_md"] else outline(body)


def tutorial_toc(items: str) -> str:
    if not items:
        return ""
    return ('    <nav class="post-toc post-toc--nested post-toc--inline" aria-label="Contents">\n'
            '      <p>Contents</p>\n'
            f'{items}\n'
            '    </nav>\n')


def check_anchors(name: str, html_by_page: dict[str, str]) -> None:
    """Warn about #fragment links that do not land on an id."""
    ids = {p: set(re.findall(r' id="([^"]+)"', h)) for p, h in html_by_page.items()}
    for href in re.findall(r'href="([^"]*#[^"]+)"', html_by_page[name]):
        target, _, frag = href.partition("#")
        target = target or name
        if target in ids and html.unescape(frag) not in ids[target]:
            print(f"  warning: {name} links to {href}, which does not exist.")


# ---------- LeetCode patterns: pages ----------

def render_tutorial(t: dict, body: str, prev: dict | None, nxt: dict | None,
                    total: int) -> str:
    url = f"{SITE}blog/leetcode/{t['slug']}.html"
    image = first_image(body, f"{SITE}blog/leetcode/")
    # What the tutorial puts above its contents list stays above the contents box.
    intro, _, rest = body.rpartition(f"<p>{TOC_MARK}</p>")
    body = rest.strip("\n")
    intro = f'    <div class="post-body post-body--intro">\n{intro.strip()}\n    </div>\n\n' if intro.strip() else ""
    items = toc_items(t, body)
    dek = re.sub(r"^<p>|</p>\s*$", "", pandoc_gfm(t["dek_md"]).strip()) if t["dek_md"] else ""
    when = (long_date(t["updated"]) if t["updated"] == t["created"]
            else f"Updated {long_date(t['updated'])}")
    kicker = (f"{LC_NAME} &middot; {t['position']} of {total}" if t.get("position")
              else LC_NAME)

    ld = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": t["title"],
        "description": t["summary"],
        "datePublished": t["created"].isoformat(),
        "dateModified": t["updated"].isoformat(),
        "author": {"@type": "Person", "name": AUTHOR, "url": SITE},
        "isPartOf": {"@type": "CollectionPage", "name": LC_NAME,
                     "url": f"{SITE}blog/leetcode/"},
        "mainEntityOfPage": url,
    }
    if image:
        ld["image"] = image

    pager = ""
    if prev or nxt:
        left = (f'      <a class="prev" href="{prev["slug"]}.html"><span>Previous</span>'
                f'<strong>{e(prev["title"])}</strong></a>\n') if prev else ""
        right = (f'      <a class="next" href="{nxt["slug"]}.html"><span>Next</span>'
                 f'<strong>{e(nxt["title"])}</strong></a>\n') if nxt else ""
        pager = f'\n    <nav class="post-pager" aria-label="More patterns">\n{left}{right}    </nav>'

    main = f"""  <main id="main" class="post post--tutorial">
    <header class="post-head">
      <p class="post-back"><a href="../../blog.html">&larr; Blog</a> / <a href="index.html">{LC_NAME}</a></p>
      <p class="post-kicker">{kicker}</p>
      <h1 class="post-title">{e(t['title'])}</h1>
      <p class="post-dek">{dek}</p>
      <p class="post-meta">{AUTHOR} &middot; <time datetime="{t['updated'].isoformat()}">{when}</time> &middot; {t['minutes']} min read</p>
    </header>

{intro}{tutorial_toc(items)}
    <article class="post-body">
{body}
    </article>{pager}
  </main>"""

    meta = social_meta(
        kind="article", title=t["title"], summary=t["summary"], url=url, image=image,
        extra=(f'<meta property="article:published_time" content="{t["created"].isoformat()}">\n'
               f'<meta property="article:modified_time" content="{t["updated"].isoformat()}">\n'))
    return page(prefix="../../", title=f"{e(t['title'])} · {LC_NAME} — {AUTHOR}",
                meta=meta, fonts=math_font(body), ld=ld,
                source=f"blog/leetcode/{t['file']}", main=with_side(main, side_toc(items)))


def route_html(route: list[dict], by_file: dict[str, dict]) -> str:
    rows = []
    for n, step in enumerate(route, 1):
        t = by_file.get(step["file"] or "")
        num = f'<span class="route__num">{n:02d}</span>'
        if t:
            rows.append(
                f'<li class="is-written">{num}<div>'
                f'<a class="route__name" href="{t["slug"]}.html">{e(step["name"])}</a>'
                f'<p class="route__dek">{e(t["summary"])}</p>'
                f'<p class="route__meta">{t["minutes"]} min read</p></div></li>')
        else:
            rows.append(f'<li>{num}<div><span class="route__name">{e(step["name"])}</span>'
                        f' <span class="route__status">{e(step["status"])}</span></div></li>')
    return '<ol class="route">\n' + "\n".join(rows) + "\n</ol>"


def render_lc_index(tutorials: list[dict], route: list[dict],
                    by_file: dict[str, dict]) -> tuple[str, dict]:
    meta = {"title": LC_NAME, "summary": "Study notes on LeetCode patterns."}
    intro_md = "<!-- route -->\n"
    if LC_INTRO.exists():
        text = LC_INTRO.read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---\n", text, flags=re.S)
        if m:
            meta.update(parse_front_matter(m.group(1)))
            text = text[m.end():]
        intro_md = text

    written = len(tutorials)
    total = len(route) or written
    if not route:                       # no README table: list what exists
        route = [{"name": t["title"], "status": "", "file": t["file"]} for t in tutorials]
    progress = (f'<p class="route__progress">{written} of {total} patterns written. '
                'More to come.</p>\n')
    body = pandoc_gfm(intro_md)
    body = body.replace("<!-- route -->", progress + route_html(route, by_file))
    body = tables(body)
    updated = max((t["updated"] for t in tutorials), default=dt.date.today())

    url = f"{SITE}blog/leetcode/"
    main = f"""  <main id="main" class="post post--tutorial">
    <header class="post-head">
      <p class="post-back"><a href="../../blog.html">&larr; Blog</a></p>
      <h1 class="post-title">{e(meta['title'])}</h1>
      <p class="post-dek">{e(meta['summary'])}</p>
    </header>

    <article class="post-body">
{body}
    </article>
  </main>"""
    head = social_meta(kind="website", title=meta["title"], summary=meta["summary"],
                       url=url, image=None)
    out = page(prefix="../../", title=f"{e(meta['title'])} — {AUTHOR}", meta=head,
               fonts="", ld=None, source="blog/leetcode/index.md", main=main)
    return out, {"written": written, "total": total, "updated": updated,
                 "summary": meta["summary"]}


def render_lc_section(tutorials: list[dict], info: dict) -> str:
    ind = " " * 6
    cards = []
    for t in tutorials:
        where = f"Pattern {t['position']} of {info['total']} &middot; " if t.get("position") else ""
        cards.append(
            f'{ind}<article class="card">\n'
            f'{ind}  <h3 class="card__title"><a href="blog/leetcode/{t["slug"]}.html">{e(t["title"])}</a></h3>\n'
            f'{ind}  <p class="card__meta">{where}<time datetime="{t["updated"].isoformat()}">'
            f'{long_date(t["updated"])}</time> &middot; {t["minutes"]} min read</p>\n'
            f'{ind}  <p class="card__body">{e(t["summary"])}</p>\n'
            f'{ind}</article>')
    head = (f'{ind}<div class="section__head"><h2>{LC_NAME}</h2>'
            f'<a href="blog/leetcode/index.html">All {info["total"]} patterns &rarr;</a></div>\n'
            f'{ind}<p class="section__lede">{e(info["summary"])} '
            f'{info["written"]} of {info["total"]} written so far.</p>\n')
    return head + "\n\n".join(cards)


def build_leetcode() -> list[tuple[str, str, str]]:
    """Write the LeetCode pages. Returns sitemap entries (url, lastmod, priority)."""
    sources = sorted(p for p in LEETCODE.glob("*.md") if p.name.lower() not in LC_SITE_FILES)
    if not sources:
        return []
    route = read_route()
    tutorials = [read_tutorial(p) for p in sources]
    by_file = {t["file"]: t for t in tutorials}

    # Study-route order first, then anything the README does not list yet.
    order = {step["file"]: n for n, step in enumerate(route, 1) if step["file"]}
    for t in tutorials:
        t["position"] = order.get(t["file"])
    tutorials.sort(key=lambda t: (t["position"] or 10_000, t["title"]))

    bodies = {t["slug"]: tutorial_html(t, by_file) for t in tutorials}
    pages = {}
    for i, t in enumerate(tutorials):
        prev = tutorials[i - 1] if i > 0 else None
        nxt = tutorials[i + 1] if i + 1 < len(tutorials) else None
        pages[f"{t['slug']}.html"] = render_tutorial(t, bodies[t["slug"]], prev, nxt,
                                                     len(route) or len(tutorials))

    index, info = render_lc_index(tutorials, route, by_file)
    pages["index.html"] = index
    for name, text in pages.items():
        check_anchors(name, pages)
        (LEETCODE / name).write_text(text, encoding="utf-8")
    for t in tutorials:
        print(f"Wrote blog/leetcode/{t['slug']}.html ({t['minutes']} min read)")
    print(f"Wrote blog/leetcode/index.html: {info['written']} of {info['total']} patterns.")

    # The section on blog.html.
    blog = INDEX.read_text(encoding="utf-8")
    if LC_START in blog and LC_END in blog:
        before, rest = blog.split(LC_START, 1)
        _, after = rest.split(LC_END, 1)
        INDEX.write_text(f"{before}{LC_START}\n{render_lc_section(tutorials, info)}\n"
                         f"      {LC_END}{after}", encoding="utf-8")
    else:
        print(f"  warning: {INDEX.name} has no {LC_START} / {LC_END} markers; "
              "the LeetCode section there was not updated.")

    entries = [(f"{SITE}blog/leetcode/", info["updated"].isoformat(), "0.6")]
    entries += [(f"{SITE}blog/leetcode/{t['slug']}.html", t["updated"].isoformat(), "0.6")
                for t in tutorials]
    return entries


# ---------- The post list and the sitemap ----------

def render_list(posts: list[dict]) -> str:
    ind = " " * 6
    cards = []
    for p in posts:
        cards.append(
            f'{ind}<article class="card">\n'
            f'{ind}  <h3 class="card__title"><a href="blog/{p["slug"]}.html">{e(p["title"])}</a></h3>\n'
            f'{ind}  <p class="card__meta"><time datetime="{p["date"]}">{long_date(p["date_obj"])}</time>'
            f' &middot; {p["minutes"]} min read</p>\n'
            f'{ind}  <p class="card__body">{e(p["summary"])}</p>\n'
            f'{ind}</article>')
    return "\n\n".join(cards)


def update_sitemap(entries: list[tuple[str, str, str]]) -> None:
    """Add each page if it is missing; keep its lastmod current."""
    if not SITEMAP.exists():
        return
    text = SITEMAP.read_text(encoding="utf-8")
    for loc, lastmod, priority in entries:
        line = f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod><priority>{priority}</priority></url>"
        pattern = re.compile(rf"^  <url><loc>{re.escape(loc)}</loc>.*$", flags=re.M)
        if pattern.search(text):
            text = pattern.sub(line, text, count=1)
        else:
            text = text.replace("</urlset>", f"{line}\n</urlset>")
    SITEMAP.write_text(text, encoding="utf-8")


def main() -> None:
    if not shutil.which("pandoc"):
        sys.exit("error: pandoc is not installed (sudo apt install pandoc).")
    sources = sorted(BLOG.glob("*.md"))
    if not sources:
        sys.exit("error: no posts found in blog/.")

    posts = []
    for src in sources:
        post = read_post(src)
        page_html, post["minutes"] = render_post(post)
        (BLOG / f"{post['slug']}.html").write_text(page_html, encoding="utf-8")
        posts.append(post)
        print(f"Wrote blog/{post['slug']}.html ({post['minutes']} min read)")

    posts.sort(key=lambda p: p["date_obj"], reverse=True)
    index = INDEX.read_text(encoding="utf-8")
    if START not in index or END not in index:
        sys.exit(f"error: {INDEX.name} is missing the {START} / {END} markers.")
    before, rest = index.split(START, 1)
    _, after = rest.split(END, 1)
    INDEX.write_text(f"{before}{START}\n{render_list(posts)}\n      {END}{after}",
                     encoding="utf-8")
    print(f"Wrote {INDEX.name}: {len(posts)} post(s).")

    entries = [(f"{SITE}blog/{p['slug']}.html", p["date"], "0.7") for p in posts]
    if LEETCODE.is_dir():
        entries += build_leetcode()
    update_sitemap(entries)


if __name__ == "__main__":
    main()
