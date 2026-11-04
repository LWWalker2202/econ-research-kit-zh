"""Baseline table: three specifications on a deterministic synthetic panel.

This is the reference implementation of stage 5 (tables). It exists so that the
kit has one thing that can be *checked* instead of described:

    python templates/panel_ols.py --lang en
    # writes output/table1.tex

Compare the result with ``expected/table1.tex``. If they differ, either the
estimation library changed its numbers or the formatting changed; both are
worth knowing before a paper depends on it.

The dataset is synthetic and seeded, so the numbers are exact rather than
"about right". Never use it for a real paper -- it is a test fixture.

Stata equivalent: ``templates/make_table.do``.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from latex_table import render  # noqa: E402

SEED = 20260101
N_FIRM = 60
N_YEAR = 8
FIRST_YEAR = 2015


def make_panel() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    firm = np.repeat(np.arange(N_FIRM), N_YEAR)
    year = np.tile(np.arange(FIRST_YEAR, FIRST_YEAR + N_YEAR), N_FIRM)
    x = rng.normal(size=firm.size)
    treat = (rng.random(firm.size) < 0.4).astype(float)
    y = 1.0 + 0.5 * treat + 0.3 * x + rng.normal(size=firm.size)
    return pd.DataFrame(
        {"firm": firm, "year": year, "y": y, "treat": treat, "x": x}
    )


def _scalar(fit, *attrs, default=None):
    for attr in attrs:
        value = getattr(fit, attr, None)
        if value is None:
            continue
        if callable(value):
            try:
                return value()
            except TypeError:
                continue
        return value
    return default


def column(fit, label: str, depvar: str) -> dict:
    coefs = fit.coef()
    ses = fit.se()
    pvals = fit.pvalue()
    rows = [
        (
            "Treatment" if name == "treat" else "Control x",
            float(coefs[name]),
            float(ses[name]),
            float(pvals[name]),
        )
        for name in ("treat", "x")
        if name in coefs
    ]
    fixef_raw = str(getattr(fit, "_fixef", "") or "")
    fixef = [part.strip() for part in fixef_raw.split("+") if part.strip()]
    fe = {
        "Firm FE": "firm" in fixef,
        "Year FE": "year" in fixef,
    }
    return {
        "label": label,
        "coefs": rows,
        "fe": fe,
        "nobs": _scalar(fit, "_N", "nobs", default=""),
        "r2": _scalar(fit, "_r2"),
        "depvar": depvar,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=("en", "zh"), default="en")
    parser.add_argument("--out", default=os.path.join("output", "table1.tex"))
    args = parser.parse_args()

    import pyfixest as pf

    df = make_panel()
    models = [
        pf.feols("y ~ treat", data=df, vcov="HC1"),
        pf.feols("y ~ treat | firm + year", data=df, vcov={"CRV1": "firm"}),
        pf.feols("y ~ treat + x | firm + year", data=df, vcov={"CRV1": "firm"}),
    ]

    cols = [column(fit, f"({i + 1})", "y") for i, fit in enumerate(models)]
    cluster_note = (
        "标准误聚类在个体层面。" if args.lang == "zh" else "Standard errors are clustered at the firm level."
    )
    tex = render(
        cols,
        lang=args.lang,
        title="Baseline results" if args.lang == "en" else "基准回归结果",
        label="tab:main",
        cluster_note=cluster_note,
    )

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(tex)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
