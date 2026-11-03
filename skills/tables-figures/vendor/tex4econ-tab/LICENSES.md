# Licence — tex4econ-tab

- Upstream repository: https://github.com/FanWangEcon/Tex4Econ
- Commit copied: `8f7a254656b98ce5c152ea3b5ed1f2833cca496e`, read with `git rev-parse HEAD`
- Licence: MIT License, Copyright (c) 2019 Fan Wang
- Licence file in this directory: `LICENSE`, a verbatim copy of the upstream root `LICENSE` (1086 bytes)
- Copied on: 2026-11-03

## Files copied

| Local file | Upstream path |
|---|---|
| `LICENSE` | `LICENSE` |
| `estimates/estismall.tex` | `_tab/estimates/estismall.tex` |
| `multipanel/tab_4col_cts_dis2inter.tex` | `_tab/multipanel/tab_4col_cts_dis2inter.tex` |
| `multipanel/tab_6col_cts_dis2inter.tex` | `_tab/multipanel/tab_6col_cts_dis2inter.tex` |
| `multipanel/tab_6col_cts_dis2inter_texbody.tex` | `_tab/multipanel/tab_6col_cts_dis2inter_texbody.tex` |
| `text/fs_tab_text.tex` | `_tab/text/fs_tab_text.tex` |

## Why this subset

`_tab/` holds five LaTeX table fragments in three category subdirectories (`estimates/`, `multipanel/`, `text/`) plus four compiled PDF previews of the same tables (81 KB to 328 KB each). Only the `.tex` sources are copied: the PDFs are build output, not source, and would add about 665 KB to the repository. The category subdirectories are preserved; the `_tab/` level is dropped so that this vendor directory is the table collection itself.

## Modifications

None. All five `.tex` files and `LICENSE` are byte-identical to the upstream commit above; SHA-256 hashes were compared after copying. Nothing here is edited: changes belong in `skills/tables-figures/overrides/`.
