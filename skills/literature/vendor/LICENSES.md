# Vendored material in skills/literature/

One upstream project is vendored in this directory. Nothing here is ours; every
file is copied byte for byte and its `LICENSES.md` records where it came from.

| Directory | Upstream repository | Commit | Licence |
|---|---|---|---|
| `lit-review-assistant/` | https://github.com/meleantonio/awesome-econ-ai-stuff | `6c85497ad86161b34dbe0f52273e5c1978989350` | CC0 1.0 |

Considered and **not** vendored, with the reason:

- `zhouziyue233/great-econometrics`, skill `literature-review` — no LICENSE file in the
  repository, so redistribution is not permitted. Its ideas (a three-layer keyword
  matrix, JEL candidates, Boolean variants, multi-round search) informed
  `templates/search-plan.py`; no text was copied.
- `franklee16/academic-research-skills` — no LICENSE file; same reason.
