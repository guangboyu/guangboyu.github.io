#!/usr/bin/env python3
"""
Render blog posts from Markdown.

Write a post as blog/<slug>.md, then run:

    python3 scripts/build-blog.py

For every post it writes blog/<slug>.html, rewrites the list between the
POSTS:START and POSTS:END markers in blog.html, and adds the post to
sitemap.xml if it is missing. Re-running is safe.

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

Requires pandoc. The generated pages are plain HTML and need nothing at runtime.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "blog"
INDEX = ROOT / "blog.html"
SITEMAP = ROOT / "sitemap.xml"
SITE = "https://guangboyu.github.io/"
AUTHOR = "Guangbo Yu"

START, END = "<!-- POSTS:START -->", "<!-- POSTS:END -->"
WORDS_PER_MINUTE = 230


# ---------- Reading a post ----------

def read_post(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, flags=re.S)
    if not m:
        sys.exit(f"error: {path.name} has no front-matter block.")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip().lower()] = value.strip()
    for key in ("title", "summary", "date"):
        if not meta.get(key):
            sys.exit(f"error: {path.name} is missing '{key}' in its front matter.")
    meta["slug"] = path.stem
    meta["date_obj"] = dt.date.fromisoformat(meta["date"])
    meta["body_md"] = text[m.end():]
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


def polish(body: str) -> str:
    body = figures(body)
    body = body.replace("<table>", '<div class="table-scroll"><table class="post-table">')
    body = body.replace("</table>", "</table></div>")
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
    return ('    <nav class="post-toc" aria-label="Contents">\n'
            '      <p>Contents</p>\n'
            f'      <ol>\n{lis}\n      </ol>\n'
            '    </nav>\n')


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


def first_image(body: str) -> str | None:
    m = re.search(r'<img src="([^"]+)"', body)
    return f"{SITE}blog/{m.group(1)}" if m else None


def render_post(post: dict) -> tuple[str, int]:
    body = polish(pandoc(post["body_md"]))
    url = f"{SITE}blog/{post['slug']}.html"
    title, summary = post["title"], post["summary"]
    minutes = reading_minutes(post["body_md"])
    image = first_image(body)

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

    e = lambda s: html.escape(s, quote=True)
    topic = (f'      <p class="post-kicker">{e(post["topic"])}</p>\n'
             if post.get("topic") else "")
    og_image = f'<meta property="og:image" content="{e(image)}">\n' if image else ""
    # MathML needs a font with a MATH table and the math-italic letters; not every
    # device has one (Android, most Linux), so load Noto Sans Math on pages with math.
    math_font = ('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
                 '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+Math&display=swap">\n'
                 ) if "<math" in body else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} — {AUTHOR}</title>
<meta name="description" content="{e(summary)}">
<meta name="author" content="{AUTHOR}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(summary)}">
<meta property="og:url" content="{url}">
{og_image}<meta property="article:published_time" content="{post['date']}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#fefffe" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0f172a" media="(prefers-color-scheme: dark)">
{math_font}<link rel="stylesheet" href="../assets/css/style.css">
<script type="application/ld+json">
{json.dumps(ld, indent=2, ensure_ascii=False)}
</script>
<script>
  try {{ var t = localStorage.getItem('theme');
        if (t) document.documentElement.setAttribute('data-theme', t); }} catch (e) {{}}
</script>
</head>
<body>

<!-- Generated by scripts/build-blog.py from blog/{post['slug']}.md. Edit the Markdown, not this file. -->

<a class="skip-link" href="#main">Skip to content</a>

<header class="topbar">
  <div class="shell topbar__in">
    <a class="wordmark" href="../index.html">{AUTHOR}</a>
    <nav class="nav" aria-label="Primary">
{nav("../", "Blog")}
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
  <main id="main" class="post">
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
  </main>
</div>

<div class="shell">
  <footer class="site-foot">
    <span>Irvine, California</span>
    <span>Built as static HTML. <a href="https://github.com/guangboyu">Source</a></span>
  </footer>
</div>

<script src="../assets/js/site.js"></script>
</body>
</html>
""", minutes


# ---------- The post list and the sitemap ----------

def render_list(posts: list[dict]) -> str:
    ind = " " * 6
    cards = []
    for p in posts:
        e = lambda s: html.escape(s, quote=True)
        cards.append(
            f'{ind}<article class="card">\n'
            f'{ind}  <h3 class="card__title"><a href="blog/{p["slug"]}.html">{e(p["title"])}</a></h3>\n'
            f'{ind}  <p class="card__meta"><time datetime="{p["date"]}">{long_date(p["date_obj"])}</time>'
            f' &middot; {p["minutes"]} min read</p>\n'
            f'{ind}  <p class="card__body">{e(p["summary"])}</p>\n'
            f'{ind}</article>')
    return "\n\n".join(cards)


def update_sitemap(posts: list[dict]) -> None:
    if not SITEMAP.exists():
        return
    text = SITEMAP.read_text(encoding="utf-8")
    for p in posts:
        loc = f"{SITE}blog/{p['slug']}.html"
        if loc not in text:
            text = text.replace(
                "</urlset>",
                f"  <url><loc>{loc}</loc><lastmod>{p['date']}</lastmod><priority>0.7</priority></url>\n</urlset>")
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
        page, post["minutes"] = render_post(post)
        (BLOG / f"{post['slug']}.html").write_text(page, encoding="utf-8")
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
    update_sitemap(posts)
    print(f"Wrote {INDEX.name}: {len(posts)} post(s).")


if __name__ == "__main__":
    main()
