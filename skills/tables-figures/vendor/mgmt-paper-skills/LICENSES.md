# Licence — mgmt-paper-skills

- Upstream repository: https://github.com/HaonanAlex/mgmt-paper-skills
- Commit copied: `971d2f510dc849b3fbf55836f78f6f2847203a1f`, read with `git rev-parse HEAD`
- Licence: Apache License 2.0, Copyright 2026 MGMT-Paper-Skills Contributors
- Licence files in this directory: the upstream repository-root `LICENSE` is copied verbatim as `LICENSE` here. `mgmt-paper-tables/LICENSE` and `mgmt-paper-publication-figures/LICENSE` are the full Apache-2.0 text that those subdirectories carry upstream.
- NOTICE files: `mgmt-paper-tables/NOTICE` and `mgmt-paper-publication-figures/NOTICE` are copied verbatim, as Apache-2.0 requires. The upstream repository has no root `NOTICE`, and `mgmt-paper-journal-figures/` carries neither `LICENSE` nor `NOTICE` upstream; the root `LICENSE` in this directory governs it.
- Copied on: 2026-11-03

## Directories copied

| Local directory | Upstream directory | Files | Bytes |
|---|---|---|---|
| `mgmt-paper-tables/` | `mgmt-paper-tables/` | 45 | 73183 |
| `mgmt-paper-publication-figures/` | `mgmt-paper-publication-figures/` | 22 | 71217 |
| `mgmt-paper-journal-figures/` | `mgmt-paper-journal-figures/` | 6 | 13015 |

Plus `LICENSE`, the upstream root licence file. The two `NOTICE` files travel inside the directories that carry them (135 and 365 bytes).

## What the three directories contain

- `mgmt-paper-tables/` — the most relevant part of this upstream. `references/journal-formats.md` records the table rules of 《经济研究》, 《管理世界》, Journal of Finance and Management Science; `significance-conventions.md` gives the star thresholds and the cases where stars are not acceptable evidence; `se-types.md` covers standard-error choices; `table-anatomy.md`, `multi-column-design.md` and `common-mistakes.md` cover layout. Templates ship in three languages: Stata (`estout` / `esttab`, twelve do-files), R (`modelsummary`, `fixest`, eleven scripts) and Python (`stargazer`, `linearmodels`, nine scripts), with tests for skill structure and template syntax.
- `mgmt-paper-publication-figures/` — figure and table conventions for Chinese journals (fonts, sizes, colour, line width, captions), a colour-blind and black-and-white readability check, seven matplotlib templates (line, bar, scatter, box, coefficient, heatmap, histogram) with a `matplotlibrc`, and a LaTeX `booktabs` three-line-table fragment.
- `mgmt-paper-journal-figures/` — journal-level figure specifications: `references/journal-profiles.md` profiles the UTD 24 business journals by figure style, export format and notes; `references/nature-level-checklist.md` is a pre-submission checklist; `templates/python/journal_figure.py` is the figure script.

## Modifications

None. All 73 files in the three subdirectories and the root `LICENSE` are byte-identical to the upstream commit above; SHA-256 hashes were compared after copying. Nothing here is edited: changes for this kit's own conventions belong in `skills/tables-figures/overrides/`.
