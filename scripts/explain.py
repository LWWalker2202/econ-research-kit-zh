#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Explain what each stage's checks actually ask, in plain language.

Usage:
    python scripts/explain.py 2          # stage 2, Chinese
    python scripts/explain.py 2 --lang en
    python scripts/explain.py --list

Exit code: 0 on success, 2 on a usage error.

Why this file exists: the checkers print pass/fail, which tells you *that* a
check failed but not *what it was looking for*. This prints, for every stage,
each item as three lines: what it looks at, why it matters, and what a failing
answer looks like. Stages without a mechanical checker yet are marked as such,
and the same three lines double as the manual worksheet.
"""

from __future__ import annotations

import argparse
import sys

try:  # Windows console
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass


# Each item: (title, what it looks at, why it matters, what a failing answer looks like)
STAGES = [
    {
        "no": 0,
        "zh": "可行性",
        "en": "Feasibility",
        "auto_zh": "有自动检查器：skills/feasibility/templates/check_memo.py（6 项）",
        "auto_en": "Mechanical checker: skills/feasibility/templates/check_memo.py (six items)",
        "cmd": "python skills/feasibility/templates/check_memo.py your-memo.md --lang en",
        "items": [
            (
                ("四槽位都填了", "研究单位、处理变量、结果变量、对照组这四件事各写了一句", "缺一件，后面的识别设计与数据请求都无从谈起", "只写“研究 X 对 Y 的影响”，没说是谁、跟谁比"),
                ("All four slots filled", "Unit, treatment variable, outcome and comparison each get a sentence", "Missing one and the design and the data request have no footing", "\"I want to study the effect of X on Y\" with no unit and no comparison"),
            ),
            (
                ("覆盖矩阵分了三档", "每个数据来源标成可得、代理或缺失，而不是一律写“有”", "拿不到的数据等于没有识别", "所有格子都写“可得”，一格代理或缺失都没有"),
                ("Coverage matrix has three grades", "Every source is marked available, proxy or missing", "Data you cannot get gives you no identification", "Every cell says available, none is proxy or missing"),
            ),
            (
                ("止损判据不少于三条，且带数字", "提前写清到什么程度就不做了", "不写，做着做着就变成硬凑结果", "写成“视情况而定”“数据质量不好就放弃”"),
                ("At least three stop criteria, with numbers", "You write down in advance what would make you stop", "Without it the project drifts into manufacturing a result", "\"Depends on the situation\" or \"stop if the data look bad\""),
            ),
            (
                ("给出三选一结论", "做、缩小范围后做、放弃，必须选一个", "没有结论，下一步没有入口", "结尾写“有待进一步研究”"),
                ("One of three verdicts", "Go, go with reduced scope, or stop", "Without a verdict the next stage has no entry point", "Ending on \"further research is needed\""),
            ),
            (
                ("指名约束瓶颈", "说清最卡的那一件事", "瓶颈决定要不要缩范围", "列了十条困难，没说哪一条最要命"),
                ("Name the binding constraint", "The one thing that blocks the most", "The binding constraint decides whether to cut scope", "Ten difficulties listed, none named as binding"),
            ),
            (
                ("获取渠道与周期", "每个数据集写清从哪拿、等几周", "申请周期决定时间表能不能排开", "只写“来自某数据库”，没有渠道、没有周期"),
                ("Access route and lead time", "Where each dataset comes from and how many weeks it takes", "Lead time decides whether the schedule is feasible", "\"From some database\" with no route and no lead time"),
            ),
        ],
    },
    {
        "no": 1,
        "zh": "问题与文献",
        "en": "Question and literature",
        "auto_zh": "自动 7 项：python skills/literature/templates/check_matrix.py 你的文献矩阵.csv",
        "auto_en": "Seven mechanical checks: python skills/literature/templates/check_matrix.py your-matrix.csv",
        "cmd": "python skills/literature/templates/check_matrix.py <matrix.csv>",
        "items": [
            (
                ("一句话研究问题", "一个可以被数据推翻的句子，不是题目", "题目可以含糊，问题不行", "“关于教育与幸福感的研究”"),
                ("A one-sentence question", "A sentence the data could refute, not a title", "A title can stay vague, a question cannot", "\"Research on education and happiness\""),
            ),
            (
                ("点名最接近的那一篇", "指出离你最近的一篇，并写出你与它差在哪", "说不清差异就是没有贡献", "文献列表很长，但没有一篇被点名说“最近”"),
                ("Name the closest paper", "The nearest existing study, plus how yours differs", "If you cannot state the difference there is no contribution", "A long reading list, none of which is named as nearest"),
            ),
            (
                ("文献矩阵四列齐", "每行都有数据、样本、识别策略、主结论", "缺任何一列，就读不出可比性", "只记了作者、年份和结论"),
                ("Literature matrix has four columns", "Data, sample, identification strategy, main finding for every row", "Drop a column and comparability is gone", "Only author, year and finding recorded"),
            ),
            (
                ("零结果的含义", "如果系数是零，你怎么解释、说明了什么", "先写，才不会事后编故事", "从没想过零结果"),
                ("What a null means", "If the coefficient is zero, what you would conclude", "Writing it first stops you inventing a story afterwards", "The null case was never considered"),
            ),
            (
                ("贡献句", "明确对哪一个文献对话说话", "贡献是说给某一场对话听的", "“本文具有一定的理论意义和现实意义”"),
                ("A contribution sentence", "Which literature the paper is talking to", "A contribution addresses a conversation", "\"This paper has theoretical and practical significance\""),
            ),
            (
                ("每行都有可解析的标识", "DOI、卷期页码、或工作论文编号至少有一个", "没有标识的引用没法核，也没法让别人核", "只写了作者和年份，谁都定位不到是哪一篇"),
                ("A resolvable identifier on every row", "A DOI, a volume-issue-page, or a working-paper number", "An identifier is what lets you and a reader check the citation", "Author and year only, so nobody can locate the paper"),
            ),
            (
                ("至少三个不同来源", "期刊、工作论文、专著分开记", "只有一个来源的矩阵是读书笔记，不是文献地图", "四行全来自同一本刊"),
                ("At least three distinct sources", "Journals, working papers and books recorded separately", "A matrix with one source is notes, not a map", "All four rows come from one journal"),
            ),
        ],
    },
    {
        "no": 2,
        "zh": "识别设计",
        "en": "Identification",
        "auto_zh": "有自动检查器：skills/identification/templates/check_design.py（6 项）",
        "auto_en": "Mechanical checker: skills/identification/templates/check_design.py (six items)",
        "cmd": "python skills/identification/templates/check_design.py your-memo.md --lang en",
        "items": [
            (
                ("处理变量与对照组已定义", "两组分别是谁、怎么认出来", "两组认不出来，因果就没有比较对象", "只写处理组，对照组一句“其余样本”"),
                ("Treatment and comparison defined", "Who is in each group and how you tell them apart", "Without a comparison group there is nothing to compare", "Treatment defined, comparison left as \"the rest\""),
            ),
            (
                ("至少三条威胁，每条带检验", "每一条替代解释配一个能做出来的检验", "威胁不配检验，就只是自我安慰", "列了三条威胁，检验一栏写“未来研究”"),
                ("Three threats, each with a test", "Every alternative explanation gets a test you can actually run", "A threat with no test is a comfort blanket", "Three threats listed, each test column says \"future work\""),
            ),
            (
                ("写明什么结果会推翻设计", "给每条威胁写一条推翻条件", "不写，你就不会承认设计可能是错的", "只写“该威胁可能影响结果”"),
                ("State what would falsify it", "One falsifying pattern per threat", "Without it the design can never be wrong", "\"This threat may affect the results\""),
            ),
            (
                ("聚类层级及其理由", "聚到哪一级，为什么是那一级", "聚错层级，标准误就是假的", "写“聚类到个体”但没说为什么不能到城市"),
                ("Clustering level and why", "Which level you cluster at and the reason", "Wrong level and the standard errors are fiction", "Clustering at the individual with no argument against the city"),
            ),
            (
                ("一句话说清变异来源", "一句话写清处理变量的变化由什么带来", "说不清变异来源，等于没有识别", "用“政策实施带来差异”这类空话"),
                ("One sentence on the source of variation", "What generates the variation in treatment", "No source, no identification", "\"The policy created differences\" and nothing more"),
            ),
            (
                ("点名最脆弱的假设", "哪一个假设一破，整篇就不成立", "知道最弱的那一环，才知道先做哪个检验", "说“所有假设都很重要”"),
                ("Name the weakest assumption", "The assumption whose failure sinks the paper", "Knowing the weak link tells you which test comes first", "\"All assumptions are equally important\""),
            ),
        ],
    },
    {
        "no": 5,
        "zh": "表与图",
        "en": "Tables and figures",
        "auto_zh": "还没有自动检查器；下面七项对照 skills/tables-figures/SKILL.md 的验收清单",
        "auto_en": "No mechanical checker yet; the seven items below mirror the acceptance list in skills/tables-figures/SKILL.md",
        "cmd": "",
        "items": [
            (
                ("每个编号表图都有文件", "初稿里每一张都在 output/ 下有文件、在 table_index.csv 里有行", "没有文件的表图，等于没做过", "正文有表 5，output/ 里找不到"),
                ("Every numbered exhibit has a file", "Each one is under output/ and has a row in table_index.csv", "An exhibit without a file does not exist", "Table 5 in the draft, nothing in output/"),
            ),
            (
                ("一条命令重建", "清空 output/ 后能全部复现，不用手工改", "不能重建，三个月后自己也复现不了", "每次都要手动改列宽和表注"),
                ("One command rebuilds", "Empty output/ and one command reproduces everything", "If it cannot rebuild, nobody can reproduce it later", "Column widths and notes edited by hand every time"),
            ),
            (
                ("系数在上、标准误在下", "标准误紧贴系数下方，不放到最右一列", "右一列的排版会让人读错星号", "标准误单独一列，读者对不上系数"),
                ("Coefficients above standard errors", "Standard errors sit right below, not in a far-right column", "A far-right column makes stars easy to misread", "Standard errors in their own column, reader cannot pair them"),
            ),
            (
                ("表注在下方且五项齐全", "星号阈值、估计方法、样本、固定效应、聚类层级", "表注不齐，审稿人会逐条问", "表注只写“注：*** 表示 1% 显著”"),
                ("Note below, five elements", "Star thresholds, estimator, sample, fixed effects, clustering", "An incomplete note produces referee questions", "Only \"Note: *** denotes 1% significance\""),
            ),
            (
                ("不超版心", "排版后表图没有越出版心", "超出就会被要求重排", "宽表右边缘被裁掉"),
                ("Nothing overflows the margin", "After typesetting no exhibit crosses the text block", "Overflow forces a re-layout", "The right edge of a wide table is cut off"),
            ),
            (
                ("正文按编号引用，无悬空引用", "每张表图至少被引用一次，且引用都指向存在的表图", "悬空引用是审稿人最快的挑错点", "正文写“见表 6”，全文没有表 6"),
                ("Cross-referenced by number", "Every exhibit is cited at least once and no citation dangles", "A dangling reference is the fastest catch for a referee", "\"See Table 6\" with no Table 6"),
            ),
            (
                ("Stata 与 Python 逐位一致", "同一估计文件两条链导出的表数值相同", "两条链不一致，说明有一条错了", "两边的样本量差 3 个"),
                ("Stata and Python agree digit for digit", "Both chains export identical numbers from the same estimate", "If they differ, one of them is wrong", "Sample sizes differ by three"),
            ),
        ],
    },
    {
        "no": 6,
        "zh": "报告",
        "en": "Report",
        "auto_zh": "还没有自动检查器；下面七项对照 skills/report/SKILL.md 的验收清单",
        "auto_en": "No mechanical checker yet; the seven items below mirror the acceptance list in skills/report/SKILL.md",
        "cmd": "",
        "items": [
            (
                ("一条命令重建全部", "数据、表、图与两份报告都由一条命令产出", "手工步骤越多，越不可能复现", "先跑脚本，再手动贴一张图"),
                ("One command rebuilds everything", "Data, tables, figures and both reports from one command", "Every manual step is a reproduction hole", "Run the script, then paste one figure by hand"),
            ),
            (
                ("正文没有手打数字", "每个引用值都从 values.json 解析出来", "手打的数字改一处就会漏一处", "数字直接敲进正文，改表后忘了改正文"),
                ("No typed-in numbers", "Every cited value resolves from values.json", "A typed number breaks silently when the table changes", "Numbers typed into prose, stale after the table changes"),
            ),
            (
                ("构建前后 data/raw 哈希不变", "原始数据没有被脚本改写", "原始数据被改，等于证据被改", "清洗时直接覆盖了原始文件"),
                ("data/raw hashes unchanged", "The build never rewrites the raw data", "Rewriting raw data is rewriting the evidence", "Cleaning overwrote the raw file in place"),
            ),
            (
                ("中英两份数值一致", "每个共同表图的取值相同", "双语报告数值不一致，是最难看的错", "中文报告 0.42，英文报告 0.43"),
                ("Chinese and English agree", "Every shared exhibit carries the same value", "A mismatch across languages is the worst kind of error", "0.42 in the Chinese report, 0.43 in the English one"),
            ),
            (
                ("空 output 渲染零警告", "清空后能从头跑通", "有警告的渲染，交付时会再炸一次", "跑通了，但日志里有五条警告"),
                ("Clean render, no warnings", "An empty output/ runs through with no warnings", "A warning today is a failure at submission", "It runs but the log holds five warnings"),
            ),
            (
                ("provenance 写明三项", "数据快照日期、代码提交、软件环境", "这三项是复现的坐标", "只写“数据来自某某库”"),
                ("Provenance records three things", "Data snapshot date, code commit, software environment", "These three are the coordinates of reproduction", "\"Data from some database\" and nothing else"),
            ),
            (
                ("重建结果与已审阅版本一致", "若不同，每条差异在 build.log 里有解释", "差异不解释，就等于改了结果没说", "重建后数字变了，日志里没有一行说明"),
                ("Rebuild matches the reviewed version", "Any difference is explained in build.log", "An unexplained difference is an unreported change", "Numbers moved after rebuild, log says nothing"),
            ),
        ],
    },
    {
        "no": 7,
        "zh": "写作",
        "en": "Writing",
        "auto_zh": "有自动检查器：skills/writing/templates/check_abstract.py（7 项，针对摘要）",
        "auto_en": "Mechanical checker: skills/writing/templates/check_abstract.py (seven items, for the abstract)",
        "cmd": "python skills/writing/templates/check_abstract.py your-abstract.md --lang en",
        "items": [
            (
                ("字数区间", "英文 100–150 词、中文 200–300 字", "超了会被要求删，删的时候容易删掉识别策略", "中文摘要写了 480 字"),
                ("Length window", "100–150 words in English, 200–300 characters in Chinese", "Over the limit you will cut, and the cut usually removes the design", "A 480-character Chinese abstract"),
            ),
            (
                ("识别策略或方法", "摘要里点明用了什么方法", "方法不写，读者不知道能不能信", "只写“本文进行了实证分析”"),
                ("Method or design named", "The abstract says what identifies the effect", "Without it the reader cannot judge credibility", "\"This paper conducts an empirical analysis\""),
            ),
            (
                ("量化结果", "给出一个具体数量级", "只写方向和显著性，读者拿不走任何东西", "写“显著为正”但不给数值"),
                ("A magnitude", "One concrete number", "Direction and stars alone give the reader nothing to carry away", "\"Significantly positive\" with no number"),
            ),
            (
                ("自称方式", "中文用“本文”，英文用 this paper", "混用会让整段口径不一致", "中文写“我们认为”，英文写 we"),
                ("Self-reference", "\"本文\" in Chinese, \"this paper\" in English", "Mixing voices makes the register wobble", "Chinese that says \"we believe\", English that says we"),
            ),
            (
                ("没有第一人称", "摘要里不出现我们、笔者、I、we", "中文期刊的摘要惯例是第三人称", "We find that ..."),
                ("No first person", "No we, our, I in the abstract", "Chinese journals expect third person in the abstract", "We find that ..."),
            ),
            (
                ("关键词 3–5 个", "数量对，且是检索会用到的词", "太多太散，检索时谁都匹配不上", "关键词写了 9 个"),
                ("Three to five keywords", "The right count, and words people actually search", "Too many and nothing matches", "Nine keywords"),
            ),
            (
                ("分类号", "英文给 JEL codes，中文给中图分类号", "编辑部按它分派审稿人", "两边都空着"),
                ("Classification codes", "JEL codes in English, 中图分类号 in Chinese", "Editors route the paper by them", "Both left empty"),
            ),
        ],
    },
    {
        "no": 8,
        "zh": "审稿回复",
        "en": "Referee response",
        "auto_zh": "有自动检查器：skills/review/templates/check_response.py（5 项）",
        "auto_en": "Mechanical checker: skills/review/templates/check_response.py (five items)",
        "cmd": "python skills/review/templates/check_response.py your-letter.md --lang en",
        "items": [
            (
                ("意见与回应成对", "每条意见后面都有对应的回应", "漏一条，第二轮就会被打回来", "五条意见只回了三条"),
                ("One response per comment", "Every comment has an answer right after it", "One gap and the next round sends it back", "Five comments, three answers"),
            ),
            (
                ("指明改在何处", "给出页码、节号或表图号", "不说改在哪，等于说“我改了，你找”", "只写“已修改相关内容”"),
                ("Point to where it changed", "Page, section, table or figure number", "Without a pointer you are asking the referee to hunt", "\"Relevant text has been revised\""),
            ),
            (
                ("至少一条不改并说明理由", "该拒绝就拒绝，并给出理由", "全盘照改，会被看成没有判断力", "所有意见一律“已按要求修改”"),
                ("At least one pushback with a reason", "Declining where declining is right, with an argument", "Accepting everything reads as having no judgement", "Every comment met with \"revised as requested\""),
            ),
            (
                ("没有情绪化措辞", "不出现贬低审稿人的话", "一句气话会让整封信失去分量", "写“审稿人显然误读了本文”"),
                ("No emotive wording", "Nothing that belittles the referee", "One sharp line costs the whole letter its weight", "\"The referee has obviously misread the paper\""),
            ),
            (
                ("有总述段", "第一条意见之前先讲清这一轮改了什么", "没有总述，审稿人看不出你抓没抓到重点", "直接进入第 1 条意见"),
                ("An opening summary", "Before comment one, what this round changed overall", "Without it the referee cannot see whether you saw the point", "Straight into comment one"),
            ),
        ],
    },
]


def find(no):
    for stage in STAGES:
        if stage["no"] == no:
            return stage
    return None


def render(stage, lang):
    zh = lang == "zh"
    title = ("【第 %d 段 · %s】" % (stage["no"], stage["zh"])) if zh else ("Stage %d · %s" % (stage["no"], stage["en"]))
    lines = [title, (stage["auto_zh"] if zh else stage["auto_en"])]
    if stage["cmd"]:
        lines.append(("命令：" if zh else "Command: ") + stage["cmd"])
    lines.append("")
    for i, (item_zh, item_en) in enumerate(stage["items"], 1):
        title_i, what, why, fail = item_zh if zh else item_en
        lines.append("[%d] %s" % (i, title_i))
        lines.append(("    查什么：" if zh else "    Looks at: ") + what)
        lines.append(("    为什么：" if zh else "    Why: ") + why)
        lines.append(("    不合格长什么样：" if zh else "    Failing answer: ") + fail)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def listing(lang):
    zh = lang == "zh"
    out = ["八道工序的检查单（用 python scripts/explain.py <段号> 看某一段）", ""] if zh else [
        "Checks per stage (use python scripts/explain.py <stage>)",
        "",
    ]
    for stage in STAGES:
        head = ("第 %d 段" % stage["no"]) if zh else ("Stage %d" % stage["no"])
        name = stage["zh"] if zh else stage["en"]
        mark = ("自动 %d 项" % len(stage["items"])) if (zh and stage["cmd"]) else (
            ("%d checks" % len(stage["items"])) if (not zh and stage["cmd"]) else (
                ("人工 %d 项" % len(stage["items"])) if zh else ("%d items, by hand" % len(stage["items"]))
            )
        )
        out.append("  %-9s %-14s %s" % (head, name, mark))
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Explain in plain language what each stage's checks ask for.",
    )
    parser.add_argument("stage", nargs="?", help="stage number, 0 to 8")
    parser.add_argument("--lang", choices=("en", "zh"), default="zh", help="language of the output")
    parser.add_argument("--list", action="store_true", help="list every stage instead")
    args = parser.parse_args(argv)

    if args.list or args.stage is None:
        sys.stdout.write(listing(args.lang))
        return 0 if args.list else 2

    try:
        no = int(args.stage)
    except ValueError:
        sys.stderr.write(("段号必须是 0 到 8 的整数\n" if args.lang == "zh" else "Stage must be an integer from 0 to 8\n"))
        return 2
    stage = find(no)
    if stage is None:
        sys.stderr.write(
            ("没有第 %d 段。先跑 python scripts/explain.py --list 看有哪些段\n" % no)
            if args.lang == "zh"
            else ("No stage %d. Run python scripts/explain.py --list first\n" % no)
        )
        return 2
    sys.stdout.write(render(stage, args.lang))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
