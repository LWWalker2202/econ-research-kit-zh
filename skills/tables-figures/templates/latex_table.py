"""Render a booktabs three-line table from fitted models.

Why this file exists
--------------------
Estimation libraries change their output format every few releases, and the
format is the part a journal cares about. So estimation and formatting are
kept apart: pyfixest (or anything else) produces coefficients, this module
produces the table. The output is plain ``booktabs``: no ``makecell``, no
``threeparttable``, nothing beyond booktabs itself.

Two conventions are supported and they differ in more than wording:

* ``--lang en``  stars at * p<0.10, ** p<0.05, *** p<0.01, note starts with
  "Note:" and standard errors are labelled.
* ``--lang zh``  same thresholds, but the note starts with "注：" and the
  sentence order follows Chinese journal practice (先说明星号，再说括号里是什么).

Usage
-----
    from latex_table import render
    tex = render(cols, lang="en", title="Baseline results")
    open("output/table1.tex", "w", encoding="utf-8").write(tex)

``cols`` is a list of dicts, one per column::

    {
      "label":  "(1)",
      "coefs":  [("Treatment", 0.503, 0.097, 0.000), ...],  # label, b, se, p
      "fe":     {"Firm FE": True, "Year FE": True},
      "nobs":   480,
      "r2":     0.188,
      "depvar": "y",
    }

Nothing here guesses a number: whatever is passed in is printed. If a value
is missing the cell is left empty rather than filled with a placeholder.
"""

from __future__ import annotations

DASH = "---"

STAR_THRESHOLDS = ((0.01, "***"), (0.05, "**"), (0.10, "*"))


def stars(p) -> str:
    """Return the significance marker for a p-value."""
    if p is None:
        return ""
    for cut, mark in STAR_THRESHOLDS:
        if p < cut:
            return mark
    return ""


def _num(x, digits: int) -> str:
    if x is None:
        return ""
    return f"{x:.{digits}f}"


def _note(lang: str) -> str:
    """Star legend only. How the standard errors were computed belongs in
    ``cluster_note``, because it differs by specification."""
    if lang == "zh":
        return "注：***、**、* 分别表示在 1%、5%、10% 的水平上显著；括号内为标准误。"
    return (
        "Note: ***, ** and * denote significance at the 1%, 5% and 10% levels; "
        "standard errors are in parentheses."
    )


def render(
    cols,
    *,
    lang: str = "en",
    title: str = "",
    label: str = "",
    digits: int = 3,
    cluster_note: str = "",
    extra_note: str = "",
) -> str:
    """Return a complete LaTeX ``table`` environment as a string."""
    if not cols:
        raise ValueError("render() needs at least one column")

    ncol = len(cols)

    # Row order is the order of the first column, so that a coefficient kept in
    # column 1 but dropped in column 2 does not shift the table.
    order = []
    for label_name, *_ in cols[0]["coefs"]:
        order.append(label_name)
    for col in cols[1:]:
        for label_name, *_ in col["coefs"]:
            if label_name not in order:
                order.append(label_name)

    by_col = [{c[0]: c for c in col["coefs"]} for col in cols]

    lines = []
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"\centering")
    if title:
        lines.append(r"\caption{%s}" % title)
    if label:
        lines.append(r"\label{%s}" % label)
    lines.append(r"\begin{tabular}{l" + "c" * ncol + "}")
    lines.append(r"\toprule")

    depvars = [c.get("depvar", "") for c in cols]
    if any(depvars):
        first = depvars[0]
        if all(d == first for d in depvars):
            lines.append(r"\multicolumn{%d}{c}{%s} \\" % (ncol + 1, first))
            lines.append(r"\midrule")
        else:
            lines.append(" & " + " & ".join(depvars) + r" \\")
            lines.append(r"\midrule")

    lines.append(" & " + " & ".join(c.get("label", "") for c in cols) + r" \\")
    lines.append(r"\midrule")

    for name in order:
        coef_cells, se_cells = [], []
        for idx, col in enumerate(cols):
            entry = by_col[idx].get(name)
            if entry is None:
                coef_cells.append("")
                se_cells.append("")
            else:
                _, b, se, p = entry
                coef_cells.append(_num(b, digits) + stars(p))
                se_cells.append("(" + _num(se, digits) + ")" if se is not None else "")
        lines.append(name + " & " + " & ".join(coef_cells) + r" \\")
        if any(se_cells):
            lines.append(" & " + " & ".join(se_cells) + r" \\")
        lines.append(r"\addlinespace[0.3ex]")

    fe_names = []
    for col in cols:
        for key in col.get("fe", {}):
            if key not in fe_names:
                fe_names.append(key)
    if fe_names:
        lines.append(r"\midrule")
        for fe in fe_names:
            cells = ["Yes" if col.get("fe", {}).get(fe) else DASH for col in cols]
            lines.append(fe + " & " + " & ".join(cells) + r" \\")
        lines.append(r"\addlinespace[0.3ex]")

    lines.append(r"\midrule")
    lines.append("Observations & " + " & ".join(str(c.get("nobs", "")) for c in cols) + r" \\")
    if any(c.get("r2") is not None for c in cols):
        lines.append(
            r"$R^2$ & "
            + " & ".join(
                _num(c.get("r2"), digits) if c.get("r2") is not None else ""
                for c in cols
            )
            + r" \\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")

    paras = [_note(lang)]
    if cluster_note:
        paras.append(cluster_note)
    if extra_note:
        paras.append(extra_note)
    # Chinese notes are not separated by a space; English sentences are.
    joiner = "" if lang == "zh" else " "
    lines.append(r"\par\smallskip\footnotesize " + joiner.join(paras))
    lines.append(r"\end{table}")

    return "\n".join(lines) + "\n"
