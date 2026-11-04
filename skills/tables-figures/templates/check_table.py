#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check one LaTeX table against the seven mechanical rules of stage 5.

Usage:
    python skills/tables-figures/templates/check_table.py output/table1.tex --lang en
    python skills/tables-figures/templates/check_table.py output/table1.tex --lang zh

Exit code: 0 when all seven checks pass, 1 when any check is not OK, 2 on a
usage error.

What it does not do: it cannot tell whether the numbers are right. It checks
the shape of the table — the things that regularly break when a table is
rebuilt or copied by hand.
"""

from __future__ import annotations

import argparse
import io
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

TEXT = {
    "en": {
        "title": "check_table — seven mechanical rules for one LaTeX table",
        "file": "file",
        "ok": "OK",
        "weak": "WEAK",
        "missing": "MISSING",
        "passed": "{n}/7 checks passed",
        "note": "note",
        "checks": [
            "caption before the tabular",
            "booktabs rules and no \\hline",
            "no vertical bars in the column specification",
            "the same number of columns in every content row",
            "standard errors in parentheses directly below their coefficient",
            "note below the table that defines the stars and names the clustering",
            "a \\label so the table can be cited by number",
        ],
        "detail_caption": "caption found before the tabular",
        "detail_caption_bad": "no \\caption before \\begin{tabular}",
        "detail_booktabs": "toprule / midrule / bottomrule found",
        "detail_booktabs_bad": "missing one of toprule, midrule, bottomrule",
        "detail_hline": "\\hline still present (old-style rule)",
        "detail_vbars": "no vertical bar in the column specification",
        "detail_vbars_bad": "vertical bar in the column specification: {spec}",
        "detail_cols": "{n} columns in every content row",
        "detail_cols_bad": "row {row} has {got} columns, expected {want}",
        "detail_se": "{n} coefficient rows followed by a parenthesised standard error",
        "detail_se_bad": "no row of parenthesised standard errors under a coefficient",
        "detail_note": "note defines the stars and names the clustering",
        "detail_note_missing": "no note after the tabular",
        "detail_note_stars": "note does not define *** ** *",
        "detail_note_cluster": "note does not name the clustering level",
        "detail_label": "label {label}",
        "detail_label_bad": "no \\label{...}",
    },
    "zh": {
        "title": "check_table —— 一张 LaTeX 表的七项机检",
        "file": "文件",
        "ok": "OK",
        "weak": "WEAK",
        "missing": "MISSING",
        "passed": "{n}/7 项通过",
        "note": "备注",
        "checks": [
            "表题在表格之前",
            "有 booktabs 三线且没有 \\hline",
            "列定义里没有竖线",
            "每个内容行的列数一致",
            "标准误在括号里、紧跟系数下一行",
            "表注在表下方、定义了星号并写明聚类层级",
            "有 \\label，能被按编号引用",
        ],
        "detail_caption": "表题在 tabular 之前",
        "detail_caption_bad": "\\begin{tabular} 前没有 \\caption",
        "detail_booktabs": "toprule / midrule / bottomrule 齐全",
        "detail_booktabs_bad": "toprule、midrule、bottomrule 缺一个",
        "detail_hline": "仍有 \\hline（老式横线）",
        "detail_vbars": "列定义里没有竖线",
        "detail_vbars_bad": "列定义里有竖线：{spec}",
        "detail_cols": "每个内容行都是 {n} 列",
        "detail_cols_bad": "第 {row} 行有 {got} 列，应为 {want}",
        "detail_se": "{n} 处系数下一行紧跟括号标准误",
        "detail_se_bad": "没有「系数行 + 下一行括号标准误」的配对",
        "detail_note": "表注定义了星号并写明聚类层级",
        "detail_note_missing": "tabular 之后没有表注",
        "detail_note_stars": "表注没有定义 *** ** *",
        "detail_note_cluster": "表注没有写明聚类层级",
        "detail_label": "标签 {label}",
        "detail_label_bad": "没有 \\label{...}",
    },
}

TABULAR = re.compile(r"\\begin\{tabular\}\s*(\{[^}]*\})?")
NUMBER_ROW = re.compile(r"^[^%]*&[^&]*?(?<![\d.])-?\d+\.\d\d\d\*{0,3}")
PAREN_ROW = re.compile(r"^[^%]*&\s*\(\s*-?\d+\.\d+\s*\)")
CLUSTER_WORDS = ("cluster", "clustered", "聚类")
STAR_DEF = ("***", "**", "*")


def read_text(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def strip_comments(text):
    return "\n".join(line.split("%")[0] if line.lstrip().startswith("%") else line for line in text.splitlines())


def split_rows(text):
    body = []
    in_tab = False
    for line in text.splitlines():
        low = line.strip()
        if low.startswith("\\begin{tabular}"):
            in_tab = True
            continue
        if low.startswith("\\end{tabular}"):
            in_tab = False
            continue
        if in_tab:
            body.append(line)
    return body


def content_cells(row):
    """Number of cells in a content row, or None for a structural row."""
    low = row.strip()
    if not low or low.startswith("\\") or low.startswith("%"):
        return None
    return len([c for c in low.split("&")])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check one LaTeX table against seven mechanical rules.")
    parser.add_argument("path", help="path to the .tex file holding one table")
    parser.add_argument("--lang", choices=("en", "zh"), default="zh", help="language of the report")
    args = parser.parse_args(argv)

    tx = TEXT[args.lang]
    try:
        raw = read_text(args.path)
    except OSError as exc:
        sys.stderr.write("cannot read %s: %s\n" % (args.path, exc))
        return 2

    text = strip_comments(raw)
    rows = split_rows(text)
    results = []

    # 1 caption before tabular
    cap = text.find("\\caption")
    tab = text.find("\\begin{tabular}")
    ok = cap != -1 and tab != -1 and cap < tab
    results.append((ok, ok, tx["detail_caption"] if ok else tx["detail_caption_bad"]))

    # 2 booktabs, no hline
    have = all(k in text for k in ("\\toprule", "\\midrule", "\\bottomrule"))
    if not have:
        results.append((False, True, tx["detail_booktabs_bad"]))
    elif "\\hline" in text:
        results.append((False, True, tx["detail_hline"]))
    else:
        results.append((True, True, tx["detail_booktabs"]))

    # 3 no vertical bars
    m = TABULAR.search(text)
    spec = m.group(1) if m and m.group(1) else ""
    if "|" in spec:
        results.append((False, True, tx["detail_vbars_bad"].format(spec=spec)))
    else:
        results.append((True, True, tx["detail_vbars"]))

    # 4 column count
    counts = [(i, content_cells(r)) for i, r in enumerate(rows)]
    counts = [(i, c) for i, c in counts if c is not None]
    if not counts:
        results.append((False, True, tx["detail_cols_bad"].format(row="?", got=0, want=0)))
    else:
        want = counts[0][1]
        bad = [(i, c) for i, c in counts if c != want]
        if bad:
            results.append((False, True, tx["detail_cols_bad"].format(row=bad[0][0] + 1, got=bad[0][1], want=want)))
        else:
            results.append((True, True, tx["detail_cols"].format(n=want)))

    # 5 standard errors in parentheses under their coefficient
    pairs = 0
    for i, row in enumerate(rows[:-1]):
        if NUMBER_ROW.match(row.strip()) and PAREN_ROW.match(rows[i + 1].strip()):
            pairs += 1
    if pairs:
        results.append((True, True, tx["detail_se"].format(n=pairs)))
    else:
        results.append((False, True, tx["detail_se_bad"]))

    # 6 note below the table
    end = text.find("\\end{tabular}")
    after = text[end:] if end != -1 else ""
    note = re.search(r"(?:Note|Notes|注)\s*[:：]?\s*(.+)", after)
    if not note:
        results.append((False, True, tx["detail_note_missing"]))
    else:
        note_text = note.group(1)
        stars = all(s in note_text for s in STAR_DEF)
        cluster = any(w in note_text.lower() for w in CLUSTER_WORDS)
        if not stars:
            results.append((False, True, tx["detail_note_stars"]))
        elif not cluster:
            results.append((False, True, tx["detail_note_cluster"]))
        else:
            results.append((True, True, tx["detail_note"]))

    # 7 label
    lab = re.search(r"\\label\{([^}]+)\}", text)
    if lab:
        results.append((True, True, tx["detail_label"].format(label=lab.group(1))))
    else:
        results.append((False, True, tx["detail_label_bad"]))

    print(tx["title"])
    print("%s: %s" % (tx["file"], args.path))
    print()
    passed = 0
    for i, (ok, weak, detail) in enumerate(results, 1):
        mark = tx["ok"] if ok else (tx["weak"] if weak else tx["missing"])
        if ok:
            passed += 1
        print("[%s] %d/7 %s: %s" % (mark, i, tx["checks"][i - 1], detail))
    print(tx["passed"].format(n=passed))
    return 0 if passed == 7 else 1


if __name__ == "__main__":
    raise SystemExit(main())
