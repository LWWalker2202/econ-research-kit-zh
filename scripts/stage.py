#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print the status header and the confirmation question for one of the eight stages.

Zero dependencies, deterministic output. Exit codes: 0 ok, 2 usage error.

    python scripts/stage.py 3
    python scripts/stage.py --lang en 3
    python scripts/stage.py --list
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

STAGES = [
    dict(
        num=0,
        en=dict(
            name="Feasibility gate",
            does="fill the four slots (unit, treatment, outcome, comparison) and write the stop criteria",
            artifact="feasibility-memo.md",
            ask="The four slots are filled; can you settle the ones I inferred?",
        ),
        zh=dict(
            name="可行性闸门",
            does="把四槽位（分析单元、处理变量、结果变量、对照组）填满，并写出止损判据",
            artifact="feasibility-memo.md",
            ask="四槽填满了，我推断的那几项你能定吗？",
        ),
    ),
    dict(
        num=1,
        en=dict(
            name="Problem and literature",
            does="build the literature matrix and name the gap in one sentence",
            artifact="lit-matrix.csv",
            ask="Which of these candidate questions, and is the gap this one?",
        ),
        zh=dict(
            name="问题与文献",
            does="做文献矩阵，用一句话点明缺口",
            artifact="lit-matrix.csv",
            ask="这几个候选题目选哪个？缺口是这个吗？",
        ),
    ),
    dict(
        num=2,
        en=dict(
            name="Identification design",
            does="write the treatment, the comparison and the timing as one testable sentence, plus the threat list",
            artifact="identification-memo.md",
            ask="Treatment group, comparison group and timing set this way: do you accept it?",
        ),
        zh=dict(
            name="识别设计",
            does="把处理组、对照组、时点写成一句可检验的话，并列出威胁清单",
            artifact="identification-memo.md",
            ask="处理组、对照组、时点这样定，你认吗？",
        ),
    ),
    dict(
        num=3,
        en=dict(
            name="Data",
            does="list every cleaning action in a decision table before touching a single row",
            artifact="cleaning-decisions.md",
            ask="These cleaning actions and variable definitions: do you accept them, or change which one?",
        ),
        zh=dict(
            name="数据",
            does="先用一张决策表列出每一处删改，再动数据",
            artifact="cleaning-decisions.md",
            ask="这些清洗动作与变量口径，你认吗？哪一条要改？",
        ),
    ),
    dict(
        num=4,
        en=dict(
            name="Estimation",
            does="run the specification ladder one rung at a time and show what moves",
            artifact="spec-ladder.md",
            ask="This ladder and robustness list: add or drop anything?",
        ),
        zh=dict(
            name="估计",
            does="一级一级跑设定阶梯，把每一级的结果都摊开",
            artifact="spec-ladder.md",
            ask="这份设定阶梯与稳健性清单，要增减吗？",
        ),
    ),
    dict(
        num=5,
        en=dict(
            name="Tables and figures",
            does="produce the table or figure from a script and check it against the journal habit",
            artifact="table1.tex",
            ask="This layout and note style: is this what you want?",
        ),
        zh=dict(
            name="表与图",
            does="用脚本产出表或图，并对照期刊惯例检查",
            artifact="table1.tex",
            ask="三线表样式与表注写法按这个出？",
        ),
    ),
    dict(
        num=6,
        en=dict(
            name="Report",
            does="let a script write the report so every number traces back to a file",
            artifact="report.md",
            ask="One-page conclusion written this way: any change to how the numbers read?",
        ),
        zh=dict(
            name="报告",
            does="让脚本产出报告，每个数字都能追到文件",
            artifact="report.md",
            ask="一页纸结论这样写，对数字的读法要改吗？",
        ),
    ),
    dict(
        num=7,
        en=dict(
            name="Writing and submission",
            does="draft the identification paragraph first, then the rest",
            artifact="abstract.md",
            ask="Which part of this draft goes back?",
        ),
        zh=dict(
            name="写作与投稿",
            does="先写识别策略那一段，再写其余部分",
            artifact="abstract.md",
            ask="这段初稿哪一部分要打回去？",
        ),
    ),
    dict(
        num=8,
        en=dict(
            name="Referee response",
            does="classify every comment, then answer one at a time in writing",
            artifact="response-letter.md",
            ask="Do we revise this comment or push back, and is this the reason?",
        ),
        zh=dict(
            name="审稿回复",
            does="先把每条意见分类，再逐条书面回答",
            artifact="response-letter.md",
            ask="这条意见是改还是争，理由这样写吗？",
        ),
    ),
]

L = dict(
    en=dict(
        stage="Stage {num} · {name}",
        does="This step only does: {does}",
        artifact="Produces: {artifact}",
        stop="Stops and waits for you: yes",
        ask="The question for this stage: {ask}",
        hint="Print the header for one stage: python scripts/stage.py 3",
        badnum="No such stage: {raw}. Run python scripts/stage.py --list to see them.",
    ),
    zh=dict(
        stage="【第 {num} 段 · {name}】",
        does="这一步只做：{does}",
        artifact="产出：{artifact}",
        stop="停下来等你：是",
        ask="这一段的确认句：{ask}",
        hint="打印某一段的状态头：python scripts/stage.py 3",
        badnum="没有第 {raw} 段。先跑 python scripts/stage.py --list 看看有哪几段。",
    ),
)


