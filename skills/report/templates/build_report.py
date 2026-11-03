#!/usr/bin/env python3
"""Build a fixed-format Markdown report from frozen exhibit and estimate files.

The builder reads two files and nothing else: a LaTeX table from the
tables-figures stage and a JSON file from the estimation stage. Every number in
the output is copied or rounded from those two files. A field that they do not
contain is printed as a placeholder instead of a guess, so the report never
states a result that the frozen files do not support.

Run from the repository root:

    python skills/report/templates/build_report.py --tables skills/tables-figures/expected/table1.tex --results skills/estimation/expected/estimation-results.json --lang en --out output/report.md

The output is a pure function of the two input files, the language flag, and the
paths printed in the reproduction section; two runs on the same inputs produce
the same bytes.
"""

import argparse
import json
import os
import sys
from pathlib import Path

PLACEHOLDER = {"en": "[to fill]", "zh": "[待填]"}

TEXT = {
    "en": {
        "title": "Reproducible report",
        "intro": (
            "Built by `skills/report/templates/build_report.py` from the two frozen "
            "files listed under `## How to reproduce`. Every number below is copied or "
            "rounded from those files; a field they do not contain is printed as a "
            "placeholder rather than typed by hand."
        ),
        "h_conclusion": "One-line conclusion",
        "conclusion": (
            "The coefficient on `{term}` is {coef}, with a standard error of {se} "
            "({vcov_desc}); it is estimated on {n_obs} observations under the "
            "specification `{formula}`."
        ),
        "conclusion_missing": (
            "The results file contains no specification the builder can select, so the "
            "benchmark statement stays open as `[to fill]`."
        ),
        "h_main": "Main results",
        "main_estimate": (
            "Baseline specification selected from `{results}`: `{formula}` with fixed "
            "effects `{fixef}`; point estimate {coef}, standard error {se}, p-value {p}, "
            "R-squared {r2}, observations {n_obs}."
        ),
        "main_embed": (
            "Table 1 is embedded verbatim from `{tables}`. A converter should pass the "
            "fenced block through unchanged so that the booktabs-style layout and the "
            "table note survive."
        ),
        "main_missing": (
            "The results file contains no specification the builder can select, so the "
            "main estimate stays open as `[to fill]`."
        ),
        "h_rob": "Robustness",
        "rob_intro": (
            "Each item below applies one variance estimator to the robustness "
            "specification `{formula}`; the point estimate is held fixed, so the "
            "comparison isolates the standard errors."
        ),
        "rob_item": "- {vcov_desc}: coefficient {coef}, standard error {se}, p-value {p}{clusters}.",
        "clusters": ", {n} clusters",
        "rob_missing": (
            "The results file records no robustness levels, so this section stays a "
            "placeholder."
        ),
        "h_data": "Data and definitions",
        "data_intro": (
            "This section is written by the researcher. The builder leaves it open on "
            "purpose: the two input files record estimates and exhibits, not sample "
            "construction, so any sentence a machine typed here would be invention."
        ),
        "data_items": [
            "- Sample frame and period: `{ph}`",
            "- Unit of observation: `{ph}`",
            "- Variable definitions and data sources: `{ph}`",
            "- Sample restrictions and winsorizing rules: `{ph}`",
        ],
        "h_repro": "How to reproduce",
        "repro_script": "- Estimation script: `{script}`",
        "repro_seed": "- Random seed: `{seed}` (read from the results file)",
        "repro_seed_missing": "- Random seed: `{ph}` (the results file records none)",
        "repro_inputs": "- Input files: `{tables}` and `{results}`",
        "repro_command": "- Command: `{command}`",
        "h_missing": "What is still missing",
        "missing_noscript": (
            "- The estimation script is not recorded; pass `--script` so a reader can "
            "rerun the estimates."
        ),
        "missing_data": (
            "- The data and definitions section is still open; only the researcher can "
            "close it."
        ),
        "missing_table": (
            "- The embedded table does not contain the baseline coefficient {coef} from "
            "the results file. Check that both inputs come from the same project before "
            "the report leaves the folder."
        ),
        "missing_event": (
            "- Event-study coefficients are present in the results file but are not "
            "summarised in this report."
        ),
        "missing_figure": (
            "- No figure is embedded; figures are produced in the tables-figures stage "
            "and included separately."
        ),
    },
    "zh": {
        "title": "可复现报告",
        "intro": (
            "本文件由 `skills/report/templates/build_report.py` 从 `## 复现方式` 一节列出的"
            "两个冻结文件生成。下文所有数值都取自这两个文件，文件里没有的字段一律打印为 "
            "`[待填]`，不由人手补写。"
        ),
        "h_conclusion": "一句话结论",
        "conclusion": (
            "`{term}` 的系数为 {coef}，标准误为 {se}（{vcov_desc}）；该估计基于 {n_obs} "
            "个观测、设定为 `{formula}`。"
        ),
        "conclusion_missing": (
            "结果文件里没有可供选取的设定，基准结论暂留为 `[待填]`。"
        ),
        "h_main": "主结果",
        "main_estimate": (
            "从 `{results}` 选定的基准设定：`{formula}`，固定效应 `{fixef}`；点估计 "
            "{coef}，标准误 {se}，p 值 {p}，R 方 {r2}，观测数 {n_obs}。"
        ),
        "main_embed": (
            "下表从 `{tables}` 原样嵌入。转换时请让代码块原样通过，以保留三线表版式与表注。"
        ),
        "main_missing": "结果文件里没有可供选取的设定，主结果暂留为 `[待填]`。",
        "h_rob": "稳健性",
        "rob_intro": (
            "下面每一项对同一个稳健性设定 `{formula}` 换一种方差估计方式；点估计保持不变，"
            "因此比较的是标准误。"
        ),
        "rob_item": "- {vcov_desc}：系数 {coef}，标准误 {se}，p 值 {p}{clusters}。",
        "clusters": "，聚类数 {n}",
        "rob_missing": "结果文件里没有记录稳健性设定，本节暂留为 `[待填]`。",
        "h_data": "数据与口径",
        "data_intro": (
            "本节由研究者填写。生成器故意留空：两个输入文件记录的是估计结果与表图，不含样本"
            "构造过程，由机器写在这里的每一句都会是无中生有。"
        ),
        "data_items": [
            "- 样本范围与时间跨度：`{ph}`",
            "- 观测单位：`{ph}`",
            "- 变量定义与数据来源：`{ph}`",
            "- 样本剔除规则与缩尾处理：`{ph}`",
        ],
        "h_repro": "复现方式",
        "repro_script": "- 估计脚本：`{script}`",
        "repro_seed": "- 随机种子：`{seed}`（读自结果文件）",
        "repro_seed_missing": "- 随机种子：`{ph}`（结果文件未记录）",
        "repro_inputs": "- 输入文件：`{tables}` 与 `{results}`",
        "repro_command": "- 命令：`{command}`",
        "h_missing": "还缺什么",
        "missing_noscript": (
            "- 估计脚本尚未记录；传入 `--script` 之后读者才能复跑估计。"
        ),
        "missing_data": (
            "- “数据与口径”一节仍是空位，只能由研究者补齐。"
        ),
        "missing_table": (
            "- 嵌入的表里没有结果文件中的基准系数 {coef}。报告流出之前，先确认两个输入文件"
            "来自同一个项目。"
        ),
        "missing_event": "- 结果文件里有事件研究系数，本报告没有汇总。",
        "missing_figure": "- 本报告不嵌入图；图在表图阶段产出，另行插入。",
    },
}


