#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check one reproducible report against the seven mechanical rules of stage 6.

Usage:
    python skills/report/templates/check_report.py output/report.md --lang en
    python skills/report/templates/check_report.py output/report.md --lang zh

Exit code: 0 when all seven checks pass, 1 when any check is not OK, 2 on a
usage error.

What it does not do: it cannot tell whether a number is right, or whether the
prose explains anything. It checks the six required sections and the facts a
reader needs in order to rerun the thing.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

TEXT = {
    "en": {
        "title": "check_report — seven mechanical rules for one report",
        "file": "file",
        "ok": "OK",
        "weak": "WEAK",
        "missing": "MISSING",
        "passed": "{n}/{total} checks passed",
        "note": "{n} placeholder(s) still to fill",
        "checks": [
            "the six required sections are all present",
            "the one-line conclusion carries a coefficient and a standard error",
            "the main results section embeds one complete table",
            "robustness lists at least two alternatives, each with numbers",
            "data and definitions lists at least three fields",
            "reproduction names a seed and the input files",
            "what is still missing lists at least one item",
            "every decimal in the prose appears in the results file",
        ],
        "d_sections": "six sections found",
        "d_sections_bad": "missing section(s): {names}",
        "d_conclusion": "coefficient and standard error both given",
        "d_conclusion_bad": "the conclusion gives {what} only",
        "d_table": "one complete table embedded",
        "d_table_open": "a table starts but never closes",
        "d_table_bad": "no table embedded",
        "d_robust": "{n} alternatives each with numbers",
        "d_robust_bad": "only {n} alternative(s) with numbers",
        "d_data": "{n} fields listed",
        "d_data_bad": "no fields listed under data and definitions",
        "d_repro": "seed and input files recorded",
        "d_repro_seed": "no seed recorded",
        "d_repro_inputs": "no input file recorded",
        "d_missing": "{n} open items",
        "d_missing_bad": "no open items listed",
        "d_numbers": "{n} numbers matched",
        "d_numbers_bad": "{m} of {n} numbers are not in the results file: {items}",
        "d_no_numbers": "the prose carries no decimal, so there is nothing to reconcile",
        "None": "nothing",
        "coef": "a coefficient",
        "se": "a standard error",
    },
    "zh": {
        "title": "check_report —— 一份可复现报告的七项机检",
        "file": "文件",
        "ok": "OK",
        "weak": "WEAK",
        "missing": "MISSING",
        "passed": "{n}/{total} 项通过",
        "note": "{n} 处占位待填",
        "checks": [
            "六个必需小节齐全",
            "一句话结论里给了系数与标准误",
            "主结果小节嵌入了一张完整的表",
            "稳健性至少两条、每条都带数值",
            "数据与口径至少列出三个字段",
            "复现方式写明种子与输入文件",
            "还缺什么至少写了一条",
            "正文里每个小数都能在结果文件里找到",
        ],
        "d_sections": "六个小节都在",
        "d_sections_bad": "缺这几节：{names}",
        "d_conclusion": "系数与标准误都给了",
        "d_conclusion_bad": "结论里只给了{what}",
        "d_table": "嵌入了一张完整的表",
        "d_table_open": "有表开头但没有表结尾",
        "d_table_bad": "没有嵌入表",
        "d_robust": "{n} 条替代设定，每条带数值",
        "d_robust_bad": "只有 {n} 条带数值的替代设定",
        "d_data": "列出 {n} 个字段",
        "d_data_bad": "数据与口径小节没有列字段",
        "d_repro": "种子与输入文件都写了",
        "d_repro_seed": "没有写随机种子",
        "d_repro_inputs": "没有写输入文件",
        "d_missing": "{n} 条待办",
        "d_missing_bad": "没有列待办",
        "d_numbers": "{n} 个数字都找到了",
        "d_numbers_bad": "{n} 个数字里有 {m} 个在结果文件里找不到：{items}",
        "d_no_numbers": "正文没有小数，没有可对账的数字",
        "None": "任何一项",
        "coef": "系数",
        "se": "标准误",
    },
}

SECTIONS = [
    ("conclusion", ("one-line conclusion", "一句话结论")),
    ("main", ("main results", "主结果")),
    ("robust", ("robustness", "稳健性")),
    ("data", ("data and definitions", "数据与口径")),
    ("repro", ("how to reproduce", "复现方式")),
    ("missing", ("what is still missing", "还缺什么")),
]

PLACEHOLDER = re.compile(r"\[(?:to fill|待填|待核实|verify)\]")
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
DECIMAL = re.compile(r"\d+\.\d{2,}")
NUM = re.compile(r"\d+\.\d{2,}")
SE_WORDS = ("standard error", "标准误")


def read_text(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def split_sections(text):
    out = {}
    current = None
    buffer = []
    for line in text.splitlines():
        m = re.match(r"^(##)\s+(.*)$", line)
        if m:
            if current is not None:
                out[current] = "\n".join(buffer)
            current = m.group(2).strip()
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    if current is not None:
        out[current] = "\n".join(buffer)
    return out


def pick(sections, aliases):
    for name, body in sections.items():
        low = name.lower()
        for alias in aliases:
            if alias in low:
                return body
    return None


def bullets(body):
    return [line for line in body.splitlines() if line.strip().startswith(("- ", "* "))]


def strip_fences(text):
    """Drop fenced code blocks so that table digits are not reconciled."""
    return FENCE.sub("", text)


def gather_numbers(path):
    """Every real number found anywhere in the JSON, as floats."""
    import json

    with io.open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = []

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, bool):
            return
        elif isinstance(node, (int, float)):
            out.append(float(node))

    walk(data)
    return out


