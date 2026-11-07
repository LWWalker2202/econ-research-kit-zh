#!/usr/bin/env python3
"""Estimate a staggered difference-in-differences panel and write a report.

The panel is generated inside this script from a fixed seed, so every number in
``output/estimation-results.md`` and ``output/estimation-results.json`` is
reproducible: two consecutive runs write byte-identical files, which makes the
pinned copy under ``expected/`` a regression test rather than a decoration.

Five steps are run in order:

1. two-way fixed effects (individual and year);
2. the same specification plus two time-varying controls;
3. the same coefficients with standard errors clustered at the individual level;
4. an event study with two leads, two lags, and a binned endpoint on each side,
   base period -1;
5. the same coefficients with standard errors clustered at two more levels
   (block and year), so the reader sees how far the clustering assumption moves
   the standard error.

``--lang en|zh`` switches the wording of the report and changes nothing else, so
the machine-readable JSON is identical in both languages. The Stata counterpart
with the one-to-one step mapping is ``templates/estimate_main.do``.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import json
import os

import numpy as np
import pandas as pd
import pyfixest as pf

SEED = 20260315
N_ID = 60
FIRST_YEAR = 2010
N_YEAR = 10
COHORTS = ((2014, 20), (2016, 20))
BLOCK_SIZE = 4
EVENT_LEADS = 2
EVENT_LAGS = 2
BASE_PERIOD = -1
EVENT_TERMS = ("rel_le_m3", "rel_m2", "rel_p0", "rel_p1", "rel_p2", "rel_ge_p3")
CONTROL_TERMS = ("x1", "x2")
FE_TERMS = ("id", "year")

EN = {
    "h1": "Estimation results",
    "intro": (
        "This report is written by `templates/estimate_main.py` from a synthetic panel generated "
        "inside the script with a fixed seed. Every number below is recomputed on each run, so the "
        "file is meant to be diffed against `expected/estimation-results.md`: when the specification "
        "or the estimation library moves, the diff says where. The estimates are exact outputs of "
        "the seeded sample, not evidence about any real market."
    ),
    "s_fixture": "1. Fixture",
    "fixture_intro": (
        "The panel is balanced: 60 individuals observed from 2010 to 2019. Twenty individuals are "
        "treated from 2014 and twenty from 2016; the remaining twenty are never treated. Treatment "
        "is absorbing, so D is one from the cohort year onward and zero before it. The spread of "
        "cohort years is deliberate: it keeps the design away from the single-period case, where "
        "the two-way fixed effects coefficient and the event study answer the same question."
    ),
    "fixture_header": ("Item", "Value"),
    "fixture_rows": {
        "n_id": "Individuals",
        "years": "Years",
        "n_obs": "Observations",
        "cohort_2014": "Treated individuals, cohort 2014",
        "cohort_2016": "Treated individuals, cohort 2016",
        "never": "Never treated individuals",
        "treated_cells": "Treated individual-years",
        "treated_share": "Share of treated individual-years",
        "seed": "Generator seed",
    },
    "s_chain": "2. Main chain",
    "chain_intro": (
        "Column (1) is the workhorse: the outcome on the treatment indicator with individual and "
        "year fixed effects, which is the two-way fixed effects estimator. Column (2) adds two "
        "time-varying controls. Column (3) keeps the column (2) coefficients and changes only the "
        "standard errors, clustering them at the individual level, because treatment turns on for "
        "all remaining years of an individual and residuals are serially correlated within an "
        "individual. The coefficient on D moves from {c1:.4f} in column (1) to {c2:.4f} in column "
        "(2), less than half of its own standard error of {se:.4f}: the controls are not driving "
        "the comparison, and the standard error in column (3) is the one to quote."
    ),
    "chain_header": (
        "Term",
        "(1) Individual and year fixed effects",
        "(2) Plus controls",
        "(3) Clustered by individual",
    ),
    "chain_rows": {
        "n_obs": "Observations",
        "r2": "R-squared",
        "fe_id": "Individual fixed effects",
        "fe_year": "Year fixed effects",
        "se": "Standard errors",
    },
    "yes": "yes",
    "dash": "—",
    "se_iid": "iid",
    "se_cluster_id": "clustered by individual",
    "s_event": "3. Event study",
    "event_intro": (
        "The single coefficient on D averages every post-treatment year and hides timing. The event "
        "study replaces it with relative-time terms: the leads test whether the treatment timing is "
        "anticipated, the lags trace the dynamic path, and the period just before treatment is the "
        "base period and is omitted. Cells further than two periods from the cohort year are binned "
        "into the two endpoint terms instead of silently joining the base period. Controls and both "
        "sets of fixed effects are kept."
    ),
    "event_header": ("Relative period", "Coefficient (standard error)"),
    "event_periods": {
        "rel_le_m3": "-3 or earlier",
        "rel_m2": "-2",
        "rel_p0": "0",
        "rel_p1": "+1",
        "rel_p2": "+2",
        "rel_ge_p3": "+3 or later",
    },
    "event_base_label": "-1 (base period)",
    "event_base_value": "omitted",
    "event_rows": {
        "n_obs": "Observations",
        "r2": "R-squared",
        "fe": "Fixed effects",
        "controls": "Controls",
        "se": "Standard errors",
    },
    "fe_value": "individual, year",
    "controls_value": "x1, x2",
    "s_robust": "4. Robustness",
    "robust_intro": (
        "The specification stays at column (2) and only the cluster level changes. The coefficient "
        "on D is identical by construction, because a cluster level changes the variance estimator "
        "and not the point estimate; the standard error moves with the level of aggregation. The "
        "last row clusters on year with ten clusters, where the asymptotic cluster-robust standard "
        "error is optimistic: report that row next to a wild cluster bootstrap instead of treating "
        "it as a verdict."
    ),
    "robust_header": (
        "Cluster level",
        "Clusters",
        "Coefficient on D",
        "Standard error",
        "t",
        "p",
    ),
    "robust_clusters": {
        "iid": "none (iid)",
        "cluster_id": "individual",
        "cluster_block": "block, four individuals each",
        "cluster_year": "year",
    },
    "s_repro": "5. Reproducibility",
    "repro_lead": (
        "Run `python skills/estimation/templates/estimate_main.py --lang en` from the repository "
        "root, then diff `output/estimation-results.md` against this file and compare "
        "`output/estimation-results.json` with `expected/estimation-results.json`. The JSON is "
        "language-neutral, so `--lang en` and `--lang zh` write the same bytes; its checksum is "
    ),
    "repro_mid": (
        ". Two consecutive runs give the same checksum, which is what turns the seed into a "
        "regression test. The Stata counterpart `templates/estimate_main.do` repeats the five steps "
        "with `reghdfe`, clustering the same way; its random draws differ from the ones here, so it "
        "matches on structure and step order, not on values."
    ),
}

ZH = {
    "h1": "估计结果",
    "intro": (
        "本报告由 `templates/estimate_main.py` 生成，数据是脚本内部按固定种子合成的面板。下面每个数字都在每次运行时重算，"
        "所以这个文件本来就是拿来和 `expected/estimation-results.md` 做逐行比对的：设定或估计库一变，diff 就会指出变在哪。"
        "这些数字是固定种子样本的精确输出，不是关于任何真实市场的证据。"
    ),
    "s_fixture": "1. 测试数据",
    "fixture_intro": (
        "面板平衡：60 个个体，2010 到 2019 年。20 个个体从 2014 年起受处理，20 个从 2016 年起受处理，剩下 20 个从未受处理。"
        "处理是吸收型的：D 从处理组年份起取 1，之前取 0。两个处理组年份错开是刻意的，这样设计就不会退化成只有一个处理时点的情形，"
        "而在那种情形下双向固定效应系数与事件研究回答的是同一个问题。"
    ),
    "fixture_header": ("项目", "取值"),
    "fixture_rows": {
        "n_id": "个体数",
        "years": "年份",
        "n_obs": "观测数",
        "cohort_2014": "2014 组受处理个体数",
        "cohort_2016": "2016 组受处理个体数",
        "never": "从未受处理个体数",
        "treated_cells": "受处理个体—年份数",
        "treated_share": "受处理的个体—年份占比",
        "seed": "生成器种子",
    },
    "s_chain": "2. 主设定链",
    "chain_intro": (
        "第 (1) 列是主力设定：因变量对处理指示变量回归，加个体与年份双向固定效应，也就是双向固定效应估计量。第 (2) 列加入两个时变控制变量。"
        "第 (3) 列沿用第 (2) 列的系数，只把标准误改成按个体聚类，因为处理一旦开启就覆盖该个体此后所有年份，个体内残差存在序列相关。"
        "D 的系数从第 (1) 列的 {c1:.4f} 变成第 (2) 列的 {c2:.4f}，变化幅度不到它自己标准误 {se:.4f} 的一半：控制变量并没有改变这个比较，"
        "要引用的是第 (3) 列的标准误。"
    ),
    "chain_header": ("项", "(1) 个体与年份固定效应", "(2) 加控制变量", "(3) 按个体聚类"),
    "chain_rows": {
        "n_obs": "观测数",
        "r2": "R 平方",
        "fe_id": "个体固定效应",
        "fe_year": "年份固定效应",
        "se": "标准误",
    },
    "yes": "有",
    "dash": "—",
    "se_iid": "同方差",
    "se_cluster_id": "按个体聚类",
    "s_event": "3. 事件研究",
    "event_intro": (
        "D 的单一系数把处理后的每一年平均掉了，看不出时点结构。事件研究把它换成相对期虚拟变量：前置项检验处理时点是否被预期，"
        "后置项画出动态路径，而处理前一期作为基期被省略。距离处理组年份超过两期的格子归到两端各自的端点箱里，"
        "不让它们混进基期。控制变量与两组固定效应都保留。"
    ),
    "event_header": ("相对期", "系数（标准误）"),
    "event_periods": {
        "rel_le_m3": "-3 期及更早",
        "rel_m2": "-2 期",
        "rel_p0": "0 期",
        "rel_p1": "+1 期",
        "rel_p2": "+2 期",
        "rel_ge_p3": "+3 期及更晚",
    },
    "event_base_label": "-1 期（基期）",
    "event_base_value": "省略",
    "event_rows": {
        "n_obs": "观测数",
        "r2": "R 平方",
        "fe": "固定效应",
        "controls": "控制变量",
        "se": "标准误",
    },
    "fe_value": "个体、年份",
    "controls_value": "x1、x2",
    "s_robust": "4. 稳健性",
    "robust_intro": (
        "设定固定在第 (2) 列，只换聚类层级。D 的系数在构造上完全不变，因为聚类换的是方差估计量、不是点估计；标准误随聚合层级移动。"
        "最后一行按年份聚类，只有 10 个聚类，此时渐近聚类稳健标准误偏乐观：这一行应和野聚类 bootstrap 一起报告，而不是当成结论。"
    ),
    "robust_header": ("聚类层级", "聚类数", "D 的系数", "标准误", "t 值", "p 值"),
    "robust_clusters": {
        "iid": "不聚类（同方差）",
        "cluster_id": "个体",
        "cluster_block": "组（每四个个体一组）",
        "cluster_year": "年份",
    },
    "s_repro": "5. 可复现性",
    "repro_lead": (
        "在仓库根目录跑 `python skills/estimation/templates/estimate_main.py --lang zh`，然后把 `output/estimation-results.md` "
        "与本文件逐行比对，并把 `output/estimation-results.json` 与 `expected/estimation-results.json` 对照。JSON 与语言无关："
        "`--lang en` 与 `--lang zh` 写出完全相同的字节，其校验值是 "
    ),
    "repro_mid": (
        "。连跑两遍校验值不变，这正是把种子当回归测试用的原因。Stata 对照实现 `templates/estimate_main.do` 用 `reghdfe` "
        "重跑同样五步、按同样的层级聚类；它的随机抽样与这里不同，所以对齐的是结构与步骤顺序，不是数值。"
    ),
}

TEXT = {"en": EN, "zh": ZH}


def make_panel() -> pd.DataFrame:
    """Build the seeded panel with the treatment, controls, and cluster variables."""
    rng = np.random.default_rng(SEED)
    grid = pd.MultiIndex.from_product(
        [np.arange(N_ID), np.arange(FIRST_YEAR, FIRST_YEAR + N_YEAR)],
        names=["id", "year"],
    ).to_frame(index=False)

    cohort = np.zeros(N_ID, dtype=int)
    start = 0
    for year, count in COHORTS:
        cohort[start : start + count] = year
        start += count

    grid["cohort"] = cohort[grid["id"].to_numpy()]
    grid["block"] = grid["id"].to_numpy() // BLOCK_SIZE
    grid["D"] = ((grid["cohort"] > 0) & (grid["year"] >= grid["cohort"])).astype(float)

    id_effect = rng.normal(0.0, 0.8, N_ID)
    year_effect = 0.05 * (np.arange(FIRST_YEAR, FIRST_YEAR + N_YEAR) - FIRST_YEAR)
    grid["x1"] = rng.normal(0.0, 1.0, len(grid))
    grid["x2"] = rng.normal(0.2, 1.0, len(grid))
    grid["y"] = (
        0.45 * grid["D"].to_numpy()
        + 0.30 * grid["x1"].to_numpy()
        - 0.20 * grid["x2"].to_numpy()
        + id_effect[grid["id"].to_numpy()]
        + year_effect[grid["year"].to_numpy() - FIRST_YEAR]
        + rng.normal(0.0, 1.0, len(grid))
    )
    return grid.sort_values(["id", "year"]).reset_index(drop=True)


def add_event_time(panel: pd.DataFrame) -> pd.DataFrame:
    """Add relative time and its dummies, with binned endpoints and a clean base period."""
    frame = panel.copy()
    rel = (frame["year"] - frame["cohort"]).where(frame["cohort"] > 0)
    frame["rel"] = rel
    frame["rel_le_m3"] = (rel <= -(EVENT_LEADS + 1)).astype(float)
    frame["rel_ge_p3"] = (rel >= EVENT_LAGS + 1).astype(float)
    for lead in range(1, EVENT_LEADS + 1):
        frame[f"rel_m{lead}"] = (rel == -lead).astype(float)
    for lag in range(0, EVENT_LAGS + 1):
        frame[f"rel_p{lag}"] = (rel == lag).astype(float)
    return frame


def build_formula(terms, fixef_terms) -> str:
    """Assemble a formula string; the same string is quoted in the JSON."""
    left = "y ~ " + " + ".join(terms)
    if fixef_terms:
        left += " | " + " + ".join(fixef_terms)
    return left


def fixed_effects(fit) -> list:
    """Read the absorbed fixed effects off a pyfixest result.

    ``_fixef`` is a plain string such as ``'id + year'`` and is ``None`` for a
    model without fixed effects; the split has to strip the spaces around the
    plus signs.
    """
    raw = getattr(fit, "_fixef", None)
    if raw is None:
        return []
    return [part.strip() for part in str(raw).split("+") if part.strip()]


def coefficients(fit, terms) -> list:
    """Pull coefficient rows out of a fit, in the order the terms are given."""
    coef = fit.coef()
    se = fit.se()
    pvalue = fit.pvalue()
    rows = []
    for term in terms:
        rows.append(
            {
                "term": term,
                "coef": round(float(coef[term]), 6),
                "se": round(float(se[term]), 6),
                "t": round(float(coef[term] / se[term]), 6),
                "p": round(float(pvalue[term]), 6),
            }
        )
    return rows


def fit_spec(formula: str, data: pd.DataFrame, vcov):
    """Run one least squares fit with the given variance estimator."""
    return pf.feols(formula, data=data, vcov=vcov)


def estimate(panel: pd.DataFrame) -> dict:
    """Run the five steps and return everything the two output files need."""
    chain_terms = ("D",) + CONTROL_TERMS
    chain = [
        ("m1", ("D",), build_formula(("D",), FE_TERMS), "iid"),
        ("m2", chain_terms, build_formula(chain_terms, FE_TERMS), "iid"),
        ("m3", chain_terms, build_formula(chain_terms, FE_TERMS), "cluster_id"),
    ]
    fits = {}
    for spec_id, _terms, formula, vcov_label in chain:
        vcov = "iid" if vcov_label == "iid" else {"CRV1": vcov_label.split("_", 1)[1]}
        fits[spec_id] = fit_spec(formula, panel, vcov)

    event_panel = add_event_time(panel)
    event_formula = build_formula(EVENT_TERMS + CONTROL_TERMS, FE_TERMS)
    event_fit = fit_spec(event_formula, event_panel, {"CRV1": "id"})

    robust_formula = build_formula(chain_terms, FE_TERMS)
    levels = []
    for vcov_label, cluster_var in (
        ("iid", None),
        ("cluster_id", "id"),
        ("cluster_block", "block"),
        ("cluster_year", "year"),
    ):
        fit = fit_spec(robust_formula, panel, "iid" if cluster_var is None else {"CRV1": cluster_var})
        row = coefficients(fit, ("D",))[0]
        row["vcov"] = vcov_label
        row["n_clusters"] = None if cluster_var is None else int(panel[cluster_var].nunique())
        levels.append(row)

    panel_info = {
        "seed": SEED,
        "n_individuals": N_ID,
        "first_year": FIRST_YEAR,
        "last_year": FIRST_YEAR + N_YEAR - 1,
        "n_obs": int(len(panel)),
        "cohorts": [{"cohort_year": year, "n_individuals": count} for year, count in COHORTS],
        "never_treated": int((panel.groupby("id")["cohort"].first() == 0).sum()),
        "treated_cells": int(panel["D"].sum()),
        "treated_share": round(float(panel["D"].mean()), 6),
    }

    specifications = []
    for spec_id, terms, formula, vcov_label in chain:
        fit = fits[spec_id]
        specifications.append(
            {
                "id": spec_id,
                "formula": formula,
                "vcov": vcov_label,
                "n_obs": int(fit._N),
                "r2": round(float(fit._r2), 6),
                "fixef": fixed_effects(fit),
                "coefficients": coefficients(fit, terms),
            }
        )

    return {
        "panel": panel_info,
        "specifications": specifications,
        "event_study": {
            "formula": event_formula,
            "base_period": BASE_PERIOD,
            "window": [-EVENT_LEADS, EVENT_LAGS],
            "vcov": "cluster_id",
            "n_obs": int(event_fit._N),
            "r2": round(float(event_fit._r2), 6),
            "fixef": fixed_effects(event_fit),
            "coefficients": coefficients(event_fit, EVENT_TERMS),
        },
        "robustness": {
            "formula": robust_formula,
            "coefficient": "D",
            "levels": levels,
        },
    }


def render_table(header, rows) -> list:
    """Render one markdown table with a consistent pipe count."""
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def fmt_pair(coef: float, se: float) -> str:
    return "{0:.4f} ({1:.4f})".format(coef, se)


def render_md(results: dict, lang: str, json_sha: str) -> str:
    """Render the human-readable report in the requested language."""
    text = TEXT[lang]
    panel = results["panel"]
    specs = {spec["id"]: spec for spec in results["specifications"]}
    event = results["event_study"]
    robust = results["robustness"]

    def coef_of(spec_id: str, term: str) -> str:
        for row in specs[spec_id]["coefficients"]:
            if row["term"] == term:
                return fmt_pair(row["coef"], row["se"])
        return text["dash"]

    lines = ["# " + text["h1"], "", text["intro"], ""]

    lines.append("## " + text["s_fixture"])
    lines.append("")
    lines.append(text["fixture_intro"])
    lines.append("")
    rows = text["fixture_rows"]
    fixture_rows = [
        [rows["n_id"], str(panel["n_individuals"])],
        [rows["years"], "{0}-{1}".format(panel["first_year"], panel["last_year"])],
        [rows["n_obs"], str(panel["n_obs"])],
        [
            rows["cohort_2014"],
            str(panel["cohorts"][0]["n_individuals"]),
        ],
        [
            rows["cohort_2016"],
            str(panel["cohorts"][1]["n_individuals"]),
        ],
        [rows["never"], str(panel["never_treated"])],
        [rows["treated_cells"], str(panel["treated_cells"])],
        [rows["treated_share"], "{0:.4f}".format(panel["treated_share"])],
        [rows["seed"], str(panel["seed"])],
    ]
    lines.extend(render_table(text["fixture_header"], fixture_rows))
    lines.append("")

    lines.append("## " + text["s_chain"])
    lines.append("")
    chain_coef_m1 = specs["m1"]["coefficients"][0]
    chain_coef_m2 = specs["m2"]["coefficients"][0]
    lines.append(
        text["chain_intro"].format(
            c1=chain_coef_m1["coef"], c2=chain_coef_m2["coef"], se=chain_coef_m1["se"]
        )
    )
    lines.append("")
    row_names = text["chain_rows"]
    chain_rows = [
        ["D", coef_of("m1", "D"), coef_of("m2", "D"), coef_of("m3", "D")],
        ["x1", text["dash"], coef_of("m2", "x1"), coef_of("m3", "x1")],
        ["x2", text["dash"], coef_of("m2", "x2"), coef_of("m3", "x2")],
        [
            row_names["n_obs"],
            str(specs["m1"]["n_obs"]),
            str(specs["m2"]["n_obs"]),
            str(specs["m3"]["n_obs"]),
        ],
        [
            row_names["r2"],
            "{0:.4f}".format(specs["m1"]["r2"]),
            "{0:.4f}".format(specs["m2"]["r2"]),
            "{0:.4f}".format(specs["m3"]["r2"]),
        ],
        [row_names["fe_id"], text["yes"], text["yes"], text["yes"]],
        [row_names["fe_year"], text["yes"], text["yes"], text["yes"]],
        [row_names["se"], text["se_iid"], text["se_iid"], text["se_cluster_id"]],
    ]
    lines.extend(render_table(text["chain_header"], chain_rows))
    lines.append("")

    lines.append("## " + text["s_event"])
    lines.append("")
    lines.append(text["event_intro"])
    lines.append("")
    event_coefs = {row["term"]: row for row in event["coefficients"]}
    event_labels = text["event_periods"]
    event_rows = []
    for term in EVENT_TERMS[:2]:
        row = event_coefs[term]
        event_rows.append([event_labels[term], fmt_pair(row["coef"], row["se"])])
    event_rows.append([text["event_base_label"], text["event_base_value"]])
    for term in EVENT_TERMS[2:]:
        row = event_coefs[term]
        event_rows.append([event_labels[term], fmt_pair(row["coef"], row["se"])])
    event_row_names = text["event_rows"]
    event_rows.extend(
        [
            [event_row_names["n_obs"], str(event["n_obs"])],
            [event_row_names["r2"], "{0:.4f}".format(event["r2"])],
            [event_row_names["fe"], text["fe_value"]],
            [event_row_names["controls"], text["controls_value"]],
            [event_row_names["se"], text["se_cluster_id"]],
        ]
    )
    lines.extend(render_table(text["event_header"], event_rows))
    lines.append("")

    lines.append("## " + text["s_robust"])
    lines.append("")
    lines.append(text["robust_intro"])
    lines.append("")
    cluster_labels = text["robust_clusters"]
    robust_rows = []
    for level in robust["levels"]:
        n_clusters = text["dash"] if level["n_clusters"] is None else str(level["n_clusters"])
        robust_rows.append(
            [
                cluster_labels[level["vcov"]],
                n_clusters,
                "{0:.4f}".format(level["coef"]),
                "{0:.4f}".format(level["se"]),
                "{0:.2f}".format(level["t"]),
                "{0:.3f}".format(level["p"]),
            ]
        )
    lines.extend(render_table(text["robust_header"], robust_rows))
    lines.append("")

    lines.append("## " + text["s_repro"])
    lines.append("")
    lines.append(text["repro_lead"] + "`" + json_sha + "`" + text["repro_mid"])
    lines.append("")
    return "\n".join(lines)


def build_json(results: dict) -> str:
    """Serialise the machine-readable report; no language-dependent text goes in."""
    return json.dumps(results, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


LADDER_TEXT = {
    "en": {
        "h1": "# Specification ladder",
        "lead": (
            "One rung per row, in the order they were run. What matters is how far the "
            "coefficient moves between rungs, not its value on any single rung."
        ),
        "head": [
            "Step",
            "What changes",
            "Fixed effects",
            "Clustering",
            "N",
            "R2",
            "Coefficient on D (SE)",
            "Change vs previous",
        ],
        "rung": {
            "m1": "Baseline, treatment dummy only",
            "m2": "Add control variables",
            "m3": "Cluster at the individual level",
        },
        "event": "Event study around the treatment date",
        "robust": "Alternative clustering levels",
        "none": "",
        "stop": "Stops and waits for you: run --step {nxt} only after you have looked at this file.",
        "last": "Last rung. Run without --step for the full result file.",
        "alt_head": ["Clustering", "Clusters", "Coefficient on D", "Standard error"],
        "alt_lead": "The same specification under four variance estimators.",
        "ev_head": ["term", "coef (se)"],
        "cli_next": "next, not run yet: rung {next_step}, {next_label}",
    },
    "zh": {
        "h1": "# 设定阶梯",
        "lead": (
            "一级一行，顺序就是实际跑的顺序。要紧的是系数在级与级之间走了多远，"
            "而不是任何单独一级上的数值。"
        ),
        "head": [
            "步",
            "改了什么",
            "固定效应",
            "聚类层级",
            "N",
            "R2",
            "D 的系数（标准误）",
            "相对上一级",
        ],
        "rung": {
            "m1": "基准，只放处理变量",
            "m2": "加控制变量",
            "m3": "聚类到个体",
        },
        "event": "围绕处理日的事件研究",
        "robust": "换其他聚类层级",
        "none": "",
        "stop": "停下来等你：看过这个文件之后，再跑 --step {nxt}。",
        "last": "这是最后一级。不带 --step 跑一次，会写出完整结果文件。",
        "alt_head": ["聚类", "簇数", "D 的系数", "标准误"],
        "alt_lead": "同一个设定，四种方差估计量下的结果。",
        "ev_head": ["项", "系数（标准误）"],
        "cli_next": "下一步还没跑：第 {next_step} 级，{next_label}",
    },
}

LADDER_NEXT = {1: "m2", 2: "m3", 3: "event", 4: "robust"}


def _on_d(coefficients_list) -> dict:
    for row in coefficients_list:
        if row["term"] == "D":
            return row
    return {"coef": float("nan"), "se": float("nan")}


def render_ladder(results, lang: str, upto: int = 5) -> str:
    text = LADDER_TEXT[lang]
    rows = []
    previous = None
    for spec in results["specifications"]:
        step = int(spec["id"][1:])
        if step > upto:
            break
        hit = _on_d(spec["coefficients"])
        change = text["none"] if previous is None else "{0:+.4f}".format(hit["coef"] - previous)
        previous = hit["coef"]
        rows.append(
            "| {0} | {1} | {2} | {3} | {4} | {5:.3f} | {6:.4f} ({7:.4f}) | {8} |".format(
                step,
                text["rung"][spec["id"]],
                " + ".join(spec["fixef"]) or "-",
                spec["vcov"],
                spec["n_obs"],
                spec["r2"],
                hit["coef"],
                hit["se"],
                change,
            )
        )

    lines = [text["h1"], "", text["lead"], ""]
    lines.append("| " + " | ".join(text["head"]) + " |")
    lines.append("|" + "---|" * len(text["head"]))
    lines.extend(rows)

    if upto >= 4:
        event = results["event_study"]
        lines.extend(
            [
                "",
                "## {0}".format(text["event"]),
                "",
                "| " + text["ev_head"][0] + " | " + text["ev_head"][1] + " |",
                "|---|---|",
            ]
        )
        for row in event["coefficients"]:
            lines.append("| {0} | {1:.4f} ({2:.4f}) |".format(row["term"], row["coef"], row["se"]))

    if upto >= 5:
        lines.extend(
            [
                "",
                "## {0}".format(text["robust"]),
                "",
                text["alt_lead"],
                "",
                "| " + " | ".join(text["alt_head"]) + " |",
                "|" + "---|" * len(text["alt_head"]),
            ]
        )
        for level in results["robustness"]["levels"]:
            clusters = level["n_clusters"] if level["n_clusters"] is not None else "-"
            lines.append(
                "| {0} | {1} | {2:.4f} | {3:.4f} |".format(
                    level["vcov"], clusters, level["coef"], level["se"]
                )
            )

    if upto < 5:
        lines.extend(["", text["stop"].format(nxt=upto + 1)])
    else:
        lines.extend(["", text["last"]])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", choices=("en", "zh"), default="en", help="report wording")
    parser.add_argument("--out-dir", default="output", help="directory for the outputs")
    parser.add_argument(
        "--ladder",
        action="store_true",
        help="also write spec-ladder.md, one rung per line",
    )
    parser.add_argument(
        "--dump-csv",
        metavar="PATH",
        help="write the seeded panel to PATH as CSV and stop (for crosscheck.py)",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=0,
        metavar="N",
        help="run only the first N rungs and stop (1 to 5)",
    )
    args = parser.parse_args()

    panel = make_panel()
    if args.dump_csv:
        target = os.path.abspath(args.dump_csv)
        parent = os.path.dirname(target)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        panel.to_csv(target, index=False)
        print("wrote {0}".format(target))
        return 0
    results = estimate(panel)

    os.makedirs(args.out_dir, exist_ok=True)

    if args.step:
        if not 1 <= args.step <= 5:
            print("--step takes a number from 1 to 5", file=sys.stderr)
            return 2
        ladder_path = os.path.join(args.out_dir, "spec-ladder-step{0}.md".format(args.step))
        with open(ladder_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(render_ladder(results, args.lang, upto=args.step))
        text = LADDER_TEXT[args.lang]
        print("wrote {0}".format(os.path.abspath(ladder_path)))
        if args.step < 5:
            nxt = args.step + 1
            if nxt <= 3:
                next_label = text["rung"]["m{0}".format(nxt)]
            elif nxt == 4:
                next_label = text["event"]
            else:
                next_label = text["robust"]
            print(text["cli_next"].format(next_step=nxt, next_label=next_label))
        return 0

    json_text = build_json(results)
    json_bytes = json_text.encode("utf-8")
    json_sha = hashlib.sha256(json_bytes).hexdigest()
    md_text = render_md(results, args.lang, json_sha)

    md_path = os.path.join(args.out_dir, "estimation-results.md")
    json_path = os.path.join(args.out_dir, "estimation-results.json")
    with open(md_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(md_text)
    with open(json_path, "wb") as handle:
        handle.write(json_bytes)

    if args.ladder:
        ladder_path = os.path.join(args.out_dir, "spec-ladder.md")
        with open(ladder_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(render_ladder(results, args.lang, upto=5))
        print("wrote {0}".format(os.path.abspath(ladder_path)))

    specs = len(results["specifications"])
    print("wrote {0} ({1} specifications, {2} characters)".format(os.path.abspath(md_path), specs, len(md_text)))
    print("wrote {0} ({1} bytes)".format(os.path.abspath(json_path), len(json_bytes)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
