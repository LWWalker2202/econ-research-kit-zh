"""Clean a dirty panel: the reference implementation of stage 3 (data-prep).

The data-prep skill describes six cleaning steps. This file performs them on a
synthetic panel so that the description can be *checked*:

    python skills/data-prep/templates/clean_panel.py --lang en
    # writes output/clean_panel.csv, output/clean_panel_summary.csv and
    # output/cleaning-log.md

Compare the log with ``expected/cleaning-log.md``. If the two differ, either a
cleaning rule changed or the numbers moved; both are worth knowing before a
paper depends on the pipeline.

The panel is synthetic and seeded, and every anomaly is injected at a fixed row
position, so the counts in the log are exact rather than "about right". Never
use the fixture for a real paper -- it is a test.

Steps, in order: deduplicate, drop rows missing a key field, check panel
balance, winsorize the ratios, harmonize units, flag definition drift. The
language switch changes the log wording only, never a number.

Stata equivalent: ``templates/clean_panel.do``.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys

import numpy as np
import pandas as pd

# ---- the fixture ----------------------------------------------------------
SEED = 20261103
N_FIRM = 40
FIRST_YEAR = 2018
N_YEAR = 6
BALANCED_CELLS = N_FIRM * N_YEAR

# Row positions at which the generator injects each failure. Positions are
# fixed on purpose: a seeded draw would work too, but fixed positions let a
# reader check the fixture by eye.
DUPLICATE_ROWS = (5, 42, 90, 133, 201)
MISSING_KEY_ROWS = {"revenue": (11, 57, 118, 176), "roa": (33, 95, 210)}
MISSING_NON_KEY_ROWS = {"leverage": (70, 140, 205)}
OUTLIER_ROWS = {
    "roa": {7: 1.85, 61: 2.40, 150: -1.10},
    "leverage": {22: 9.70, 180: 12.40},
}

KEY_FIELDS = ("revenue", "roa")
WINSOR_FIELDS = ("roa", "leverage")
WINSOR_LIMITS = (0.01, 0.99)
WINSOR_PERCENTILES = (1, 99)

# Derived variables are declared here, not in the code that uses them.
YEAR_YUAN_LAST = 2019
UNIT_FACTOR = 10000.0

# The codebook: what each variable actually meant in each period. Step 6 reads
# this table instead of assuming the variable is stable across years.
DEFINITIONS = {
    "revenue": (
        (2018, 2019, "yuan", "status_unit"),
        (2020, 2023, "ten_thousand_yuan", "status_reference"),
    ),
    "roa": (
        (2018, 2019, "net_profit_assets", "status_vintage_1"),
        (2020, 2023, "operating_profit_assets", "status_vintage_2"),
    ),
}
DRIFT_KIND = {"revenue": "unit", "roa": "definition"}


# ---- fixture construction -------------------------------------------------
def make_dirty_panel() -> pd.DataFrame:
    """Return the seeded panel with every failure already injected."""
    rng = np.random.default_rng(SEED)
    n = BALANCED_CELLS
    firm = np.repeat(np.arange(1, N_FIRM + 1), N_YEAR)
    year = np.tile(np.arange(FIRST_YEAR, FIRST_YEAR + N_YEAR), N_FIRM)

    size = np.repeat(rng.lognormal(mean=np.log(50000.0), sigma=0.8, size=N_FIRM), N_YEAR)
    assets = size * np.exp(rng.normal(0.0, 0.1, size=n))
    revenue_wan = assets * rng.uniform(0.5, 1.6, size=n)
    roa = 0.03 + 0.05 * rng.normal(size=n)
    # Two periods, two definitions: net profit before 2020, operating profit from
    # 2020 on. The level shift is the drift a cleaning log has to warn about.
    roa = roa + np.where(year >= YEAR_YUAN_LAST + 1, 0.03, 0.0)
    leverage = np.clip(0.55 + 0.25 * rng.normal(size=n), 0.0, None)

    # Mixed units: yuan before 2020, ten-thousand yuan from 2020 on.
    revenue = np.where(
        year <= YEAR_YUAN_LAST,
        np.round(revenue_wan * UNIT_FACTOR),
        np.round(revenue_wan, 2),
    )

    panel = pd.DataFrame(
        {"firm": firm, "year": year, "revenue": revenue, "roa": roa, "leverage": leverage}
    )
    return _inject_anomalies(panel)


def _inject_anomalies(panel: pd.DataFrame) -> pd.DataFrame:
    """Overwrite fixed cells with the failures the fixture is about."""
    dirty = panel.copy()
    for column, rows in MISSING_KEY_ROWS.items():
        dirty.loc[list(rows), column] = np.nan
    for column, rows in MISSING_NON_KEY_ROWS.items():
        dirty.loc[list(rows), column] = np.nan
    for column, values in OUTLIER_ROWS.items():
        for row, value in values.items():
            dirty.loc[row, column] = float(value)
    duplicates = dirty.iloc[list(DUPLICATE_ROWS)].copy()
    return pd.concat([dirty, duplicates], ignore_index=True)


# ---- small helpers --------------------------------------------------------
def md_table(headers, rows) -> str:
    """Render a Markdown table. No cell may contain a pipe."""
    out = ["| " + " | ".join(headers) + " |"]
    out.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(out)


def fmt_pct(count: int, total: int) -> str:
    return f"{100.0 * count / total:.2f}%"


def fmt_ratio(value: float) -> str:
    return f"{value:.4f}"


def fmt_amount(value: float) -> str:
    return f"{value:,.2f}"


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---- the six cleaning steps ----------------------------------------------
# ---- the six steps, one function each ------------------------------------
# `clean_panel` below runs them in order. `main` can run them one at a time with
# `--step N`, which stops after step N and says what step N+1 would do: that is
# the stepwise mode the stage-3 confirmation point in SKILL.md refers to.


def step_1_dedupe(kept, stats):
    """Remove exact duplicate rows."""
    deduped = kept.drop_duplicates().reset_index(drop=True)
    stats["dup_removed"] = len(kept) - len(deduped)
    stats["rows_after_dedup"] = len(deduped)
    return deduped


def step_2_missing(kept, stats):
    """Drop rows missing a key field. The rate is computed before any drop."""
    stats["missing"] = []
    for column in ("revenue", "roa", "leverage"):
        count = int(kept[column].isna().sum())
        stats["missing"].append((column, count, column in KEY_FIELDS))
    key_mask = kept["revenue"].isna() | kept["roa"].isna()
    stats["rows_dropped"] = int(key_mask.sum())
    kept = kept.loc[~key_mask].copy().reset_index(drop=True)
    stats["rows_after_missing"] = len(kept)
    return kept


def step_3_balance(kept, stats):
    """Report panel gaps. Nothing is filled in."""
    per_year = kept.groupby("year").size()
    balance = []
    for offset in range(N_YEAR):
        year = FIRST_YEAR + offset
        present = int(per_year.get(year, 0))
        balance.append((year, present, N_FIRM - present))
    stats["balance"] = balance
    stats["cells_present"] = len(kept)
    stats["cells_missing"] = BALANCED_CELLS - len(kept)
    return kept


def step_4_winsorize(kept, stats):
    """Winsorize the ratios. The level variable is not pooled in here because its
    unit is still mixed at this step; see step 5."""
    stats["winsor"] = []
    for column in WINSOR_FIELDS:
        series = kept[column]
        low = float(np.nanquantile(series.to_numpy(), WINSOR_LIMITS[0]))
        high = float(np.nanquantile(series.to_numpy(), WINSOR_LIMITS[1]))
        stats["winsor"].append(
            {
                "var": column,
                "min_before": float(np.nanmin(series)),
                "max_before": float(np.nanmax(series)),
                "clipped_low": int((series < low).sum()),
                "clipped_high": int((series > high).sum()),
                "min_after": float(np.nanmin(series.clip(lower=low, upper=high))),
                "max_after": float(np.nanmax(series.clip(lower=low, upper=high))),
            }
        )
        kept[column] = series.clip(lower=low, upper=high)
    return kept


def step_5_units(kept, stats):
    """Harmonise the unit in code, never in a spreadsheet cell."""
    early = kept["year"] <= YEAR_YUAN_LAST
    stats["rows_converted"] = int(early.sum())
    stats["mean_before"] = float(kept["revenue"].mean())
    kept["revenue_wan"] = np.where(early, kept["revenue"] / UNIT_FACTOR, kept["revenue"])
    stats["mean_after"] = float(kept["revenue_wan"].mean())
    stats["revenue_wan_min"] = float(kept["revenue_wan"].min())
    stats["revenue_wan_max"] = float(kept["revenue_wan"].max())
    kept = kept.drop(columns=["revenue"])
    return kept


def step_6_drift(kept, stats):
    """Flag the definition drift. Compare the codebook, do not assume stability."""
    stats["drift"] = [
        {"var": var, "kind": DRIFT_KIND[var], "periods": periods}
        for var, periods in DEFINITIONS.items()
        if len({period[2] for period in periods}) > 1
    ]
    kept["roa_vintage"] = np.where(kept["year"] <= YEAR_YUAN_LAST, 1, 2)
    stats["vintage"] = []
    for vintage in (1, 2):
        subset = kept.loc[kept["roa_vintage"] == vintage]
        first = int(subset["year"].min())
        last = int(subset["year"].max())
        stats["vintage"].append(
            (vintage, f"{first}-{last}", len(subset), float(subset["roa"].mean()))
        )
    return kept


CLEAN_STEPS = (
    (1, step_1_dedupe),
    (2, step_2_missing),
    (3, step_3_balance),
    (4, step_4_winsorize),
    (5, step_5_units),
    (6, step_6_drift),
)

CLEAN_LABEL = {
    1: {"en": "Drop exact duplicate rows", "zh": "删除完全重复的行"},
    2: {"en": "Drop rows missing a key field", "zh": "删掉关键字段缺失的行"},
    3: {"en": "Report panel gaps, fill nothing", "zh": "报告面板缺口，不插补"},
    4: {
        "en": "Winsorize the ratios at 1 and 99 percent",
        "zh": "对比率变量在 1 与 99 分位缩尾",
    },
    5: {"en": "Harmonise the unit in code", "zh": "在代码里统一单位"},
    6: {"en": "Flag the definition drift", "zh": "标注口径漂移"},
}

CLEAN_DEFAULT = {
    1: {
        "en": "keep the first copy, drop later copies",
        "zh": "保留首次出现，删后出现的副本",
    },
    2: {
        "en": "compute the missing rate first, then drop",
        "zh": "先算缺失率，再删",
    },
    3: {"en": "report only, never fill", "zh": "只报告，不插补"},
    4: {
        "en": "clip at the 1st and 99th percentile, keep the row",
        "zh": "在 1 与 99 分位截断，不删行",
    },
    5: {
        "en": "convert to ten-thousand yuan in a new column",
        "zh": "换算成万元并另存一列",
    },
    6: {
        "en": "add a vintage column, do not merge the definitions",
        "zh": "加一列版本号，不合并两套口径",
    },
}


def moved(index: int, stats) -> str:
    """How much step `index` touched, with the unit that makes the number mean something."""
    if index == 1:
        return "{0} rows".format(stats["dup_removed"])
    if index == 2:
        return "{0} rows".format(stats["rows_dropped"])
    if index == 3:
        return "{0} cells".format(stats["cells_missing"])
    if index == 4:
        values = sum(item["clipped_low"] + item["clipped_high"] for item in stats["winsor"])
        return "{0} values".format(values)
    if index == 5:
        return "{0} rows".format(stats["rows_converted"])
    return "{0} variables".format(len(stats["drift"]))


def moved_zh(index: int, stats) -> str:
    if index == 1:
        return "{0} 行".format(stats["dup_removed"])
    if index == 2:
        return "{0} 行".format(stats["rows_dropped"])
    if index == 3:
        return "{0} 格".format(stats["cells_missing"])
    if index == 4:
        values = sum(item["clipped_low"] + item["clipped_high"] for item in stats["winsor"])
        return "{0} 个值".format(values)
    if index == 5:
        return "{0} 行".format(stats["rows_converted"])
    return "{0} 个变量".format(len(stats["drift"]))


def moved_text(index: int, stats, lang: str) -> str:
    return moved_zh(index, stats) if lang == "zh" else moved(index, stats)


CLEAN_TEXT = {
    "en": {
        "dec_h1": "# Cleaning decisions",
        "dec_lead": (
            "Written before any row is touched. One row per action, in the order the "
            "script runs them. Fill `Your call`, and only then run `--step`."
        ),
        "dec_head": [
            "#",
            "Action",
            "Rows in",
            "Rows out",
            "What it touches",
            "Default",
            "Your call",
        ],
        "dec_tail": (
            "Run `python skills/data-prep/templates/clean_panel.py --step 1`, read the "
            "file it leaves, then `--step 2`, and so on. Each run stops and prints what "
            "the next step would do."
        ),
        "note_h1": "# Step {step} of 6: {label}",
        "note_does": "This step only does: {label}.",
        "note_rows": "Rows: {before} before, {after} after.",
        "note_out": "Produces: {path}",
        "note_next": "Next, not run yet: step {next_step}, {next_label}.",
        "note_stop": (
            "Stops and waits for you: run --step {next_step} only after you have looked "
            "at this file."
        ),
        "note_last": (
            "Last step. Run without --step to write the full log and the cleaned panel."
        ),
        "cli_next": "next, not run yet: step {next_step}, {next_label}",
        "cli_stop": "stopping here: run --step {next_step} once you have looked",
    },
    "zh": {
        "dec_h1": "# 清洗决策表",
        "dec_lead": (
            "在任何一行数据被改动之前写好。一个动作一行，顺序就是脚本的执行顺序。"
            "先把 `你的决定` 填上，再跑 `--step`。"
        ),
        "dec_head": [
            "#",
            "动作",
            "进多少行",
            "出多少行",
            "动了多少",
            "默认做法",
            "你的决定",
        ],
        "dec_tail": (
            "先跑 `python skills/data-prep/templates/clean_panel.py --step 1`，看它留下的文件，"
            "再跑 `--step 2`，依此类推。每次都停下来，并打印下一步会做什么。"
        ),
        "note_h1": "# 第 {step} 步，共 6 步：{label}",
        "note_does": "这一步只做：{label}。",
        "note_rows": "行数：做之前 {before} 行，做完 {after} 行。",
        "note_out": "产出：{path}",
        "note_next": "下一步还没跑：第 {next_step} 步，{next_label}。",
        "note_stop": "停下来等你：看过这个文件之后，再跑 --step {next_step}。",
        "note_last": "这是最后一步。不带 --step 跑一次，会写出完整的日志与清洗后的面板。",
        "cli_next": "下一步还没跑：第 {next_step} 步，{next_label}",
        "cli_stop": "停在这里：看过之后，再跑 --step {next_step}",
    },
}


def render_decisions(stats, lang: str) -> str:
    text = CLEAN_TEXT[lang]
    rows = ["| " + " | ".join(text["dec_head"]) + " |"]
    rows.append("|" + "---|" * len(text["dec_head"]))
    for index, before, after in stats["trace"]:
        rows.append(
            "| {0} | {1} | {2} | {3} | {4} | {5} |  |".format(
                index,
                CLEAN_LABEL[index][lang],
                before,
                after,
                moved_text(index, stats, lang),
                CLEAN_DEFAULT[index][lang],
            )
        )
    lines = [text["dec_h1"], "", text["dec_lead"], ""]
    lines.extend(rows)
    lines.extend(["", text["dec_tail"], ""])
    return "\n".join(lines)


def render_step_note(stats, step: int, lang: str, csv_path: str) -> str:
    text = CLEAN_TEXT[lang]
    trace = [item for item in stats["trace"] if item[0] == step][0]
    _, before, after = trace
    lines = [
        text["note_h1"].format(step=step, label=CLEAN_LABEL[step][lang]),
        "",
        text["note_does"].format(label=CLEAN_LABEL[step][lang]),
        text["note_rows"].format(before=before, after=after),
        text["note_out"].format(path=csv_path),
        "",
    ]
    if step < 6:
        lines.append(
            text["note_next"].format(
                next_step=step + 1, next_label=CLEAN_LABEL[step + 1][lang]
            )
        )
        lines.append(text["note_stop"].format(next_step=step + 1))
    else:
        lines.append(text["note_last"])
    lines.append("")
    return "\n".join(lines)


def clean_panel(dirty: pd.DataFrame, upto: int = 6):
    """Run the six steps, or the first `upto` of them, and return frame plus numbers."""
    stats = {"rows_generated": len(dirty), "trace": []}
    kept = dirty
    for index, step in CLEAN_STEPS:
        if index > upto:
            break
        before = len(kept)
        kept = step(kept, stats)
        stats["trace"].append((index, before, len(kept)))
    if upto < 6:
        return kept, stats

    cleaned = kept[["firm", "year", "revenue_wan", "roa", "leverage", "roa_vintage"]]
    cleaned = cleaned.sort_values(["firm", "year"]).reset_index(drop=True)
    for column in ("firm", "year", "roa_vintage"):
        cleaned[column] = cleaned[column].astype(int)
    stats["rows_clean"] = len(cleaned)
    stats["n_vars"] = len(cleaned.columns)
    return cleaned, stats


# ---- the log, in two languages -------------------------------------------
TEXT = {
    "en": {
        "h1": "# Cleaning log",
        "intro": (
            "This log is written by `templates/clean_panel.py`. The panel is synthetic and "
            "seeded, so every count below is exact and a rerun reproduces the file byte for "
            "byte; none of these numbers is an estimate from real data. The fixture carries "
            "the six failures this skill is about: duplicate records, missing key fields, an "
            "unbalanced panel, outliers, mixed units, and a definition that changes across "
            "years."
        ),
        "h_fixture": "## 1. Fixture",
        "fixture_lead": (
            "The generator builds a firm-year panel and then injects each failure at a fixed "
            "row position, so the size of every anomaly is known before cleaning starts."
        ),
        "th_item_value": ["Item", "Value"],
        "lbl_firms": "Firms",
        "lbl_years": "Years",
        "lbl_balanced_cells": "Balanced cells",
        "lbl_generator_rows": "Rows written by the generator",
        "lbl_seed": "Seed",
        "h_dedup": "## 2. Step 1: duplicates",
        "dedup_lead": (
            "A duplicate is removed on the full row: two rows that agree on every column are "
            "the same record, and the second copy carries no information. The count is logged "
            "instead of inspecting records one by one."
        ),
        "lbl_rows_before": "Rows before",
        "lbl_dup_removed": "Exact duplicate rows removed",
        "lbl_rows_after": "Rows after",
        "h_missing": "## 3. Step 2: missing values in key fields",
        "missing_lead": (
            "The missing rate is computed before any row is dropped. `revenue` and `roa` are "
            "key fields: a row missing either one is dropped and the count is logged. "
            "`leverage` is not a key field, so its gaps stay in the file and only the "
            "specification that uses it loses those rows."
        ),
        "th_missing": ["Variable", "Missing", "Rate", "Key field", "Rule"],
        "yes": "yes",
        "no": "no",
        "rule_drop": "drop the row",
        "rule_keep": "keep the row",
        "missing_after": (
            "{dropped} rows are dropped because the key-field gaps sit on disjoint rows: "
            "{rev} + {roa} = {dropped}. Rows remaining: {remaining}."
        ),
        "h_balance": "## 4. Step 3: panel balance",
        "balance_lead": (
            "{present} of the {cells} firm-year cells are present, so the panel is unbalanced. "
            "The response is not to interpolate the gaps and not to drop firms until the "
            "table looks rectangular: keep the gaps visible, report them in the sample-flow "
            "table, and let the estimator declare the imbalance."
        ),
        "th_balance": ["Year", "Cells present", "Cells missing"],
        "lbl_total": "Total",
        "h_winsor": "## 5. Step 4: winsorize",
        "winsor_lead": (
            "Winsorizing uses the 1st and 99th percentiles of each ratio variable. `revenue` "
            "is a level variable whose unit is still mixed at this step, so it is "
            "deliberately kept out of the pooled limits. Missing values are ignored when the "
            "percentiles are computed, and they are not filled with a winsor limit."
        ),
        "th_winsor": [
            "Variable",
            "Min before",
            "Max before",
            "Clipped low",
            "Clipped high",
            "Min after",
            "Max after",
        ],
        "h_units": "## 6. Step 5: unit harmonization",
        "units_lead": (
            "`revenue` is recorded in yuan for 2018-2019 and in ten-thousand yuan for "
            "2020-2023. The conversion runs in the script, never in a spreadsheet cell, and "
            "the harmonized column is renamed `revenue_wan` so that the unit travels with "
            "the variable name."
        ),
        "lbl_years_yuan": "Years reported in yuan",
        "lbl_rows_converted": "Rows converted",
        "lbl_factor": "Conversion factor",
        "lbl_mean_before": "Mean revenue before conversion",
        "lbl_mean_after": "Mean revenue after conversion",
        "units_after": (
            "A pooled mean computed before the conversion mixes two units and is not a "
            "quantity; that is why the conversion cannot be deferred to the estimation step."
        ),
        "h_drift": "## 7. Step 6: definition drift",
        "drift_lead": (
            "The codebook records what each variable meant in each period, and the script "
            "compares those records instead of assuming the variable is stable. The check "
            "finds {count} changes:"
        ),
        "warn": (
            "> WARNING: `{var}` is recorded differently across the period: {d1} in {a1}-{b1}, "
            "{d2} in {a2}-{b2}. {resolution}"
        ),
        "resolution_unit": (
            "Unit drift only: harmonized to ten-thousand yuan in step 5; the meaning of the "
            "variable itself does not change."
        ),
        "resolution_definition": (
            "The two periods are not directly comparable; rows are tagged and the template "
            "does not pool them."
        ),
        "th_drift": ["Variable", "Period", "Definition", "Status in the cleaned file"],
        "status_unit": "harmonized to ten-thousand yuan in step 5",
        "status_reference": "reference unit",
        "status_vintage_1": "tagged vintage 1",
        "status_vintage_2": "tagged vintage 2",
        "terms": {
            "yuan": "yuan",
            "ten_thousand_yuan": "ten-thousand yuan",
            "net_profit_assets": "net profit / total assets",
            "operating_profit_assets": "operating profit / total assets",
        },
        "drift_after": (
            "The cleaned file keeps all {rows} rows and tags each one with `roa_vintage`. The "
            "template does not choose a pooling rule: either split the sample at 2020 or add "
            "a vintage dummy, and record the choice in the paper's cleaning log."
        ),
        "drift_break_lead": "The break shows up in the tagged data before any regression:",
        "th_vintage": ["Vintage", "Years", "Observations", "Mean roa"],
        "h_outputs": "## 8. Outputs",
        "th_outputs": ["File", "Rows", "Columns"],
        "cols_lead": "Columns of `clean_panel.csv`:",
        "th_cols": ["Column", "Unit", "Note"],
        "unit_id": "identifier",
        "unit_year": "calendar year",
        "unit_wan": "ten-thousand yuan",
        "unit_ratio": "ratio",
        "unit_code": "code",
        "note_firm": "firm identifier, 1 to 40",
        "note_year": "2018-2023",
        "note_revenue": "harmonized in step 5",
        "note_roa": "two definitions, tagged in `roa_vintage`",
        "note_leverage": "winsorized at the 1st and 99th percentiles",
        "note_vintage": "1 = net profit definition, 2 = operating profit definition",
        "output_after": (
            "Rows are sorted by firm and year and floats are written with six decimals, so "
            "the file does not depend on row order or on the platform's default rounding. The "
            "three `leverage` gaps that step 2 keeps stay empty in the file; the column is "
            "not imputed."
        ),
        "h_repro": "## 9. Reproducibility",
        "repro_1": (
            "- No timestamp, no absolute path, and no unseeded draw enters the output, so two "
            "runs produce the same bytes."
        ),
        "repro_2": (
            "- The checksums are written into this log: `clean_panel.csv` sha256 `{csv_sha}`, "
            "`clean_panel_summary.csv` sha256 `{summary_sha}`."
        ),
        "repro_3": (
            "- The golden copy in `skills/data-prep/expected/` holds the output of the same "
            "command; a diff against it is the regression test for the pipeline: run "
            "`python skills/data-prep/templates/clean_panel.py --lang en` from the repository "
            "root and compare `output/cleaning-log.md` with the golden file."
        ),
    },
    "zh": {
        "h1": "# 清洗日志",
        "intro": (
            "本日志由 `templates/clean_panel.py` 生成。面板是合成数据、固定随机种子，因此下面每个"
            "计数都是精确值，重跑一遍得到逐字节相同的文件；这些数字不是真实数据的估计结果。"
            "样例里预先埋了本 skill 关心的六类问题：重复记录、关键字段缺失、非平衡面板、极端值、"
            "单位混用，以及跨年变化的口径。"
        ),
        "h_fixture": "## 1. 测试数据",
        "fixture_lead": (
            "生成器先造一个企业—年份面板，再在固定行位置上把每一类问题注入进去，所以清洗开始"
            "之前，每个异常的数量就是已知的。"
        ),
        "th_item_value": ["项目", "取值"],
        "lbl_firms": "企业数",
        "lbl_years": "年份",
        "lbl_balanced_cells": "平衡格数",
        "lbl_generator_rows": "生成器写入行数",
        "lbl_seed": "随机种子",
        "h_dedup": "## 2. 第 1 步：去重",
        "dedup_lead": (
            "重复记录按整行判定：所有列都相同的两行是同一条记录，后一份不携带任何信息。"
            "这里只记数量，不逐条判断。"
        ),
        "lbl_rows_before": "去重前行数",
        "lbl_dup_removed": "删除的完全重复行",
        "lbl_rows_after": "去重后行数",
        "h_missing": "## 3. 第 2 步：关键字段缺失",
        "missing_lead": (
            "先算缺失率，再决定删不删。`revenue` 与 `roa` 是关键字段：缺任意一个就删掉整行，"
            "并把数量记下来。`leverage` 不是关键字段，它的缺口留在文件里，只有用到它的那一个"
            "设定会因此少掉这几行。"
        ),
        "th_missing": ["变量", "缺失数", "缺失率", "关键字段", "处理"],
        "yes": "是",
        "no": "否",
        "rule_drop": "删整行",
        "rule_keep": "保留整行",
        "missing_after": (
            "关键字段的缺口落在互不相同的行上，因此共删 {dropped} 行：{rev} + {roa} = "
            "{dropped}。剩余行数：{remaining}。"
        ),
        "h_balance": "## 4. 第 3 步：面板平衡性",
        "balance_lead": (
            "{cells} 个企业—年份格子里，有观测的只有 {present} 个，面板因此非平衡。正确的做法"
            "不是把缺口插值补齐，也不是删掉企业直到表面平衡：让缺口保持可见、写进样本流程表，"
            "并让估计环节明确声明面板非平衡。"
        ),
        "th_balance": ["年份", "有观测的格子", "缺失格子"],
        "lbl_total": "合计",
        "h_winsor": "## 5. 第 4 步：缩尾",
        "winsor_lead": (
            "缩尾用每个比率变量自身的 1% 与 99% 分位数。`revenue` 是水平变量，且在这一步它的"
            "单位还是混的，所以故意不把它的分位数混进来。计算分位数时忽略缺失值，也不拿缩尾"
            "阈值去填补缺失值。"
        ),
        "th_winsor": [
            "变量",
            "缩尾前最小值",
            "缩尾前最大值",
            "低端截断数",
            "高端截断数",
            "缩尾后最小值",
            "缩尾后最大值",
        ],
        "h_units": "## 6. 第 5 步：单位统一",
        "units_lead": (
            "`revenue` 在 2018-2019 年以元记录，2020-2023 年以万元记录。换算在脚本里做，"
            "绝不在表格单元格里做，并把统一后的列改名为 `revenue_wan`，让单位跟着变量名一起走。"
        ),
        "lbl_years_yuan": "以元记录的年份",
        "lbl_rows_converted": "换算行数",
        "lbl_factor": "换算系数",
        "lbl_mean_before": "换算前 revenue 均值",
        "lbl_mean_after": "换算后 revenue 均值",
        "units_after": (
            "换算之前算出来的合并均值把两种单位混在一起，不是一个有意义的量；这就是为什么"
            "换算不能推到估计那一步再做。"
        ),
        "h_drift": "## 7. 第 6 步：口径漂移",
        "drift_lead": (
            "码本逐年记录每个变量当时的含义，脚本比较这些记录，而不是默认变量是稳定的。"
            "共发现 {count} 处变化："
        ),
        "warn": (
            "> 警告：`{var}` 在样本期内记录方式不同：{a1}-{b1} 年为{d1}，{a2}-{b2} 年为{d2}。"
            "{resolution}"
        ),
        "resolution_unit": "仅为单位差异：已在第 5 步统一为万元，变量本身的含义没有变化。",
        "resolution_definition": "两段不可直接比较；相关行已打标，模板不替作者合并口径。",
        "th_drift": ["变量", "期间", "口径", "清洗后文件里的处理"],
        "status_unit": "第 5 步已统一为万元",
        "status_reference": "基准单位",
        "status_vintage_1": "标记 vintage 1",
        "status_vintage_2": "标记 vintage 2",
        "terms": {
            "yuan": "元",
            "ten_thousand_yuan": "万元",
            "net_profit_assets": "净利润/总资产",
            "operating_profit_assets": "营业利润/总资产",
        },
        "drift_after": (
            "清洗后的文件保留全部 {rows} 行，并给每一行打上 `roa_vintage` 标记。模板不替作者"
            "决定合并口径：要么在 2020 年拆样本，要么加一个 vintage 虚拟变量，并把选择写进"
            "论文的清洗日志。"
        ),
        "drift_break_lead": "在跑任何回归之前，这个断点在打标的数据里就能看到：",
        "th_vintage": ["Vintage", "年份", "观测数", "roa 均值"],
        "h_outputs": "## 8. 产出",
        "th_outputs": ["文件", "行数", "列数"],
        "cols_lead": "`clean_panel.csv` 的列：",
        "th_cols": ["列", "单位", "说明"],
        "unit_id": "标识",
        "unit_year": "年份",
        "unit_wan": "万元",
        "unit_ratio": "比率",
        "unit_code": "代码",
        "note_firm": "企业标识，1 到 40",
        "note_year": "2018-2023",
        "note_revenue": "第 5 步统一后的单位",
        "note_roa": "两套口径，由 `roa_vintage` 标记",
        "note_leverage": "在 1% 与 99% 处缩尾",
        "note_vintage": "1 = 净利润口径，2 = 营业利润口径",
        "output_after": (
            "行按企业与年份排序，浮点数固定写六位小数，因此文件既不依赖行序，也不依赖平台的"
            "默认舍入。第 2 步留下的三个 `leverage` 缺口在文件里保持为空，不做插补。"
        ),
        "h_repro": "## 9. 可复现性",
        "repro_1": (
            "- 产出里没有时间戳、没有绝对路径、没有未设种子的随机抽样，所以跑两遍得到相同的"
            "字节。"
        ),
        "repro_2": (
            "- 校验值写在本日志里：`clean_panel.csv` 的 sha256 为 `{csv_sha}`，"
            "`clean_panel_summary.csv` 的 sha256 为 `{summary_sha}`。"
        ),
        "repro_3": (
            "- `skills/data-prep/expected/` 下放的是同一条命令的金样；与它比对就是这条清洗"
            "流水线的回归测试：在仓库根目录跑 "
            "`python skills/data-prep/templates/clean_panel.py --lang zh`，再把 "
            "`output/cleaning-log.md` 与金样逐行比对。"
        ),
    },
}


def summary_rows(stats) -> list:
    """Deterministic summary: metric, value. Language-neutral by design."""
    rows = [
        ("rows_after_cleaning", str(stats["rows_clean"])),
        ("variables_in_output", str(stats["n_vars"])),
        ("rows_written_by_generator", str(stats["rows_generated"])),
        ("duplicate_rows_removed", str(stats["dup_removed"])),
        ("rows_after_dedup", str(stats["rows_after_dedup"])),
        ("rows_dropped_missing_key", str(stats["rows_dropped"])),
        ("panel_cells_expected", str(BALANCED_CELLS)),
        ("panel_cells_present", str(stats["cells_present"])),
        ("winsor_low_percentile", str(WINSOR_PERCENTILES[0])),
        ("winsor_high_percentile", str(WINSOR_PERCENTILES[1])),
    ]
    for item in stats["winsor"]:
        var = item["var"]
        rows.extend(
            [
                (f"{var}_min_before_winsor", f"{item['min_before']:.6f}"),
                (f"{var}_max_before_winsor", f"{item['max_before']:.6f}"),
                (f"{var}_clipped_low", str(item["clipped_low"])),
                (f"{var}_clipped_high", str(item["clipped_high"])),
                (f"{var}_min_after_winsor", f"{item['min_after']:.6f}"),
                (f"{var}_max_after_winsor", f"{item['max_after']:.6f}"),
            ]
        )
    rows.extend(
        [
            ("revenue_wan_min", f"{stats['revenue_wan_min']:.6f}"),
            ("revenue_wan_max", f"{stats['revenue_wan_max']:.6f}"),
        ]
    )
    return rows


def render_log(stats, metric_count: int, csv_sha: str, summary_sha: str, lang: str) -> str:
    t = TEXT[lang]
    terms = t["terms"]
    lines = []

    def add(*items):
        lines.extend(items)

    add(t["h1"], "")
    add(t["intro"], "")

    add(t["h_fixture"], "")
    add(t["fixture_lead"], "")
    add(
        md_table(
            t["th_item_value"],
            [
                [t["lbl_firms"], str(N_FIRM)],
                [t["lbl_years"], f"{FIRST_YEAR}-{FIRST_YEAR + N_YEAR - 1}"],
                [t["lbl_balanced_cells"], str(BALANCED_CELLS)],
                [t["lbl_generator_rows"], str(stats["rows_generated"])],
                [t["lbl_seed"], str(SEED)],
            ],
        ),
        "",
    )

    add(t["h_dedup"], "")
    add(t["dedup_lead"], "")
    add(
        md_table(
            t["th_item_value"],
            [
                [t["lbl_rows_before"], str(stats["rows_generated"])],
                [t["lbl_dup_removed"], str(stats["dup_removed"])],
                [t["lbl_rows_after"], str(stats["rows_after_dedup"])],
            ],
        ),
        "",
    )

    add(t["h_missing"], "")
    add(t["missing_lead"], "")
    missing_rows = []
    for variable, count, is_key in stats["missing"]:
        missing_rows.append(
            [
                variable,
                str(count),
                fmt_pct(count, stats["rows_after_dedup"]),
                t["yes"] if is_key else t["no"],
                t["rule_drop"] if is_key else t["rule_keep"],
            ]
        )
    add(md_table(t["th_missing"], missing_rows), "")
    add(
        t["missing_after"].format(
            dropped=stats["rows_dropped"],
            rev=dict((v, c) for v, c, _ in stats["missing"])["revenue"],
            roa=dict((v, c) for v, c, _ in stats["missing"])["roa"],
            remaining=stats["rows_after_missing"],
        ),
        "",
    )

    add(t["h_balance"], "")
    add(
        t["balance_lead"].format(
            present=stats["cells_present"], cells=BALANCED_CELLS
        ),
        "",
    )
    balance_rows = [
        [str(year), str(present), str(missing)]
        for year, present, missing in stats["balance"]
    ]
    balance_rows.append([t["lbl_total"], str(stats["cells_present"]), str(stats["cells_missing"])])
    add(md_table(t["th_balance"], balance_rows), "")

    add(t["h_winsor"], "")
    add(t["winsor_lead"], "")
    winsor_rows = [
        [
            item["var"],
            fmt_ratio(item["min_before"]),
            fmt_ratio(item["max_before"]),
            str(item["clipped_low"]),
            str(item["clipped_high"]),
            fmt_ratio(item["min_after"]),
            fmt_ratio(item["max_after"]),
        ]
        for item in stats["winsor"]
    ]
    add(md_table(t["th_winsor"], winsor_rows), "")

    add(t["h_units"], "")
    add(t["units_lead"], "")
    add(
        md_table(
            t["th_item_value"],
            [
                [
                    t["lbl_years_yuan"],
                    f"{FIRST_YEAR}-{YEAR_YUAN_LAST}",
                ],
                [t["lbl_rows_converted"], str(stats["rows_converted"])],
                [t["lbl_factor"], f"{int(UNIT_FACTOR)}"],
                [t["lbl_mean_before"], fmt_amount(stats["mean_before"])],
                [t["lbl_mean_after"], fmt_amount(stats["mean_after"])],
            ],
        ),
        "",
    )
    add(t["units_after"], "")

    add(t["h_drift"], "")
    add(t["drift_lead"].format(count=len(stats["drift"])), "")
    for item in stats["drift"]:
        first, second = item["periods"]
        add(
            t["warn"].format(
                var=item["var"],
                a1=first[0],
                b1=first[1],
                d1=terms[first[2]],
                a2=second[0],
                b2=second[1],
                d2=terms[second[2]],
                resolution=t["resolution_unit"]
                if item["kind"] == "unit"
                else t["resolution_definition"],
            ),
            "",
        )
    drift_rows = []
    for item in stats["drift"]:
        for first, second in (item["periods"],):
            for period in (first, second):
                drift_rows.append(
                    [
                        item["var"],
                        f"{period[0]}-{period[1]}",
                        terms[period[2]],
                        t[period[3]],
                    ]
                )
    add(md_table(t["th_drift"], drift_rows), "")
    add(t["drift_after"].format(rows=stats["rows_clean"]), "")
    add(t["drift_break_lead"], "")
    add(
        md_table(
            t["th_vintage"],
            [
                [str(vintage), years, str(nobs), fmt_ratio(mean)]
                for vintage, years, nobs, mean in stats["vintage"]
            ],
        ),
        "",
    )

    add(t["h_outputs"], "")
    add(
        md_table(
            t["th_outputs"],
            [
                ["clean_panel.csv", str(stats["rows_clean"]), str(stats["n_vars"])],
                ["clean_panel_summary.csv", str(metric_count), "2"],
            ],
        ),
        "",
    )
    add(t["cols_lead"], "")
    add(
        md_table(
            t["th_cols"],
            [
                ["firm", t["unit_id"], t["note_firm"]],
                ["year", t["unit_year"], t["note_year"]],
                ["revenue_wan", t["unit_wan"], t["note_revenue"]],
                ["roa", t["unit_ratio"], t["note_roa"]],
                ["leverage", t["unit_ratio"], t["note_leverage"]],
                ["roa_vintage", t["unit_code"], t["note_vintage"]],
            ],
        ),
        "",
    )
    add(t["output_after"], "")

    add(t["h_repro"], "")
    add(t["repro_1"])
    add(t["repro_2"].format(csv_sha=csv_sha, summary_sha=summary_sha))
    add(t["repro_3"], "")

    return "\n".join(lines).rstrip("\n") + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=("en", "zh"), default="en")
    parser.add_argument("--out-dir", default="output")
    parser.add_argument(
        "--decisions",
        action="store_true",
        help="write the cleaning decision table and stop; no data file is written",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=0,
        metavar="N",
        help="run only the first N of the six steps, then stop (1 to 6)",
    )
    args = parser.parse_args()

    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    dirty = make_dirty_panel()

    if args.decisions:
        _, stats = clean_panel(dirty)
        path = os.path.join(out_dir, "cleaning-decisions.md")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(render_decisions(stats, args.lang))
        print(f"wrote {path} ({len(stats['trace'])} actions, no data file written)")
        return 0

    if args.step:
        if not 1 <= args.step <= 6:
            print("--step takes a number from 1 to 6", file=sys.stderr)
            return 2
        kept, stats = clean_panel(dirty, upto=args.step)
        csv_path = os.path.join(out_dir, "clean_panel_step{0}.csv".format(args.step))
        kept.to_csv(
            csv_path, index=False, float_format="%.6f", lineterminator="\n", na_rep=""
        )
        note_path = os.path.join(out_dir, "cleaning-step{0}.md".format(args.step))
        with open(note_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(render_step_note(stats, args.step, args.lang, csv_path))
        print(f"wrote {csv_path} ({len(kept)} rows)")
        print(f"wrote {note_path}")
        if args.step < 6:
            text = CLEAN_TEXT[args.lang]
            print(
                text["cli_next"].format(
                    next_step=args.step + 1,
                    next_label=CLEAN_LABEL[args.step + 1][args.lang],
                )
            )
            print(text["cli_stop"].format(next_step=args.step + 1))
        return 0

    cleaned, stats = clean_panel(dirty)

    csv_path = os.path.join(out_dir, "clean_panel.csv")
    cleaned.to_csv(
        csv_path, index=False, float_format="%.6f", lineterminator="\n", na_rep=""
    )

    metrics = summary_rows(stats)
    summary_path = os.path.join(out_dir, "clean_panel_summary.csv")
    with open(summary_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("metric,value\n")
        for metric, value in metrics:
            handle.write(f"{metric},{value}\n")

    log_path = os.path.join(out_dir, "cleaning-log.md")
    log = render_log(
        stats, len(metrics), sha256_of(csv_path), sha256_of(summary_path), args.lang
    )
    with open(log_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(log)

    print(f"wrote {csv_path} ({stats['rows_clean']} rows, {stats['n_vars']} columns)")
    print(f"wrote {summary_path} ({len(metrics)} metrics)")
    print(f"wrote {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
