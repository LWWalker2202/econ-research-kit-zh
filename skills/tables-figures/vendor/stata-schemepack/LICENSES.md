# Licence — stata-schemepack

- Upstream repository: https://github.com/asjadnaqvi/Stata-schemes (GitHub redirects this name to `asjadnaqvi/stata-schemepack`; the Stata package inside is `schemepack`)
- Commit copied: `580187ca3cd1101a17da6518a258b8ac533f7c5e`, from `git rev-parse HEAD` on a `--depth 1` clone
- Licence: MIT License, Copyright (c) 2022 Asjad Naqvi
- Licence file in this directory: `LICENSE`, a verbatim copy of the upstream root `LICENSE` (1089 bytes)
- Copied on: 2026-11-03

## Files copied

Every file is taken from the upstream `installation/` directory, except `LICENSE` which comes from the repository root. Relative paths are preserved.

| Local file | Upstream path |
|---|---|
| `LICENSE` | `LICENSE` |
| `scheme-cblind1.scheme` | `installation/scheme-cblind1.scheme` |
| `scheme-white_brbg.scheme` | `installation/scheme-white_brbg.scheme` |
| `scheme-white_cividis.scheme` | `installation/scheme-white_cividis.scheme` |
| `scheme-white_hue.scheme` | `installation/scheme-white_hue.scheme` |
| `scheme-white_jet.scheme` | `installation/scheme-white_jet.scheme` |
| `scheme-white_piyg.scheme` | `installation/scheme-white_piyg.scheme` |
| `scheme-white_ptol.scheme` | `installation/scheme-white_ptol.scheme` |
| `scheme-white_tableau.scheme` | `installation/scheme-white_tableau.scheme` |
| `scheme-white_viridis.scheme` | `installation/scheme-white_viridis.scheme` |
| `scheme-white_w3d.scheme` | `installation/scheme-white_w3d.scheme` |

## Why this subset

These are Stata graph scheme definitions: the complete white-background family plus the colour-blind-friendly `cblind1` scheme, used as figure themes for `skills/tables-figures/`. The upstream `figures/` preview images, the `data/` test dataset and do-file, and the `schemepack.pkg` / `schemepack.sthlp` / `stata.toc` installation files are not copied. The help file describes the whole package, not this selection, so shipping it here would document files that are absent.

A `.scheme` file is installed by placing it in the Stata personal directory or by `net install schemepack` from upstream; this repository only carries the definitions as reference and as the source for the overrides layer.

## Modifications

None. Every file in this directory is byte-identical to the upstream commit above; SHA-256 hashes were compared after copying.
