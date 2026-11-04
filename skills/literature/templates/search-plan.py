#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Write a reproducible search plan for one research question.

Zero dependencies, deterministic: the same question always produces the same
file. It does not search anything -- it turns your question into a keyword
matrix, candidate JEL codes, four Boolean strings and an inclusion rule that
you can paste into EconLit, Web of Science, Google Scholar or OpenAlex, and
then record the hits in the log at the bottom.

Usage:
    python search-plan.py "minimum wage affects youth employment" --lang en
    python search-plan.py "最低工资对青年就业的影响" --lang zh --out plan.md

Exit codes: 0 wrote the plan, 1 nothing to write, 2 usage error.
"""

import argparse
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

STOP_EN = {
    "a", "an", "the", "of", "on", "in", "for", "to", "and", "or", "is", "are",
    "does", "do", "how", "what", "effect", "effects", "impact", "affects",
    "affect", "influence", "relationship", "between", "study", "research",
    "we", "i", "want", "analyse", "analyze", "examine", "estimate",
}
SPLIT_EN = re.compile(r"\b(?:on|upon|of)\b", re.I)
SPLIT_ZH = re.compile(r"对|对于|对.+?的")

# keyword -> candidate JEL codes (only a starting point; every code needs a check)
JEL_RULES = [
    (("wage", "wages", "labor", "labour", "employ", "employment", "unemploy",
      "worker", "job", "minimum wage", "工资", "劳动", "就业", "失业", "用工"),
     ["J2", "J3", "J4"]),
    (("school", "education", "student", "teacher", "college", "schooling",
      "教育", "学校", "学生", "教师", "升学"), ["I2", "J24"]),
    (("health", "mortality", "hospital", "smoking", "obesity", "mental",
      "健康", "死亡", "医疗", "心理"), ["I1", "I12", "I18"]),
    (("pollution", "emission", "air quality", "energy", "climate", "carbon",
      "environment", "污染", "排放", "能源", "气候", "碳", "环境"), ["Q5", "Q4", "Q2"]),
    (("trade", "export", "import", "tariff", "fdi", "贸易", "出口", "进口", "关税", "外资"),
     ["F1", "F2", "F6"]),
    (("firm", "industry", "market", "competition", "merger", "企业", "产业", "市场", "竞争", "并购"),
     ["L1", "L2", "D4"]),
    (("credit", "bank", "finance", "stock", "interest", "信贷", "银行", "金融", "股价", "利率"),
     ["G2", "G1", "E4"]),
    (("growth", "inflation", "monetary", "fiscal", "gdp", "增长", "通胀", "货币", "财政"),
     ["E2", "E6", "O4"]),
    (("experiment", "randomi", "lab", "field experiment", "实验", "随机", "田野"),
     ["C9", "C1", "D9"]),
    (("history", "historical", "历史", "史料"), ["N3", "N4", "N9"]),
    (("migration", "migrant", "city", "urban", "mobility", "迁移", "流动", "城市", "户籍"),
     ["J6", "R2", "O1"]),
    (("household", "consumption", "income", "saving", "家庭", "消费", "收入", "储蓄"),
     ["D1", "E2", "O1"]),
]

TEXT = {
    "en": {
        "title": "Search plan",
        "question": "Research question",
        "how": ("This file is a plan, not a result. Fill the `[to fill]` slots, run the strings, "
                "and record every run in the log at the bottom. A plan without a log is a guess."),
        "matrix": "Layer 1: keyword matrix",
        "matrix_head": "| Layer | Primary term | Synonyms to try | Note |\n|---|---|---|---|",
        "jel": "Layer 2: candidate JEL codes",
        "jel_head": "| Code | Why it might fit | Check before using |\n|---|---|---|",
        "bool": "Layer 3: four Boolean strings",
        "bool_head": "| Purpose | String | Where to run it |\n|---|---|---|",
        "inc": "Inclusion and exclusion",
        "inc_head": "| Rule | Value |\n|---|---|",
        "paste": "Paste blocks",
        "log": "Search log",
        "log_head": ("| Date | Database | String no. | Hits | Kept | Why rejected |\n"
                     "|---|---|---|---|---|---|"),
        "noq": "Give the question as one argument.",
        "wrote": "wrote",
        "empty": "the question is empty after cleaning; give one concrete sentence",
    },
    "zh": {
        "title": "检索方案",
        "question": "研究问题",
        "how": ("这份文件是方案，不是结果。把 `[待填]` 补掉，把检索串真的跑一遍，"
                "每次跑都记到最下面的检索记录里。没有记录的方案只是猜。"),
        "matrix": "第一层：关键词矩阵",
        "matrix_head": "| 层 | 主词 | 可试的同义词 | 说明 |\n|---|---|---|---|",
        "jel": "第二层：JEL 码候选",
        "jel_head": "| 码 | 为什么可能对得上 | 用之前要核对什么 |\n|---|---|---|",
        "bool": "第三层：四条布尔检索串",
        "bool_head": "| 用途 | 检索串 | 去哪跑 |\n|---|---|---|",
        "inc": "纳入与排除",
        "inc_head": "| 规则 | 取值 |\n|---|---|",
        "paste": "可粘贴的检索块",
        "log": "检索记录",
        "log_head": "| 日期 | 数据库 | 第几条串 | 命中数 | 留下 | 为什么排除 |\n|---|---|---|---|---|---|",
        "noq": "把研究问题作为参数传进来。",
        "wrote": "已写出",
        "empty": "清洗后问题为空，请给一句具体的题目",
    },
}


def tokens(question, lang):
    if lang == "zh":
        parts = re.split(r"[\s，,。；;：:、]+", question)
        out = []
        for p in parts:
            if len(p) < 2 or p in ("的影响", "研究", "分析"):
                continue
            for piece in re.split(r"对|对于|的", p):
                piece = piece.strip()
                if len(piece) >= 2 and piece not in out:
                    out.append(piece)
        return out
    low = question.lower()
    words = re.findall(r"[a-z][a-z\-]+", low)
    return [w for w in words if w not in STOP_EN and len(w) >= 3]


def layers(question, lang):
    """Split the question into a candidate treatment side and outcome side."""
    q = question.strip().strip("。.!！?？")
    if lang == "zh":
        m = re.split(r"对|对于", q, maxsplit=1)
        if len(m) == 2:
            left = m[0].strip("的 ")
            right = re.split(r"的|有什么|的影响|影响", m[1], maxsplit=1)[0].strip("的 ")
            return left or "[待填]", right or "[待填]"
        return q or "[待填]", "[待填]"
    m = SPLIT_EN.split(q, maxsplit=1)
    if len(m) == 2:
        left = re.sub(r"^(the\s+)?(effect|impact|influence)s?\s+of\s+", "", m[0].strip(), flags=re.I)
        right = re.sub(r"\s+(of|on)\s*$", "", m[1].strip(), flags=re.I)
        return left.strip() or "[to fill]", right.strip() or "[to fill]"
    return q or "[to fill]", "[to fill]"


def jel_candidates(question):
    low = question.lower()
    hits = []
    for keys, codes in JEL_RULES:
        if any(k in low for k in keys):
            for c in codes:
                if c not in hits:
                    hits.append(c)
    return hits[:4]


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("question", nargs="?", default="")
    ap.add_argument("--lang", choices=["en", "zh"], default="en")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    T = TEXT[a.lang]
    if not a.question.strip():
        print(T["noq"])
        return 2
    treat, outcome = layers(a.question, a.lang)
    toks = tokens(a.question, a.lang)
    if not toks:
        print(T["empty"])
        return 1

    out = a.out or ("search-plan.md")
    lines = []
    lines.append("# %s" % T["title"])
    lines.append("")
    lines.append("## %s" % T["question"])
    lines.append("")
    lines.append("> %s" % a.question.strip())
    lines.append("")
    lines.append(T["how"])
    lines.append("")

    lines.append("## %s" % T["matrix"])
    lines.append("")
    lines.append(T["matrix_head"])
    ph = "[待填]" if a.lang == "zh" else "[to fill]"
    layer_rows = [
        ("concept" if a.lang == "en" else "构念层", toks[0] if toks else "[to fill]",
         ", ".join(toks[1:4]) or "[to fill]",
         "the word a review article would use" if a.lang == "en" else "综述文章会用的那个词"),
        ("measure" if a.lang == "en" else "措施层", treat, ph,
         "the variable name in the data" if a.lang == "en" else "数据里那一列叫什么"),
        ("outcome" if a.lang == "en" else "结果层", outcome, ph,
         "how the outcome is measured" if a.lang == "en" else "结果变量怎么测"),
    ]
    for name, primary, syn, note in layer_rows:
        lines.append("| %s | %s | %s | %s |" % (name, primary, syn, note))
    lines.append("")
    lines.append("> " + ("Two rules: every layer needs at least two synonyms before you search; "
                         "and the measure layer must use the variable name, not the concept."
                         if a.lang == "en" else
                         "两条规矩：每层至少两个同义词再开始搜；措施层要写数据里的变量名，不要写概念。"))
    lines.append("")

    lines.append("## %s" % T["jel"])
    lines.append("")
    lines.append(T["jel_head"])
    codes = jel_candidates(a.question)
    if codes:
        for c in codes:
            why = ("keyword overlap with the question" if a.lang == "en"
                   else "与题目里的关键词重合")
            chk = ("look up the code description; a wrong code misplaces the paper"
                   if a.lang == "en" else "查一遍这个码的定义；码错了文章会被放进错误的栏目")
            lines.append("| %s | %s | %s |" % (c, why, chk))
    else:
        lines.append("| %s | %s | %s |" % ("[to fill]", "-", "-"))
    lines.append("")

    lines.append("## %s" % T["bool"])
    lines.append("")
    lines.append(T["bool_head"])
    core = " AND ".join('"%s"' % t for t in toks[:2]) if len(toks) >= 2 else '"%s"' % (toks[0] if toks else "x")
    strings = [
        ("broad sweep" if a.lang == "en" else "广撒网", core,
         "EconLit / Web of Science" if a.lang == "en" else "EconLit / Web of Science"),
        ("method filter" if a.lang == "en" else "方法过滤", core + ' AND ("difference-in-differences" OR "instrumental variable" OR "regression discontinuity")',
         "Web of Science" if a.lang == "en" else "Web of Science"),
        ("mechanism" if a.lang == "en" else "机制",
         '"%s" AND (mechanism OR channel OR "mediating")' % (toks[0] if toks else "x"),
         "Google Scholar" if a.lang == "en" else "Google Scholar"),
        ("recent work" if a.lang == "en" else "最近文献",
         core + " AND (2020 OR 2021 OR 2022 OR 2023 OR 2024 OR 2025)",
         "OpenAlex" if a.lang == "en" else "OpenAlex"),
    ]
    for purpose, s, where in strings:
        lines.append("| %s | %s | %s |" % (purpose, s.replace("|", "/"), where))
    lines.append("")

    lines.append("## %s" % T["inc"])
    lines.append("")
    lines.append(T["inc_head"])
    inc_rows = [
        ("peer reviewed" if a.lang == "en" else "已发表",
         "yes: journals and the four working-paper series" if a.lang == "en"
         else "是：期刊与四个工作论文系列"),
        ("language" if a.lang == "en" else "语言",
         "English plus Chinese if the setting is China" if a.lang == "en"
         else "英文，加中文（研究对象是中国时）"),
        ("period" if a.lang == "en" else "时间范围", "[to fill]" if a.lang == "en" else "[待填]"),
        ("must use" if a.lang == "en" else "必须用到",
         "a design that could separate the mechanism" if a.lang == "en"
         else "一个能把机制分离出来的设计"),
        ("drop" if a.lang == "en" else "排除",
         "descriptive pieces, policy notes, non-causal claims used as causal" if a.lang == "en"
         else "纯描述性文章、政策解读、把相关当因果的说法"),
    ]
    for rule, val in inc_rows:
        lines.append("| %s | %s |" % (rule, val))
    lines.append("")

    lines.append("## %s" % T["paste"])
    lines.append("")
    lines.append("```text")
    lines.append("EconLit (EBSCO)  : " + strings[0][1])
    lines.append("Web of Science   : TS=" + strings[0][1] + " AND DT=(Article OR Review)")
    lines.append("Google Scholar   : " + strings[0][1])
    lines.append("OpenAlex         : https://api.openalex.org/works?search=" +
                 (toks[0] if toks else "x") + "&per-page=25")
    lines.append("CNKI (中文)      : (" + (treat if a.lang == "zh" else "[待填]") + ") AND (" +
                 (outcome if a.lang == "zh" else "[待填]") + ")")
    lines.append("```")
    lines.append("")

    lines.append("## %s" % T["log"])
    lines.append("")
    lines.append(T["log_head"])
    lines.append("| | | | | | |")
    lines.append("")

    body = "\n".join(lines) + "\n"
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print("%s %s  (%d lines)" % (T["wrote"], os.path.abspath(out), body.count("\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
