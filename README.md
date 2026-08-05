# guangboyu.github.io

Personal site. Plain HTML and CSS, no build step and no dependencies. Open
`index.html` in a browser and it works.

The design follows [PRISM](https://github.com/xyjoey/PRISM) (MIT): deep navy and gold,
Georgia headings over Inter body, slate neutrals, avatar sidebar, card-based content.
PRISM itself is a Next.js template; this is a hand-written implementation of the same
look, so there is nothing to install or upgrade.

```
index.html             About, with the sidebar and representative work
publications.html      Papers, generated from publications.bib
projects.html          Code and work outside the papers
photography.html       Gallery, generated from assets/js/photos.js
publications.bib       The publication list you actually edit
assets/css/style.css   The whole design system, one file
assets/img/profile.jpg Headshot shown in the sidebar
assets/js/             Theme toggle, gallery, generated photo manifest
assets/photos/         Photos (see below)
scripts/               Publication and photo build scripts
```

---

## Before publishing

1. **Add your CV.** The sidebar links to `assets/cv.pdf`, which does not exist yet. Add
   the PDF, or remove that line from the Links panel on `index.html`.
2. **Check the email.** Currently `ygbusc@gmail.com`, in the sidebar of all four pages.
   Swap in your UCI address if you would rather have that one public.

The sidebar photo is `assets/img/profile.jpg`, a square centre crop of
`assets/head_photo.jpg`. To recrop it, or to swap in a different picture:

```bash
convert assets/head_photo.jpg -crop 724x724+181+0 +repage \
        -resize 720x720 -quality 88 assets/img/profile.jpg
```

The `+181+0` is the crop offset. Raise the first number to move the frame right, the
second to move it down. Any square image at that path works; nothing else needs editing.

---

## Adding a publication

Paste the BibTeX into `publications.bib` and run:

```bash
python3 scripts/build-pubs.py
```

That rewrites only the block between the `PUBS:START` and `PUBS:END` markers in
`publications.html`. The sidebar, the intro line, and the "Also" section below are
hand-edited and never touched.

Entries group by year, newest first. Anything with a `status` field sits above the
dated ones. **Your position in the author list is detected automatically**, so a
first-author paper gets its badge without you flagging it, and your name is highlighted
in gold wherever it appears.

Standard fields work as expected: `author`, `title`, `journal`, `booktitle`, `year`,
`volume`, `number`, `pages`, `doi`, `url`. Five extras are specific to this site:

| Field | Effect |
|---|---|
| `status = {Under review}` | Groups the entry above the dated ones |
| `venue = {...}` | Overrides the composed journal and volume line |
| `summary = {...}` | One short paragraph under the entry |
| `code = {https://...}` | Adds a "Code" link |
| `role = {co-first}` | Overrides the detected author position |

Write `*text*` for italics, which is how the species name in the *Clostridium novyi*
title is set. Use `and others` in the author list to render "et al.".

Re-running is safe and produces identical output, so it is fine to run on every edit.

---

## Adding photos

1. Copy full-resolution files into `assets/photos/originals/`. Name them the way you want
   the URL to read: `mono-lake-dawn.jpg`, not `DSC04182.jpg`.
2. Describe them in `assets/photos/captions.txt`, one line each:

   ```
   mono-lake-dawn.jpg | Mono Lake at dawn | Mono County, California | 2025
   delicate-arch.jpg  | Delicate Arch | Arches National Park, Utah | 2024 | feature
   ```

   Only the filename is required. Adding `feature` at the end makes a photo span the full
   gallery width instead of sitting in one column, which suits panoramas and whichever
   shot you want seen first.

3. Run the build:

   ```bash
   python3 scripts/build-photos.py
   ```

   It writes a 2400px display copy and a 1200px thumbnail for each photo, strips EXIF
   including GPS, and regenerates `assets/js/photos.js`. Re-running is cheap: files that
   are already current are skipped, and your captions are never overwritten.

Requires ImageMagick (`sudo apt install imagemagick`). Nothing else.

**Originals are not committed**, see `.gitignore`. The resized copies in `large/` and
`thumb/` are what ship, so run the build before you push.

---

## Publishing to GitHub Pages

You already own the `guangboyu.github.io` repository, and it currently holds an older
site. Look at what is in it before overwriting.

```bash
cd /home/guangbo/personal/personal-website
git init
git add -A
git commit -m "New personal site"
git branch -M main
git remote add origin git@github.com:guangboyu/guangboyu.github.io.git
git push -u origin main --force   # --force replaces the old site
```

Then in the repository: **Settings → Pages → Source: deploy from branch `main`, folder
`/ (root)`**. It is live at `https://guangboyu.github.io` a minute or two later.

### Custom domain

Put one line in a file named `CNAME` at the repository root:

```
guangboyu.com
```

At your registrar, add four `A` records for the apex pointing at `185.199.108.153`,
`185.199.109.153`, `185.199.110.153`, and `185.199.111.153`, plus a `CNAME` for `www`
pointing at `guangboyu.github.io`. Tick **Enforce HTTPS** once the certificate issues.

---

## Editing

- **Colours, fonts, spacing** live at the top of `assets/css/style.css` in `:root`, with
  the dark palette right below. Nothing else in the file hardcodes a colour, so retheming
  means editing one block.
- **The header, sidebar, and footer are duplicated** across the four pages. That is the
  price of having no build step. Change a nav link or a sidebar panel and you change it
  in four files.
- **Diagrams** are hand-written inline SVG using the `dg-*` classes. They draw in
  `currentColor`, so they invert correctly in dark mode with no extra work.
- **Tables** use `class="results"`. Mark the row that carries the point with
  `class="is-key"` so the emphasis lands on the right number.
