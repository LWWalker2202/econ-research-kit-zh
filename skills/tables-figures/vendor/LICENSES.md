# Vendored material in skills/tables-figures/vendor

Four upstream projects are vendored in this directory. Each subdirectory carries its own `LICENSES.md` with the commit hash, the exact files copied, and where the licence text sits; this page is the index.

| Directory | Upstream repository | Commit | Licence |
|---|---|---|---|
| `stata-schemepack/` | https://github.com/asjadnaqvi/Stata-schemes | `580187ca3cd1101a17da6518a258b8ac533f7c5e` | MIT |
| `awesome-econ-ai-stuff/` | https://github.com/meleantonio/awesome-econ-ai-stuff | `dd890d51c789fb8f8e316a2d7e4ed5d4bd793c50` | CC0 1.0 Universal |
| `mgmt-paper-skills/` | https://github.com/HaonanAlex/mgmt-paper-skills | `971d2f510dc849b3fbf55836f78f6f2847203a1f` | Apache-2.0 (LICENSE and NOTICE files travel with the material) |
| `tex4econ-tab/` | https://github.com/FanWangEcon/Tex4Econ | `8f7a254656b98ce5c152ea3b5ed1f2833cca496e` | MIT |

Rules that apply to everything below this directory:

1. Copied verbatim. Not one byte is edited; fixes and journal conventions go to `skills/tables-figures/overrides/`.
2. Every vendored subdirectory carries its own `LICENSES.md` naming upstream, commit, licence, and copied paths.
3. No git submodules. The files are materialised in the tree so that a plain clone of this repository is complete.

Candidates rejected so far:

- `EthanDeng/Chinese-ERJ` at `8cd9523ae8f34c3d272e5369a66a341317bc6c96`: licence is LPPL 1.3c. Verbatim redistribution is permitted, so "copy unchanged" would not conflict with it, but the material is a single journal's document class (`chinese-erj.cls` for 《经济研究》) that depends on the external `biblatex-gb7714-2015` package. Too narrow for this kit to carry, and it would put a licence family in the tree that constrains modified variants even though we never modify vendored files. Not vendored for now, recorded here rather than silently dropped.

Vendored content is code and template material, therefore language-neutral: it is byte-identical in `econ-research-kit` and `econ-research-kit-zh`.
