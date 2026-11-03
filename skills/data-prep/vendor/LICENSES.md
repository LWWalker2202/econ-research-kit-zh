# Vendored material in skills/data-prep/vendor

One upstream project is vendored in this directory. Its subdirectory carries its own `LICENSES.md` with the commit hash, the exact files copied, and where the licence text sits; this page is the index.

| Directory | Upstream repository | Commit | Licence |
|---|---|---|---|
| `awesome-econ-ai-stuff/` | https://github.com/meleantonio/awesome-econ-ai-stuff | `dd890d51c789fb8f8e316a2d7e4ed5d4bd793c50` | CC0 1.0 Universal |

Rules that apply to everything below this directory:

1. Copied verbatim. Not one byte is edited; fixes for data quirks go to `skills/data-prep/overrides/` when that layer exists.
2. Every vendored subdirectory carries its own `LICENSES.md` naming upstream, commit, licence, and copied paths.
3. No git submodules. The files are materialised in the tree so that a plain clone of this repository is complete.

Vendored content is template material, therefore language-neutral: it is byte-identical in `econ-research-kit` and `econ-research-kit-zh`.

No licence-clear upstream with reusable data-cleaning code was found in this round; the prose specification below is what qualifies. See `skills/tables-figures/vendor/` for the other two upstreams vetted in the same pass.
