#!/usr/bin/env python3
"""Check whether a feasibility memo is complete before anyone acts on it.

The script applies six checks to one memo written in the format of
`skills/feasibility/SKILL.md` and prints OK, WEAK, or MISSING for each:
the four question slots, the coverage matrix, the stop criteria, the
verdict, the binding constraint, and the access channels with lead times.

The script is deterministic: the same memo produces the same report.
`--lang` changes the wording of the report only, never the outcome of a
check, because every pattern matches both English and Chinese forms.

Exit code: 0 when all six checks pass, 1 when any check is not OK, and 2
when the memo cannot be read.
"""

import argparse
import re
import sys

OK = "OK"
WEAK = "WEAK"
MISSING = "MISSING"

HEADING = re.compile(r"^##\s+(.+?)\s*$")
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.+?)\s*$")
SEPARATOR = re.compile(r"^\|[\s:\-|]+\|?$")
DIGIT = re.compile(r"\d")
LEAD_TIME = re.compile(r"(?:week|周)", re.IGNORECASE)
THRESHOLD = re.compile(
    r"(?:≥|≤|>=|<=|>|<|超过|不足|多于|少于|至少|至多|以上|以下|以内|高于|低于"
    r"|more than|less than|fewer than|at least|at most|within|exceed|above|below)",
    re.IGNORECASE,
)
VERDICT = re.compile(r"^\s*(?:verdict|结论|判定)\s*[:：]\s*(.*?)\s*$", re.IGNORECASE)
BINDING = re.compile(r"^\s*(?:binding constraint|约束瓶颈|绑定约束)\s*[:：]\s*(.*?)\s*$", re.IGNORECASE)
PLACEHOLDER = re.compile(
    r"^(?:\[to fill\]|\[待填\]|\[待核实\]|\[verify\]|tbd|n/a|—|-|\.\.\.)$",
    re.IGNORECASE,
)

SLOTS = (
    ("unit", ("unit", "unit of analysis", "observation unit", "研究单位", "观测单位", "分析单位")),
    ("treatment", ("treatment variable", "treatment", "处理变量")),
    ("outcome", ("outcome", "outcome variable", "dependent variable", "结果变量", "被解释变量")),
    ("comparison", ("comparison", "comparison group", "control group", "对照组", "比较组")),
)

COVERAGE_CLASSES = (
    ("present", "proxy", "missing"),
    ("可得", "代理", "缺失"),
)

SECTION_TITLES = {
    "coverage": ("data coverage", "coverage", "数据覆盖", "覆盖矩阵"),
    "stop": ("stop criteria", "stop rules", "止损判据", "停止判据"),
    "access": ("data access", "access", "数据获取", "获取渠道"),
}

VERDICT_TOKENS = (
    "go with reduced scope",
    "缩小范围后做",
    "stop",
    "放弃",
    "go",
    "做",
)