def read_text(path):
    # utf-8-sig accepts a plain UTF-8 file and one saved with a byte-order mark,
    # which spreadsheet and statistical exports often add.
    with open(path, "r", encoding="utf-8-sig") as handle:
        return handle.read()


def fmt(value, places=3):
    if value is None:
        return None
    try:
        return "{0:.{1}f}".format(float(value), places)
    except (TypeError, ValueError):
        return None


def select_baseline(results):
    specs = results.get("specifications") or []
    if not specs:
        return None, None
    clustered = [spec for spec in specs if str(spec.get("vcov", "")).startswith("cluster_")]
    spec = clustered[-1] if clustered else specs[-1]
    target = (results.get("robustness") or {}).get("coefficient")
    coefficients = spec.get("coefficients") or []
    chosen = None
    if target:
        for item in coefficients:
            if item.get("term") == target:
                chosen = item
                break
    if chosen is None and coefficients:
        chosen = coefficients[0]
    return spec, chosen


def describe_vcov(vcov, lang, placeholder):
    name = str(vcov or "")
    if not name:
        return placeholder
    if name == "iid":
        return "iid standard errors" if lang == "en" else "独立同分布标准误"
    if name.startswith("cluster_"):
        group = name[len("cluster_"):]
        if lang == "en":
            return "standard errors clustered at the {0} level".format(group)
        return "在 {0} 层面聚类的标准误".format(group)
    if lang == "en":
        return "standard errors of type {0}".format(name)
    return "类型为 {0} 的标准误".format(name)


def script_display():
    try:
        rel = os.path.relpath(os.path.abspath(__file__), os.getcwd())
    except ValueError:
        rel = os.path.abspath(__file__)
    return rel.replace("\\", "/")


def build_command(args, script_path):
    parts = [
        "python",
        script_path,
        "--tables",
        args.tables,
        "--results",
        args.results,
        "--lang",
        args.lang,
        "--out",
        args.out,
    ]
    if args.script:
        parts.extend(["--script", args.script])
    return " ".join(parts)


