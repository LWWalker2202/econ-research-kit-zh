#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check a literature matrix for the seven things a matrix must be able to show.

It checks format and completeness, not truth: it cannot tell whether a paper
exists or whether you read it. Use it to catch the boring failures before a
human reads the matrix.

Expected header (order free):
    id,citation,question,design,finding,source,closest

Usage:
    python check_matrix.py lit-matrix.csv --lang en
    python check_matrix.py lit-matrix.csv --lang zh --report lit-matrix-check.txt

Exit codes: 0 all seven checks pass, 1 at least one fails, 2 cannot read the file.
"""

import argparse
import csv
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

COLUMNS = ["id", "citation", "question", "design", "finding", "source", "closest"]

DOI = re.compile(r"10\.\d{4,9}/[^\s,;]+")
VENUE = re.compile(r"\d{4}[^\d]{0,24}\d+\s*\(\s*\d+\s*\)\s*[,:]\s*\d+\s*[-–—]\s*\d+")
WPNUM = re.compile(r"\b(NBER\s*w?\d{3,}|CEPR\s*\d{3,}|IZA\s*\d{3,}|WP[-\s]?\d{2,})\b", re.I)
DIRECTION = re.compile(
    r"(增加|减少|上升|下降|提高|降低|正向|负向|显著为负|显著为正|"
    r"increas|decreas|reduc|rais|positiv|negativ|higher|lower|"
    r"\d+(\.\d+)?\s*%|\d+\.\d+|系数|弹性)",
    re.I,
)
PLACEHOLDER = re.compile(r"^\s*(\[?待填\]?|\[?待核实\]?|\[?to fill\]?|\[?verify\]?|tbd|todo|-)\s*$", re.I)
GENERIC_DESIGN = {
    "实证", "定量", "数据分析", "回归分析", "面板数据",
    "empirical", "quantitative", "data analysis", "regression", "panel data",
}

TXT = {
    "en": {
        "header": "header has all seven columns",
        "id": "every row carries a resolvable identifier",
        "question": "every row states the research question",
        "design": "every row names the actual design",
        "finding": "every row states a direction or a magnitude",
        "closest": "exactly one row is marked closest",
        "source": "at least three distinct sources",
        "rows": "rows",
        "placeholders": "explicit placeholders",
        "pass": "checks passed",
        "noheader": "header is missing",
        "cannot": "cannot read",
        "detail": "detail",
    },
    "zh": {
        "header": "表头七列齐全",
        "id": "每一行都有可解析的标识",
        "question": "每一行都写了研究问题",
        "design": "每一行都点名了实际设计",
        "finding": "每一行都写了方向或幅度",
        "closest": "恰好一行标为最接近",
        "source": "至少三个不同来源",
        "rows": "行",
        "placeholders": "显式占位符",
        "pass": "项检查通过",
        "noheader": "表头不全",
        "cannot": "读不到文件",
        "detail": "细节",
    },
}


def read_rows(path):
    with io.open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
        rows = []
        for r in reader:
            rows.append({(k or "").strip().lower(): (v or "").strip() for k, v in r.items()})
    return header, rows


def is_placeholder(v):
    return bool(PLACEHOLDER.match(v or ""))


def has_identifier(v):
    if not v or is_placeholder(v):
        return False
    return bool(DOI.search(v) or VENUE.search(v) or WPNUM.search(v))


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("matrix", nargs="?", default="")
    ap.add_argument("--lang", choices=["en", "zh"], default="en")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    T = TXT[a.lang]

    if not a.matrix:
        print("%s: python check_matrix.py <lit-matrix.csv>" % T["cannot"])
        return 2
    if not os.path.isfile(a.matrix):
        print("%s: %s" % (T["cannot"], a.matrix))
        return 2

    header, rows = read_rows(a.matrix)
    missing = [c for c in COLUMNS if c not in header]
    problems = []

    def add(n, ok, detail):
        tag = "OK" if ok else "MISS"
        problems.append((n, ok, detail))
        print("[%s] %d %s%s" % (tag, n, T["%s" % name_of(n)], ("  -- " + detail) if detail and not ok else ""))

    def name_of(n):
        return {1: "header", 2: "id", 3: "question", 4: "design",
                5: "finding", 6: "closest", 7: "source"}[n]

    if missing:
        add(1, False, "missing columns: " + ", ".join(missing))
        print(T["noheader"] + ": " + ", ".join(missing))
        return 1
    add(1, True, "")

    bad_id = [str(i + 2) for i, r in enumerate(rows) if not has_identifier(r.get("id", ""))]
    add(2, not bad_id, "rows " + ", ".join(bad_id[:6]) if bad_id else "")

    bad_q = [str(i + 2) for i, r in enumerate(rows)
             if len(r.get("question", "")) < 12 or is_placeholder(r.get("question", ""))]
    add(3, not bad_q, "rows " + ", ".join(bad_q[:6]) if bad_q else "")

    def design_bad(v):
        v2 = (v or "").strip()
        return (not v2) or is_placeholder(v2) or len(v2) < 6 or v2.lower() in GENERIC_DESIGN

    bad_d = [str(i + 2) for i, r in enumerate(rows) if design_bad(r.get("design", ""))]
    add(4, not bad_d, "rows " + ", ".join(bad_d[:6]) if bad_d else "")

    def finding_bad(v):
        v2 = (v or "").strip()
        return (not v2) or is_placeholder(v2) or not DIRECTION.search(v2)

    bad_f = [str(i + 2) for i, r in enumerate(rows) if finding_bad(r.get("finding", ""))]
    add(5, not bad_f, "rows " + ", ".join(bad_f[:6]) if bad_f else "")

    yes = [r for r in rows if (r.get("closest", "").strip().lower() in
                               ("yes", "y", "是", "1", "true"))]
    add(6, len(yes) == 1, "found %d rows marked closest" % len(yes))

    sources = sorted({(r.get("source", "") or "").strip().lower() for r in rows
                      if (r.get("source", "") or "").strip() and not is_placeholder(r.get("source", ""))})
    add(7, len(sources) >= 3, "distinct sources: %d" % len(sources))

    passed = sum(1 for _, ok, _ in problems if ok)
    total = len(problems)
    placeholders = sum(1 for r in rows for v in r.values() if is_placeholder(v))
    print("")
    print("%d %s" % (len(rows), T["rows"]))
    if placeholders:
        print("%d %s" % (placeholders, T["placeholders"]))
    print("%d/%d %s" % (passed, total, T["pass"]))

    if a.report:
        out = []
        labels = {1: "header has all seven columns",
                  2: "every row carries a resolvable identifier",
                  3: "every row states the research question",
                  4: "every row names the actual design",
                  5: "every row states a direction or a magnitude",
                  6: "exactly one row is marked closest",
                  7: "at least three distinct sources"}
        for n, ok, detail in problems:
            out.append("[%s] %d %s%s" % ("OK" if ok else "MISS", n, labels[n],
                                         ("  -- " + detail) if detail and not ok else ""))
        out.append("%d/%d checks passed" % (passed, total))
        with io.open(a.report, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out) + "\n")
        print("%s %s" % (T["detail"], os.path.abspath(a.report)))

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