TEXT = {
    "en": {
        "title": "Feasibility memo completeness check",
        "memo": "memo",
        "labels": (
            "four slots filled (unit, treatment variable, outcome, comparison)",
            "coverage matrix marks present, proxy, and missing",
            "at least three stop criteria, each with a numeric threshold",
            "verdict is one of go, go with reduced scope, stop",
            "binding constraint is named",
            "every dataset has an access route and a lead time in weeks",
        ),
        "slot_names": {
            "unit": "unit",
            "treatment": "treatment variable",
            "outcome": "outcome",
            "comparison": "comparison",
        },
        "class_names": {"present": "present", "proxy": "proxy", "missing": "missing"},
        "passed": "{passed}/6 checks passed",
        "detail_slots_missing": "slots without a label: {names}",
        "detail_slots_empty": "slots left empty: {names}",
        "detail_no_coverage_section": "no data coverage section: expected a heading such as Data coverage",
        "detail_coverage_missing": "classes absent from the matrix: {names}",
        "detail_no_stop_section": "no stop criteria section: expected a heading such as Stop criteria",
        "detail_stop_short": "stop criteria with a numeric threshold: {count}, need 3",
        "detail_no_verdict": "no verdict line: expected a line such as Verdict: go with reduced scope",
        "detail_verdict_unknown": "verdict is not one of the three allowed values: {value}",
        "detail_no_binding": "no binding constraint line: expected a line such as Binding constraint: ...",
        "detail_binding_empty": "binding constraint line is present but empty or a placeholder",
        "detail_no_access_section": "no data access section: expected a heading such as Data access",
        "detail_no_access_rows": "data access section has no table rows",
        "detail_access_weak": "rows without a lead time in weeks: {count} of {total}",
        "read_error": "cannot read memo: {path}",
    },
    "zh": {
        "title": "可行性备忘录完整性检查",
        "memo": "备忘录",
        "labels": (
            "四槽位已填（研究单位、处理变量、结果变量、对照组）",
            "覆盖矩阵同时标出可得、代理、缺失",
            "止损判据不少于 3 条，每条带数字阈值",
            "结论为 做、缩小范围后做、放弃 三者之一",
            "已指名约束瓶颈",
            "每个数据集都有获取渠道与获取周期（周）",
        ),
        "slot_names": {
            "unit": "研究单位",
            "treatment": "处理变量",
            "outcome": "结果变量",
            "comparison": "对照组",
        },
        "class_names": {"present": "可得", "proxy": "代理", "missing": "缺失"},
        "passed": "{passed}/6 项通过",
        "detail_slots_missing": "缺少标签的槽位：{names}",
        "detail_slots_empty": "留空或仍是占位符的槽位：{names}",
        "detail_no_coverage_section": "没有覆盖矩阵小节：应出现类似 数据覆盖 的标题",
        "detail_coverage_missing": "矩阵里缺失的类别：{names}",
        "detail_no_stop_section": "没有止损判据小节：应出现类似 止损判据 的标题",
        "detail_stop_short": "带数字阈值的止损判据只有 {count} 条，需要 3 条",
        "detail_no_verdict": "没有结论行：应出现类似 结论：缩小范围后做 的一行",
        "detail_verdict_unknown": "结论不在三选一之内：{value}",
        "detail_no_binding": "没有约束瓶颈行：应出现类似 约束瓶颈：…… 的一行",
        "detail_binding_empty": "约束瓶颈行存在，但内容为空或仍是占位符",
        "detail_no_access_section": "没有数据获取小节：应出现类似 数据获取 的标题",
        "detail_no_access_rows": "数据获取小节里没有表格数据行",
        "detail_access_weak": "没有获取周期（周）的数据行：{count} 行，共 {total} 行",
        "read_error": "无法读取备忘录：{path}",
    },
}


def read_lines(path):
    """Return the memo as a list of lines, with any byte-order mark removed."""
    with open(path, "r", encoding="utf-8-sig") as handle:
        return handle.read().splitlines()


def is_placeholder(value):
    """Return True when a cell carries no content beyond a placeholder."""
    text = value.strip().strip("*").strip()
    return text == "" or bool(PLACEHOLDER.match(text))


def table_cells(line):
    """Return the stripped cells of one table row, or None for other lines."""
    stripped = line.strip()
    if not stripped.startswith("|") or SEPARATOR.match(stripped):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def split_sections(lines):
    """Return a list of (title, body lines) for every level-two heading."""
    sections = []
    current = None
    for line in lines:
        match = HEADING.match(line)
        if match:
            current = (match.group(1).strip(), [])
            sections.append(current)
        elif current is not None:
            current[1].append(line)
    return sections


def find_section(sections, titles):
    """Return the body of the first section whose title matches one of titles."""
    for title, body in sections:
        key = title.strip().rstrip(":：").casefold()
        for candidate in titles:
            if key == candidate or key.startswith(candidate + " ") or key.startswith(candidate + "（"):
                return body
    return None


def table_rows(body):
    """Return (header, data rows) of the first table in body."""
    header = []
    rows = []
    header_seen = False
    for line in body:
        cells = table_cells(line)
        if cells is None:
            continue
        if not header_seen:
            header = cells
            header_seen = True
            continue
        rows.append(cells)
    return header, rows


def check_slots(lines, tx):
    """Check that the four question slots are labelled and filled."""
    found = {}
    for line in lines:
        cells = table_cells(line)
        if not cells or len(cells) < 2:
            continue
        label = cells[0].strip().strip("*").strip().casefold()
        for key, names in SLOTS:
            if label in names and key not in found:
                found[key] = cells[1]
    missing = [key for key, _ in SLOTS if key not in found]
    if missing:
        names = ", ".join(tx["slot_names"][key] for key in missing)
        return MISSING, tx["detail_slots_missing"].format(names=names)
    empty = [key for key, _ in SLOTS if key in found and is_placeholder(found[key])]
    if empty:
        names = ", ".join(tx["slot_names"][key] for key in empty)
        return WEAK, tx["detail_slots_empty"].format(names=names)
    return OK, ""