def check_numbers(report_text, values):
    """Return (matched, missing) for every decimal in the prose."""
    prose = strip_fences(report_text)
    tokens = DECIMAL.findall(prose)
    formatted = {}
    for v in values:
        for p in range(2, 7):
            formatted.setdefault("%.*f" % (p, v), v)
    matched, missing = 0, []
    for tok in tokens:
        if tok in formatted:
            matched += 1
        elif tok not in missing:
            missing.append(tok)
    return len(tokens), matched, missing


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check one report against seven mechanical rules.")
    parser.add_argument("path", help="path to the report in Markdown")
    parser.add_argument("--lang", choices=("en", "zh"), default="zh", help="language of the report and of the output")
    parser.add_argument("--results", default=None,
                        help="optional results JSON; when given, an eighth check reconciles every decimal in the prose against it")
    args = parser.parse_args(argv)

    tx = TEXT[args.lang]
    try:
        text = read_text(args.path)
    except OSError as exc:
        sys.stderr.write("cannot read %s: %s\n" % (args.path, exc))
        return 2

    sections = split_sections(text)
    results = []

    # 1 six sections
    missing = [key for key, aliases in SECTIONS if pick(sections, aliases) is None]
    if missing:
        names = ", ".join(key for key in missing)
        results.append((False, True, tx["d_sections_bad"].format(names=names)))
    else:
        results.append((True, True, tx["d_sections"]))

    # 2 conclusion carries coefficient and standard error
    body = pick(sections, ("one-line conclusion", "一句话结论")) or ""
    has_num = bool(NUM.search(body))
    has_se = any(w in body.lower() for w in SE_WORDS)
    if has_num and has_se:
        results.append((True, True, tx["d_conclusion"]))
    else:
        what = tx["None"]
        if has_num:
            what = tx["se"]
        elif has_se:
            what = tx["coef"]
        results.append((False, True, tx["d_conclusion_bad"].format(what=what)))

    # 3 a complete table embedded
    opens = text.count("\\begin{table}")
    closes = text.count("\\end{table}")
    if opens >= 1 and closes >= 1:
        results.append((True, True, tx["d_table"]))
    elif opens >= 1:
        results.append((False, True, tx["d_table_open"]))
    else:
        results.append((False, True, tx["d_table_bad"]))

    # 4 robustness lists alternatives with numbers
    body = pick(sections, ("robustness", "稳健性")) or ""
    with_numbers = [b for b in bullets(body) if NUM.search(b)]
    if len(with_numbers) >= 2:
        results.append((True, True, tx["d_robust"].format(n=len(with_numbers))))
    else:
        results.append((False, True, tx["d_robust_bad"].format(n=len(with_numbers))))

    # 5 data and definitions lists fields
    body = pick(sections, ("data and definitions", "数据与口径")) or ""
    fields = bullets(body) or [l for l in body.splitlines() if ":" in l or "：" in l]
    fields = [f for f in fields if f.strip()]
    if len(fields) >= 3:
        results.append((True, True, tx["d_data"].format(n=len(fields))))
    else:
        results.append((False, True, tx["d_data_bad"]))

    # 6 reproduction names seed and inputs
    body = pick(sections, ("how to reproduce", "复现方式")) or ""
    low = body.lower()
    has_seed = ("seed" in low) or ("种子" in body)
    has_inputs = (".json" in low) or (".tex" in low) or (".csv" in low) or ("输入文件" in body)
    if has_seed and has_inputs:
        results.append((True, True, tx["d_repro"]))
    elif not has_seed:
        results.append((False, True, tx["d_repro_seed"]))
    else:
        results.append((False, True, tx["d_repro_inputs"]))

    # 7 open items
    body = pick(sections, ("what is still missing", "还缺什么")) or ""
    items = bullets(body)
    if items:
        results.append((True, True, tx["d_missing"].format(n=len(items))))
    else:
        results.append((False, True, tx["d_missing_bad"]))

    if args.results:
        try:
            values = gather_numbers(args.results)
        except (OSError, ValueError) as exc:
            sys.stderr.write("cannot read %s: %s\n" % (args.results, exc))
            return 2
        total_n, matched, missing = check_numbers(text, values)
        if total_n == 0:
            results.append((True, True, tx["d_no_numbers"]))
        elif missing:
            results.append((False, True, tx["d_numbers_bad"].format(
                n=total_n, m=len(missing), items=", ".join(missing[:6]))))
        else:
            results.append((True, True, tx["d_numbers"].format(n=matched)))

    total = len(results)
    print(tx["title"])
    print("%s: %s" % (tx["file"], args.path.replace(os.sep, "/").replace("\\", "/")))
    print()
    passed = 0
    for i, (ok, weak, detail) in enumerate(results, 1):
        mark = tx["ok"] if ok else (tx["weak"] if weak else tx["missing"])
        if ok:
            passed += 1
        print("[%s] %d/%d %s: %s" % (mark, i, total, tx["checks"][i - 1], detail))

    placeholders = PLACEHOLDER.findall(text)
    if placeholders:
        print(tx["note"].format(n=len(placeholders)))
    print(tx["passed"].format(n=passed, total=total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