def compose(results, table_text, lang, args, command):
    text = TEXT[lang]
    ph = PLACEHOLDER[lang]
    spec, chosen = select_baseline(results)

    blocks = ["# " + text["title"], "", text["intro"], ""]

    blocks.extend(["## " + text["h_conclusion"], ""])
    if spec and chosen:
        blocks.append(
            text["conclusion"].format(
                term=chosen.get("term") or ph,
                coef=fmt(chosen.get("coef")) or ph,
                se=fmt(chosen.get("se")) or ph,
                vcov_desc=describe_vcov(spec.get("vcov"), lang, ph),
                n_obs=spec.get("n_obs") if spec.get("n_obs") is not None else ph,
                formula=spec.get("formula") or ph,
            )
        )
    else:
        blocks.append(text["conclusion_missing"])
    blocks.append("")

    blocks.extend(["## " + text["h_main"], ""])
    if spec and chosen:
        fixef = spec.get("fixef") or []
        blocks.append(
            text["main_estimate"].format(
                results=args.results,
                formula=spec.get("formula") or ph,
                fixef=", ".join(str(item) for item in fixef) if fixef else ph,
                coef=fmt(chosen.get("coef")) or ph,
                se=fmt(chosen.get("se")) or ph,
                p=fmt(chosen.get("p")) or ph,
                r2=fmt(spec.get("r2")) or ph,
                n_obs=spec.get("n_obs") if spec.get("n_obs") is not None else ph,
            )
        )
    else:
        blocks.append(text["main_missing"])
    blocks.append("")
    blocks.append(text["main_embed"].format(tables=args.tables))
    blocks.append("")
    blocks.extend(["```latex", table_text.strip("\n"), "```", ""])

    blocks.extend(["## " + text["h_rob"], ""])
    robustness = results.get("robustness") or {}
    levels = robustness.get("levels") or []
    if levels:
        blocks.append(text["rob_intro"].format(formula=robustness.get("formula") or ph))
        blocks.append("")
        for level in levels:
            count = level.get("n_clusters")
            clusters = text["clusters"].format(n=count) if count is not None else ""
            blocks.append(
                text["rob_item"].format(
                    vcov_desc=describe_vcov(level.get("vcov"), lang, ph),
                    coef=fmt(level.get("coef")) or ph,
                    se=fmt(level.get("se")) or ph,
                    p=fmt(level.get("p")) or ph,
                    clusters=clusters,
                )
            )
    else:
        blocks.append(text["rob_missing"])
    blocks.append("")

    blocks.extend(["## " + text["h_data"], ""])
    blocks.append(text["data_intro"])
    blocks.append("")
    for item in text["data_items"]:
        blocks.append(item.format(ph=ph))
    blocks.append("")

    blocks.extend(["## " + text["h_repro"], ""])
    blocks.append(text["repro_script"].format(script=args.script or ph))
    seed = (results.get("panel") or {}).get("seed")
    if seed is not None:
        blocks.append(text["repro_seed"].format(seed=seed))
    else:
        blocks.append(text["repro_seed_missing"].format(ph=ph))
    blocks.append(text["repro_inputs"].format(tables=args.tables, results=args.results))
    blocks.append(text["repro_command"].format(command=command))
    blocks.append("")

    missing = []
    if not args.script:
        missing.append(text["missing_noscript"])
    missing.append(text["missing_data"])
    coef_text = fmt(chosen.get("coef")) if chosen else None
    if coef_text and coef_text not in table_text:
        missing.append(text["missing_table"].format(coef=coef_text))
    if results.get("event_study"):
        missing.append(text["missing_event"])
    missing.append(text["missing_figure"])
    blocks.extend(["## " + text["h_missing"], ""])
    blocks.extend(missing)
    blocks.append("")

    return "\n".join(blocks).rstrip("\n") + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build a fixed-format Markdown report from frozen exhibit and estimate files."
    )
    parser.add_argument("--tables", required=True, help="LaTeX table file to embed verbatim")
    parser.add_argument("--results", required=True, help="JSON file written by the estimation stage")
    parser.add_argument("--lang", choices=["en", "zh"], default="en", help="prose language")
    parser.add_argument("--out", required=True, help="path of the Markdown file to write")
    parser.add_argument(
        "--script",
        default="",
        help="path of the estimation script, printed in the reproduction section",
    )
    args = parser.parse_args(argv)

    results = json.loads(read_text(args.results))
    table_text = read_text(args.tables)
    command = build_command(args, script_display())
    report = compose(results, table_text, args.lang, args, command)

    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(report)
    print("wrote {0} ({1} characters)".format(args.out, len(report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
