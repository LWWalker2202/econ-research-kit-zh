#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec.py — 把一句模糊的研究需求翻成「任务规格 + 提示词草稿」，先给人看，人改了再往下走。

用法：
    python scripts/spec.py "我想研究教育对幸福感的影响"
    python scripts/spec.py "..." --lang en --out spec-education.md
    python scripts/spec.py "..." --json

退出码：0 = 四槽位齐了，可以往下走；1 = 有槽位缺，先回答那三问；2 = 用法错。

它不联网、不调模型：只做分词与查表，所以同一个输入永远给同一份草稿。
"""

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:
    import preflight  # 同目录，复用四槽位识别
except Exception:  # pragma: no cover
    preflight = None

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

STAGES = [
    (0, "可行性", "feasibility", "这题到底做不做得下去"),
    (1, "问题与文献", "literature", "这个缺口是真的吗"),
    (2, "识别设计", "identification", "凭什么说是因果"),
    (3, "数据", "data-prep", "数据能不能支撑这个设计"),
    (4, "估计", "estimation", "跑出来的系数怎么读"),
    (5, "表与图", "tables-figures", "结果长成能投稿的样子"),
    (6, "报告", "report", "把结果讲成一段可复现的话"),
    (7, "写作", "writing", "写进稿子里"),
    (8, "审稿回复", "review", "回应审稿人"),
]

ROUTES = {
    0: ["可行性", "做不做得下去", "能不能做", "数据有没有", "值不值得做", "feasib"],
    1: ["文献", "有没有人做过", "缺口", "综述", "literature", "gap", "contribution"],
    2: ["识别", "因果", "内生", "双重差分", "did", "工具变量", "iv", "断点", "rdd",
        "合成控制", "事件研究", "平行趋势", "identification", "causal"],
    3: ["清洗", "数据", "变量", "合并", "缺失", "缩尾", "样本", "口径", "clean", "data"],
    4: ["回归", "估计", "系数", "标准误", "聚类", "稳健", "设定", "regression", "estimate"],
    5: ["表", "图", "三线表", "画", "导出", "table", "figure", "plot"],
    6: ["报告", "汇总", "汇报", "report", "summar"],
    7: ["写", "引言", "摘要", "投稿", "润色", "write", "abstract", "draft"],
    8: ["审稿", "回复", "referee", "response", "修改意见", "rebuttal"],
}

ARTIFACTS = {
    0: "feasibility-memo.md、feasibility-check.csv、data-access-plan.md、stop-criteria.md",
    1: "search-plan.md、lit-matrix.csv、lit-matrix-check.txt",
    2: "identification-memo.md、identification-check.txt",
    3: "cleaning-decisions.md、cleaning-log.md、clean_panel.csv",
    4: "spec-ladder.md、estimation-results.md、estimation-results.json",
    5: "table1.tex、figure1.pdf、table-check.txt",
    6: "report.md、report-check.txt",
    7: "abstract.md、abstract-check.txt",
    8: "response-matrix.md、response-letter.md、review-check.txt",
}

CONFIRM = {
    0: "这题按这个分析单元和处理变量，你认为数据能拿到吗？哪一个是最可能卡住的环节？",
    1: "这个缺口陈述你认吗？如果审稿人说「已经有文献做过类似的事」，你打算用哪一句回？",
    2: "这四个槽位里，哪一条威胁是你现在没法检验的？确定要继续吗？",
    3: "这些清洗动作与变量口径，你认吗？哪一条要改？",
    4: "报告的那一级设定，是现在定下来的这一级吗？显著性换口气的那一级怎么处理？",
    5: "表里的星号、标准误层级、表注，按你目标期刊的习惯吗？",
    6: "报告的「还缺什么」那一段，读者看到的版本和你心里的一致吗？",
    7: "摘要里识别策略那一句，是你愿意署名的说法吗？",
    8: "哪一条你决定不改？理由写清楚了吗？",
}

SLOT_LABEL = {
    "unit": ("分析单元", "unit of analysis"),
    "treatment": ("处理变量", "treatment variable"),
    "outcome": ("结果变量", "outcome variable"),
    "comparison": ("对照组", "comparison group"),
}
STATUS_LABEL = {
    "given": ("你给的", "from you"),
    "implied": ("我猜的", "inferred"),
    "missing": ("空着", "missing"),
}

T = {
    "zh": {
        "title": "任务规格草稿（先看这份，改完再动手）",
        "you_said": "你说的原话",
        "slots": "四个槽位：我读到的和你还没说的",
        "route": "我猜你要进的是第 %d 段：%s（%s）",
        "route_none": "从这句话里读不出你要进哪一段，所以默认从第 0 段开始反问。",
        "draft": "提示词草稿（可以直接复制，也可以改）",
        "confirm": "动手之前，我要你确认的三件事",
        "accept": "做完之后按这几条验收",
        "next": "下一步可以跑的命令",
        "not_model": "这份草稿是查表生成的不是模型写的：同一个输入永远给同一份，所以你可以把它当版本起点。",
    },
    "en": {
        "title": "Task spec draft (read this first, edit it, then start)",
        "you_said": "What you said",
        "slots": "Four slots: what I read, and what you have not said yet",
        "route": "I would enter stage %d: %s (%s)",
        "route_none": "I cannot tell which stage you mean, so I default to stage 0 and ask.",
        "draft": "Prompt draft (copy it, or edit it)",
        "confirm": "Three things to confirm before any work starts",
        "accept": "Acceptance when it is done",
        "next": "Commands you could run next",
        "not_model": "This draft comes from a lookup table, not from a model: same input, same draft, so you can version it.",
    },
}


def pick_stage(text):
    low = text.lower()
    best, hits = 0, []
    for stage, keys in ROUTES.items():
        n = sum(1 for k in keys if k.lower() in low)
        if n > best:
            pass
        hits.append((n, stage))
    hits.sort(key=lambda x: (-x[0], x[1]))
    best = hits[0]
    if best[0] == 0:
        return None, []
    return best[1], [k for k in ROUTES[best[1]] if k.lower() in low]


def draft_prompt(text, slots, stage, lang):
    zh = lang == "zh"
    st = [s for s in STAGES if s[0] == stage]
    stage_name = st[0][1] if zh else st[0][2]
    lines = []
    if zh:
        lines.append("# 角色")
        lines.append("你是经济学实证研究的助手，只负责第 %d 段（%s）。不要替我判断研究值不值得做，也不要替我编数据。" % (stage, stage_name))
        lines.append("")
        lines.append("# 上下文")
        lines.append("- 我的题目：%s" % text)
        for key in ("unit", "treatment", "outcome", "comparison"):
            status, val = slots.get(key, ("missing", ""))
            label = SLOT_LABEL[key][0]
            if status == "missing":
                lines.append("- %s：【待填】" % label)
            else:
                lines.append("- %s：%s（%s）" % (label, val, STATUS_LABEL[status][0]))
        lines.append("")
        lines.append("# 任务")
        lines.append("按 %s 的步骤做，产出：%s。" % (stage_name, ARTIFACTS[stage]))
        lines.append("")
        lines.append("# 约束")
        lines.append("- 缺的信息写成【待填】，不要猜；猜了要单独标出来。")
        lines.append("- 每次回答开头先写三行状态头：段号与段名 / 这一步只做什么 / 产出哪个文件、要不要我确认。")
        lines.append("- 有数字就给出来源，没来源就不要给数字。")
        lines.append("")
        lines.append("# 输出格式")
        lines.append("先给一段状态头，再给这一段的产物，最后给一句确认问话。")
        lines.append("")
        lines.append("# 自检")
        lines.append("跑 explain.py %d 的检查项，逐条打勾，没过就说没过。" % stage)
    else:
        lines.append("# Role")
        lines.append("You are an empirical-economics assistant working only on stage %d (%s). Do not decide for me whether the project is worth doing, and never invent data." % (stage, stage_name))
        lines.append("")
        lines.append("# Context")
        lines.append("- My question: %s" % text)
        for key in ("unit", "treatment", "outcome", "comparison"):
            status, val = slots.get(key, ("missing", ""))
            label = SLOT_LABEL[key][1]
            if status == "missing":
                lines.append("- %s: [to fill]" % label)
            else:
                lines.append("- %s: %s (%s)" % (label, val, STATUS_LABEL[status][1]))
        lines.append("")
        lines.append("# Task")
        lines.append("Follow the %s procedure and produce: %s." % (stage_name, ARTIFACTS[stage]))
        lines.append("")
        lines.append("# Constraints")
        lines.append("- Write [to fill] where information is missing; never guess silently.")
        lines.append("- Start every answer with the three-line status header: stage / what this step does / artifact and whether confirmation is needed.")
        lines.append("- Give a source for every number; give no number you cannot source.")
        lines.append("")
        lines.append("# Output")
        lines.append("Status header first, then the artifact, then one confirmation question.")
        lines.append("")
        lines.append("# Self-check")
        lines.append("Run the stage-%d checks from explain.py and tick them; say so when one fails." % stage)
    return "\n".join(lines)


def render(text, slots, todo, questions, stage, matched, lang):
    zh = lang == "zh"
    t = T["zh" if zh else "en"]
    out = []
    out.append("# " + t["title"])
    out.append("")
    out.append("## " + t["you_said"])
    out.append("")
    out.append("> " + text.strip())
    out.append("")
    out.append("## " + t["slots"])
    out.append("")
    if zh:
        out.append("| 槽位 | 状态 | 值 |")
        out.append("|---|---|---|")
    else:
        out.append("| Slot | Status | Value |")
        out.append("|---|---|---|")
    for key in ("unit", "treatment", "outcome", "comparison"):
        status, val = slots.get(key, ("missing", ""))
        out.append("| %s | %s | %s |" % (SLOT_LABEL[key][0 if zh else 1],
                                          STATUS_LABEL[status][0 if zh else 1], val or "—"))
    out.append("")
    if todo:
        out.append(("**还差 %d 项。先回答这几个问题，答完再往下：**" if zh
                    else "**%d slot(s) missing. Ask me these first:**") % len(todo))
        out.append("")
        for i, q in enumerate(questions, 1):
            out.append("%d. %s" % (i, q))
        out.append("")
    else:
        out.append(("四个槽位都齐了：可以直接进下一步。" if zh
                    else "All four slots are there: you can move on."))
        out.append("")
    if stage is None:
        out.append("## " + t["route_none"])
    else:
        out.append("## " + t["route"] % (stage, STAGES[stage][1 if zh else 2], STAGES[stage][3]))
        if matched:
            out.append("")
            out.append(("命中词：" if zh else "Matched words: ") + "、".join(matched))
    out.append("")
    out.append("## " + t["draft"])
    out.append("")
    out.append("```text")
    out.append(draft_prompt(text, slots, stage if stage is not None else 0, lang))
    out.append("```")
    out.append("")
    out.append("## " + t["confirm"])
    out.append("")
    out.append("1. " + CONFIRM[stage if stage is not None else 0])
    out.append("2. " + ("这份草稿里，哪一句你不认同？（不认同的先改，改完再跑。）" if zh
                        else "Which line of the draft do you disagree with? Edit it first."))
    out.append("3. " + ("这一段做完，验收按什么算过？（默认按 explain.py 的检查项。）" if zh
                        else "What counts as done here? (Default: the checks in explain.py.)"))
    out.append("")
    out.append("## " + t["accept"])
    out.append("")
    if zh:
        out.append("跑 `python scripts/explain.py %d --lang zh`，逐条看「查什么 / 为什么 / 不合格长什么样」。" %
                   (stage if stage is not None else 0))
        out.append("")
        out.append("这一段要留下的文件：`%s`。" % ARTIFACTS[stage if stage is not None else 0])
    else:
        out.append("Run `python scripts/explain.py %d --lang en` and read every check." %
                   (stage if stage is not None else 0))
        out.append("")
        out.append("Artifacts to leave behind: `%s`." % ARTIFACTS[stage if stage is not None else 0])
    out.append("")
    out.append("## " + t["next"])
    out.append("")
    if zh:
        out.append("```text")
        out.append('python scripts/preflight.py "%s" --lang zh' % text.strip())
        out.append("python scripts/stage.py %d --lang zh" % (stage if stage is not None else 0))
        out.append("python scripts/explain.py %d --lang zh" % (stage if stage is not None else 0))
        if stage == 1:
            out.append('python skills/literature/templates/litsearch.py "keywords" --min-tier A --lang zh')
        if stage == 3:
            out.append("python skills/data-prep/templates/clean_panel.py --decisions --lang zh")
        if stage == 4:
            out.append("python skills/estimation/templates/estimate_main.py --ladder --lang zh")
        out.append("```")
    else:
        out.append("```text")
        out.append('python scripts/preflight.py "%s" --lang en' % text.strip())
        out.append("python scripts/stage.py %d --lang en" % (stage if stage is not None else 0))
        out.append("python scripts/explain.py %d --lang en" % (stage if stage is not None else 0))
        if stage == 1:
            out.append('python skills/literature/templates/litsearch.py "keywords" --min-tier A --lang en')
        if stage == 3:
            out.append("python skills/data-prep/templates/clean_panel.py --decisions --lang en")
        if stage == 4:
            out.append("python skills/estimation/templates/estimate_main.py --ladder --lang en")
        out.append("```")
    out.append("")
    out.append("---")
    out.append("")
    out.append(t["not_model"])
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Turn one fuzzy sentence into a task spec and a prompt draft you can edit.")
    ap.add_argument("question", nargs="?", default="", help="你的需求，一句话")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--out", default="", help="写到这个文件（默认打印到屏幕）")
    ap.add_argument("--no-write", action="store_true", help="不写 .econ-kit/spec.md")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON，方便别的脚本接")
    a = ap.parse_args(argv)

    if not a.question.strip():
        ap.print_help()
        return 2
    if preflight is None:
        print("preflight.py 不在同目录，没法识别四槽位。" if a.lang == "zh"
              else "preflight.py is not next to spec.py; cannot read the four slots.")
        return 2

    text = a.question.strip()
    slots, todo, questions = preflight.analyse(text, a.lang)
    stage, matched = pick_stage(text)

    if a.json:
        payload = {
            "question": text,
            "stage": stage,
            "stage_name": STAGES[stage][1 if a.lang == "zh" else 2] if stage is not None else "",
            "matched": matched,
            "slots": {k: {"status": v[0], "value": v[1]} for k, v in slots.items()},
            "missing": todo,
            "questions": questions,
            "artifacts": ARTIFACTS[stage if stage is not None else 0],
            "prompt": draft_prompt(text, slots, stage if stage is not None else 0, a.lang),
        }
        body = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        body = render(text, slots, todo, questions, stage, matched, a.lang)

    if a.out:
        with io.open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        print(("已写出：%s" if a.lang == "zh" else "wrote: ") % a.out)
    else:
        print(body)

    if not a.no_write:
        state_dir = ".econ-kit"
        if not os.path.isdir(state_dir):
            os.makedirs(state_dir)
        target = os.path.join(state_dir, "spec.md")
        with io.open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(body + "\n")
        print("")
        print(("规格草稿已落盘：%s" if a.lang == "zh" else "spec written: ") % target)
        print("下一步：把这份草稿给用户改；改完再 gate.py pass \"<用户的原话>\"" if a.lang == "zh"
              else "Next: let the user edit it, then gate.py pass \"<the user's words>\"")
    print("")
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import dashboard
        dashboard.write_panel_near(os.path.dirname(here), lang=a.lang)
    except Exception:
        pass
    return 0 if not todo else 1


if __name__ == "__main__":
    sys.exit(main())