BEYOND = {
    0: {
        "zh": [
            '用二手行政数据时：多一张变量口径对照表（同一指标不同年份的定义变过）',
            '跨多个数据源时：多一步合并键与覆盖度核对',
            '涉及问卷或实验时：多一份预注册与伦理审查',
        ],
        "en": [
            'With administrative data: add a definition crosswalk (the same indicator changes definition across years)',
            'With several sources: add a merge-key and coverage check',
            'With a survey or an experiment: add pre-registration and ethics review',
        ],
    },
    1: {
        "zh": [
            '中文题目：多做一轮中文文献补检（Crossref 中文元数据弱，要换关键词）',
            '已有目标期刊：多一步读该刊近三年同题文章的缺口口径',
        ],
        "en": [
            'Chinese topic: add a second search pass (Chinese metadata on Crossref is thin, so change the keywords)',
            'Target journal chosen: read how that journal framed the gap in the last three years',
        ],
    },
    2: {
        "zh": [
            '多期 DID：多一张处理时点表，并检查负权重',
            'IV：多一份一阶段强度表与排他性论证',
            'RDD：多一份带宽敏感性与操纵检验',
        ],
        "en": [
            'Staggered DID: add a treatment-timing table and check negative weights',
            'IV: add a first-stage strength table and an exclusion argument',
            'RDD: add bandwidth sensitivity and a manipulation test',
        ],
    },
    3: {
        "zh": [
            '多源合并：多一份合并日志（哪一步丢了多少行）',
            '有缺测：多一张缺失机制说明（MCAR/MAR/MNAR）',
            '有抽样权重：多一份权重与代表性核对',
        ],
        "en": [
            'Several sources merged: add a merge log (how many rows each step dropped)',
            'Missing values: add a missingness note (MCAR/MAR/MNAR)',
            'Sampling weights: add a weight and representativeness check',
        ],
    },
    4: {
        "zh": [
            '主结果不稳：多做设定阶梯（--ladder），并说明报告哪一级',
            '聚类层级有争议：多一份多层级聚类对照',
            '结果变量不止一个：多一份多重检验校正',
        ],
        "en": [
            'Fragile main result: run the specification ladder (--ladder) and say which rung you report',
            'Clustering level disputed: add a multi-level clustering comparison',
            'Several outcomes: add a multiple-testing correction',
        ],
    },
    5: {
        "zh": [
            '投中文刊：套 journal-cn 规范（表题位置、横线数、小数位、标点）',
            '有异质性结果：多一张分组表与交互项',
        ],
        "en": [
            'Chinese journal: follow the journal-cn overrides (caption position, rules, decimals, punctuation)',
            'Heterogeneity: add a subgroup table and the interaction term',
        ],
    },
    6: {
        "zh": [
            '要复现：多一份复现说明（数据版本、随机种子、运行时间）',
            '数据保密：多一份可得性声明与申请流程',
        ],
        "en": [
            'Reproducibility required: add a reproduction note (data version, seed, runtime)',
            'Restricted data: add an availability statement and the access route',
        ],
    },
    7: {
        "zh": [
            '投英文刊：多一轮语言与文献风格对齐',
            '投中文刊：多一轮按刊改摘要与关键词',
        ],
        "en": [
            'English journal: add a language and citation-style pass',
            'Chinese journal: rewrite the abstract and keywords for that journal',
        ],
    },
    8: {
        "zh": [
            '意见有分歧：多一份「不同意但已处理」的逐条说明',
            '要求补分析：多一份补充结果附录与新增表',
        ],
        "en": [
            'A comment you disagree with: add a line-by-line note on what you did instead',
            'New analysis requested: add a supplementary appendix with the new tables',
        ],
    },
}


def render(stage, lang):
    t = L[lang]
    d = stage[lang]
    lines = [
        t["stage"].format(num=stage["num"], name=d["name"]),
        t["does"].format(does=d["does"]),
        t["artifact"].format(artifact=d["artifact"]),
        t["stop"],
        t["ask"].format(ask=d["ask"]),
    ]
    beyond = BEYOND.get(stage["num"], {}).get(lang) or []
    if beyond:
        lines.append("")
        lines.append("＋ 按题目可能要加的（做了就记在账本 note 里，不做不算缺）")
        for item in beyond:
            lines.append("  · " + item)
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("stage", nargs="?", help="stage number, 0 to 8")
    ap.add_argument("--lang", choices=["en", "zh"], default="zh")
    ap.add_argument("--list", action="store_true", help="list all stages")
    args = ap.parse_args(argv)
    t = L[args.lang]

    if args.list:
        for st in STAGES:
            print("{num}  {name}".format(num=st["num"], name=st[args.lang]["name"]))
        print()
        print(t["hint"])
        return 0

    if args.stage is None:
        print(t["hint"], file=sys.stderr)
        return 2

    raw = args.stage.strip()
    if not raw.isdigit() or int(raw) not in [s["num"] for s in STAGES]:
        print(t["badnum"].format(raw=raw), file=sys.stderr)
        return 2

    num = int(raw)
    st = [s for s in STAGES if s["num"] == num][0]
    print(render(st, args.lang))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