def check_coverage(sections, tx):
    """Check that the coverage matrix marks present, proxy, and missing."""
    body = find_section(sections, SECTION_TITLES["coverage"])
    if body is None:
        return MISSING, tx["detail_no_coverage_section"]
    _, rows = table_rows(body)
    if not rows:
        return MISSING, tx["detail_no_coverage_section"]
    blob = " ".join(" ".join(row) for row in rows).casefold()
    best_absent = None
    for classes in COVERAGE_CLASSES:
        absent = [name for name in classes if name.casefold() not in blob]
        if not absent:
            return OK, ""
        if best_absent is None or len(absent) < len(best_absent):
            best_absent = absent
    names = ", ".join(tx["class_names"].get(name, name) for name in best_absent)
    return WEAK, tx["detail_coverage_missing"].format(names=names)


def check_stop_criteria(sections, tx):
    """Check for at least three stop criteria, each with a numeric threshold."""
    body = find_section(sections, SECTION_TITLES["stop"])
    if body is None:
        return MISSING, tx["detail_no_stop_section"]
    qualified = 0
    for line in body:
        match = BULLET.match(line)
        if not match:
            continue
        item = match.group(1)
        if DIGIT.search(item) and THRESHOLD.search(item):
            qualified += 1
    if qualified >= 3:
        return OK, ""
    if qualified == 0:
        return MISSING, tx["detail_stop_short"].format(count=0)
    return WEAK, tx["detail_stop_short"].format(count=qualified)


def check_verdict(lines, tx):
    """Check for a verdict line naming one of the three allowed outcomes."""
    value = None
    for line in lines:
        match = VERDICT.match(line)
        if match:
            value = match.group(1).strip().strip("*").strip()
            break
    if value is None:
        return MISSING, tx["detail_no_verdict"]
    lowered = value.casefold()
    for token in VERDICT_TOKENS:
        if lowered.startswith(token.casefold()):
            return OK, ""
    return WEAK, tx["detail_verdict_unknown"].format(value=value)


def check_binding(lines, tx):
    """Check that the binding constraint is named and not left as a placeholder."""
    value = None
    for line in lines:
        match = BINDING.match(line)
        if match:
            value = match.group(1).strip().strip("*").strip()
            break
    if value is None:
        return MISSING, tx["detail_no_binding"]
    if is_placeholder(value):
        return WEAK, tx["detail_binding_empty"]
    return OK, ""


def check_access(sections, tx):
    """Check that every dataset row names an access route and a lead time."""
    body = find_section(sections, SECTION_TITLES["access"])
    if body is None:
        return MISSING, tx["detail_no_access_section"]
    header, rows = table_rows(body)
    if not rows:
        return MISSING, tx["detail_no_access_rows"]
    lead_column = None
    for index, cell in enumerate(header):
        if LEAD_TIME.search(cell):
            lead_column = index
            break
    blank = 0
    for row in rows:
        if lead_column is not None and lead_column < len(row):
            has_lead = bool(DIGIT.search(row[lead_column]))
        else:
            has_lead = bool(DIGIT.search(" ".join(row)) and LEAD_TIME.search(" ".join(row)))
        if not has_lead:
            blank += 1
    if blank == 0:
        return OK, ""
    return WEAK, tx["detail_access_weak"].format(count=blank, total=len(rows))


def build_report(results, labels, memo_path, tx):
    """Return the report text for the six check results."""
    width = max(len(label) for label in labels)
    lines = [tx["title"], tx["memo"] + ": " + memo_path, ""]
    for index, (label, (status, detail)) in enumerate(zip(labels, results), start=1):
        lines.append("[{}] {}  {}".format(index, label.ljust(width), status))
        if detail:
            lines.append("    " + detail)
    passed = sum(1 for status, _ in results if status == OK)
    lines.append("")
    lines.append(tx["passed"].format(passed=passed))
    return "\n".join(lines) + "\n", passed


def main(argv=None):
    """Run the six checks and print the report."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Check whether a feasibility memo is complete (six checks).",
    )
    parser.add_argument("memo", help="path to the feasibility memo to check")
    parser.add_argument("--lang", choices=("en", "zh"), default="en", help="language of the report")
    parser.add_argument("--out", default=None, help="optional path to write the report to")
    args = parser.parse_args(argv)

    tx = TEXT[args.lang]
    try:
        lines = read_lines(args.memo)
    except OSError:
        sys.stderr.write(tx["read_error"].format(path=args.memo) + "\n")
        return 2

    sections = split_sections(lines)
    results = (
        check_slots(lines, tx),
        check_coverage(sections, tx),
        check_stop_criteria(sections, tx),
        check_verdict(lines, tx),
        check_binding(lines, tx),
        check_access(sections, tx),
    )
    report, passed = build_report(results, tx["labels"], args.memo, tx)
    sys.stdout.write(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(report)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
