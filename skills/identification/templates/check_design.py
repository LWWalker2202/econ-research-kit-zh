#!/usr/bin/env python3
"""Check a design memo for the six items an identification memo must contain.

Usage:
    python skills/identification/templates/check_design.py MEMO.md
    python skills/identification/templates/check_design.py MEMO.md --lang zh

The script reads one Markdown memo and reports OK, WEAK or MISSING for six
items: treatment and control, at least three threats each with a test, a
falsifying outcome for each threat, a clustering level with its reason, a
one-sentence statement of where the variation comes from, and a named binding
assumption. The exit status is 0 when all six items are OK.

Only the standard library is used. The verdicts depend on the memo alone, so
two runs on the same file print the same report, and --lang changes the
wording of the report without changing any verdict.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys

HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")
TABLE_ROW = re.compile(r"^\s*\|(.+?)\|\s*$")
SEPARATOR = re.compile(r"^:?-{3,}:?$")

VAR_WORDS = ("differ", "differs", "varies", "vary", "variation", "不同", "差异")
CAUSE_WORDS = ("because", "due to", "comes from", "stems from", "来自", "因为", "由于", "源于")
INDEP_WORDS = ("unrelated", "independent of", "no relation", "无关", "独立于", "不受")
TEST_WORDS = (
    "placebo",
    "pre-trend",
    "pretrend",
    "pre trend",
    "event study",
    "event-study",
    "parallel trend",
    "falsification",
    "balance",
    "robustness",
    "安慰剂",
    "事前趋势",
    "事件研究",
    "平行趋势",
    "平衡",
    "稳健",
    "反事实",
)
FALSIFY_WORDS = (
    "falsif",
    "would fail",
    "no longer identified",
    "cannot be identified",
    "would be rejected",
    "推翻",
    "证伪",
    "失效",
    "不能识别",
    "不成立",
)
LEVEL_WORDS = (
    "prefecture",
    "city",
    "county",
    "firm",
    "industry",
    "province",
    "district",
    "village",
    "school",
    "地市",
    "城市",
    "县",
    "企业",
    "行业",
    "省",
    "区",
    "村庄",
    "学校",
)
REASON_WORDS = (
    "because",
    "since",
    "reason",
    "理由",
    "原因",
    "因为",
    "由于",
    "取决于",
)

L10N = {
    "en": {
        "title": "Identification design check",
        "memo": "memo: {name}",
        "labels": (
            "Treatment and control are defined",
            "At least three threats, each with a test",
            "Each threat states what would falsify the design",
            "Clustering level and the reason for it",
            "Source of variation stated in one sentence",
            "Binding assumption named",
        ),
        "detail": {
            "c1_ok": "both groups defined in one section",
            "c1_weak": "treatment named, control group not defined",
            "c1_missing": "no treatment and control section",
            "c2_ok": "{nt} threats, {nw} carry a test",
            "c2_weak": "{nw} of {nt} threats carry a test, at least three are needed",
            "c2_missing": "no threat table with tests",
            "c3_ok": "{nw} of {nt} threats state a falsifying result",
            "c3_weak": "{nw} of {nt} threats state a falsifying result, all of them should",
            "c3_missing": "no falsifying result stated",
            "c4_ok": "level and reason stated",
            "c4_weak": "level named, reason missing",
            "c4_missing": "no clustering statement",
            "c5_ok": "variation sentence found",
            "c5_weak": "mechanism named, independence from the outcome not stated",
            "c5_missing": "no one-sentence source of variation",
            "c6_ok": "binding assumption named",
            "c6_weak": "phrase appears without a stated assumption",
            "c6_missing": "binding assumption not named",
        },
        "passed": "{n}/6 checks passed",
    },
    "zh": {
        "title": "识别设计检查",
        "memo": "备忘录：{name}",
        "labels": (
            "处理变量与对照组已定义",
            "至少三条威胁，每条都带检验",
            "每条威胁写明什么结果会推翻设计",
            "聚类层级及其理由",
            "用一句话说明变异来源",
            "点名最脆弱的假设",
        ),
        "detail": {
            "c1_ok": "两组定义在同一节里写清",
            "c1_weak": "点名了处理组，对照组没定义",
            "c1_missing": "缺处理变量与对照组一节",
            "c2_ok": "{nt} 条威胁，{nw} 条带检验",
            "c2_weak": "{nt} 条威胁里只有 {nw} 条带检验，至少要三条",
            "c2_missing": "没有带检验的威胁表",
            "c3_ok": "{nt} 条威胁里有 {nw} 条写明推翻条件",
            "c3_weak": "{nt} 条威胁里只有 {nw} 条写明推翻条件，应条条都有",
            "c3_missing": "没写推翻条件",
            "c4_ok": "层级与理由都写了",
            "c4_weak": "写了层级，缺理由",
            "c4_missing": "没写聚类层级",
            "c5_ok": "找到了变异句",
            "c5_weak": "写了机制，没写与结果变量无关",
            "c5_missing": "没有一句话的变异来源",
            "c6_ok": "点名了最脆弱的假设",
            "c6_weak": "提到了这个说法，但没写成假设",
            "c6_missing": "没点名最脆弱的假设",
        },
        "passed": "{n}/6 checks passed",
    },
}


def read_text(path):
    with io.open(path, "r", encoding="utf-8") as handle:
        return handle.read().replace("\r\n", "\n")


def split_sections(text):
    """Return a list of (level, title, body) triples in document order."""
    sections = []
    level, title, body = 0, "", []
    for line in text.split("\n"):
        match = HEADING.match(line)
        if match:
            sections.append((level, title, "\n".join(body)))
            level, title, body = len(match.group(1)), match.group(2).strip(), []
        else:
            body.append(line)
    sections.append((level, title, "\n".join(body)))
    return sections


def find_section(sections, words):
    for level, title, body in sections:
        if level and all(word in title.lower() for word in words):
            return body
    return None


def table_rows(body):
    rows = []
    for line in body.split("\n"):
        match = TABLE_ROW.match(line)
        if not match:
            continue
        cells = [cell.strip() for cell in match.group(1).split("|")]
        if cells and all(SEPARATOR.match(cell) for cell in cells if cell):
            continue
        rows.append(cells)
    return rows


def threat_rows(body):
    rows = table_rows(body)
    if not rows:
        return []
    data = rows[1:]
    keep = []
    for row in data:
        text = " ".join(row).strip().lower()
        if not text:
            continue
        if text in ("total", "合计"):
            continue
        keep.append(row)
    return keep


def candidates(text):
    out = []
    for line in text.split("\n"):
        line = line.strip(" \t-*#>|")
        if not line:
            continue
        for part in re.split(r"[。；;]", line):
            for piece in re.split(r"(?<=\.)\s+", part):
                piece = piece.strip()
                if piece:
                    out.append(piece)
    return out


def has_any(text, words):
    low = text.lower()
    return any(word in low for word in words)


def report(path, lang):
    text = read_text(path)
    sections = split_sections(text)
    rows = []

    # 1. Treatment and control
    body = find_section(sections, ("treatment", "control"))
    if body is None:
        body = find_section(sections, ("处理", "对照"))
    if body and len(body.strip()) >= 120:
        rows.append(("OK", "1", "c1_ok"))
    elif body is not None or (
        has_any(text, ("treatment", "处理")) and has_any(text, ("control", "对照"))
    ):
        rows.append(("WEAK", "1", "c1_weak"))
    else:
        rows.append(("MISSING", "1", "c1_missing"))

    # 2 and 3. Threat table with tests and falsifying outcomes
    body = find_section(sections, ("threat",))
    if body is None:
        body = find_section(sections, ("威胁",))
    threats = threat_rows(body) if body else []
    n_threats = len(threats)
    n_tested = sum(1 for row in threats if has_any(" ".join(row), TEST_WORDS))
    n_falsified = sum(1 for row in threats if has_any(" ".join(row), FALSIFY_WORDS))
    counts = {"nt": n_threats, "nw": n_tested}
    falsified = {"nt": n_threats, "nw": n_falsified}
    if n_threats >= 3 and n_tested >= 3:
        rows.append(("OK", "2", "c2_ok", counts))
    elif n_tested:
        rows.append(("WEAK", "2", "c2_weak", counts))
    else:
        rows.append(("MISSING", "2", "c2_missing", {}))
    if n_threats >= 3 and n_falsified == n_threats:
        rows.append(("OK", "3", "c3_ok", falsified))
    elif n_falsified:
        rows.append(("WEAK", "3", "c3_weak", falsified))
    else:
        rows.append(("MISSING", "3", "c3_missing", {}))

    # 4. Clustering level and its reason
    body = find_section(sections, ("cluster",))
    if body is None:
        body = find_section(sections, ("聚类",))
    scope = body if body is not None else text
    level = has_any(scope, LEVEL_WORDS)
    reason = has_any(scope, REASON_WORDS)
    if level and reason:
        rows.append(("OK", "4", "c4_ok"))
    elif level or body is not None and has_any(body, REASON_WORDS):
        rows.append(("WEAK", "4", "c4_weak"))
    else:
        rows.append(("MISSING", "4", "c4_missing"))

    # 5. One-sentence source of variation
    full = None
    partial = False
    for sentence in candidates(text):
        has_var = has_any(sentence, VAR_WORDS)
        has_cause = has_any(sentence, CAUSE_WORDS)
        has_indep = has_any(sentence, INDEP_WORDS)
        if has_var and has_cause and has_indep:
            full = sentence
            break
        if has_var and has_cause:
            partial = True
    if full is not None:
        rows.append(("OK", "5", "c5_ok"))
    elif partial:
        rows.append(("WEAK", "5", "c5_weak"))
    else:
        rows.append(("MISSING", "5", "c5_missing"))

    # 6. Binding assumption
    body = find_section(sections, ("binding assumption",))
    if body is None:
        body = find_section(sections, ("最脆弱",))
    if body is not None and len(body.strip()) >= 60:
        rows.append(("OK", "6", "c6_ok"))
    elif body is not None or has_any(text, ("binding assumption", "最脆弱")):
        rows.append(("WEAK", "6", "c6_weak"))
    else:
        rows.append(("MISSING", "6", "c6_missing"))

    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check a design memo for the six items of an identification memo."
    )
    parser.add_argument("memo", help="path to the design memo in Markdown")
    parser.add_argument(
        "--lang",
        choices=("en", "zh"),
        default="en",
        help="language of the report; the verdicts do not change",
    )
    args = parser.parse_args(argv)

    if not os.path.isfile(args.memo):
        sys.stderr.write("no such file: %s\n" % args.memo)
        return 2

    strings = L10N[args.lang]
    rows = report(args.memo, args.lang)
    passed = sum(1 for row in rows if row[0] == "OK")

    print(strings["title"])
    print(strings["memo"].format(name=os.path.basename(args.memo)))
    for row in rows:
        status, number, key = row[0], row[1], row[2]
        params = row[3] if len(row) > 3 else {}
        label = strings["labels"][int(number) - 1]
        detail = strings["detail"][key]
        if params:
            detail = detail.format(**params)
        print("[%s] %s %s: %s" % (status, number, label, detail))
    print(strings["passed"].format(n=passed))
    return 0 if passed == 6 else 1


if __name__ == "__main__":
    sys.exit(main())
