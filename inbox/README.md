# inbox

Drop zone for LeetCode tutorials. Nothing here is committed except this file.

Dump new or updated files here in any shape: the whole `tutorials/` folder, or
just the changed `.md` files plus the assets they reference. Then run

```bash
python3 scripts/import-leetcode.py            # add --dry-run to preview
```

or ask Claude to process the inbox. The import copies each tutorial to
`blog/leetcode/<Name>.md` with the images it uses, refreshes the study route
from the README's status table, deletes assets no tutorial uses any more,
rebuilds the blog, and empties this folder. Everything else in the dump (the
animation generator, fonts, notes) is deleted with it, so keep your originals
where you write them.
