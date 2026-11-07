#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate.py — 八段闸门：每一步都要一句人给的回答才能往下走，没回答就停在那里。

状态存在当前目录的 `.econ-kit/gate.json`（跟你的研究项目一起，不进仓库）。

    python scripts/gate.py start "我现在想研究家庭收入对阶层认同的影响"
    python scripts/gate.py status          # 现在停在哪一段、缺什么、下一步允许做什么
    python scripts/gate.py ask             # 打印这一段要问的那句话
    python scripts/gate.py pass "答复原文"  # 只有给了回答才放行，记时间与答复
    python scripts/gate.py block "为什么停"

退出码：0 可以继续 / 1 被闸门挡住（还在等回答或产物不齐）/ 2 用法错。
"""

import argparse
import io
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

STATE_DIR = ".econ-kit"
STATE_FILE = os.path.join(STATE_DIR, "gate.json")
SPEC_FILE = os.path.join(STATE_DIR, "spec.md")
AGENTS_FILE = "AGENTS.md"
PROTOCOL_FILE = os.path.join(STATE_DIR, "PROTOCOL.md")

PROTOCOL = """
# 这个目录是一个研究项目

三行契约，任何 AI 助手（DSH / Codex / Claude Code / Cursor）进这个目录都要先读：

1. **开工前先看闸门**：`python <kit>/scripts/gate.py status`。没有 `.econ-kit/gate.json`，
   先 `gate.py start "<题目>"`；没开闸门不许产出任何研究文件。
2. **每一步先给规格再动手**：`gate.py` 放行前要求 `.econ-kit/spec.md` 存在，
   它由 `python <kit>/scripts/spec.py "<原话>"` 生成——那份规格与提示词草稿要先给用户看、改完再开工。
3. **每段结束要一句人给的回答**：`gate.py pass "<用户的原话>"`；少于八个字不算回答。
   `--force` 可以跳过，但缺口会记进 `gate.json`，看板上会标出来。

看板数据 `.econ-kit/dashboard.json` 由 `gate.py` / `spec.py` 自动重写，不需要手跑。
"""

AGENTS_SECTION = """
<!-- econ-research-kit:begin -->
## 研究项目契约（econ-research-kit 自动写入）

本目录是一个研究项目。开工前先跑 `python <kit>/scripts/gate.py status`；
没有闸门状态先 `gate.py start "<题目>"`；放行前必须有 `.econ-kit/spec.md`。

完整契约见 `.econ-kit/PROTOCOL.md`。不要删除本段——删了就等于关掉闸门。
<!-- econ-research-kit:end -->
"""



def _refresh_panel():
    """状态一变就把看板数据重写一遍（失败不吭声，闸门优先）。"""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import dashboard
        dashboard.write_panel_near(os.path.dirname(here))
    except Exception:
        pass

STAGES = [
    (0, "可行性", "feasibility", "这题到底做不做得下去",
     "这题按这个分析单元和处理变量，你认为数据能拿到吗？哪一个最可能卡住？"),
    (1, "问题与文献", "literature", "这个缺口是真的吗",
     "这个缺口陈述你认吗？审稿人说「已有文献做过类似的事」时，你用哪一句回？"),
    (2, "识别设计", "identification", "凭什么说是因果",
     "这四条威胁里，哪一条你现在没法检验？确定带着它往下走吗？"),
    (3, "数据", "data-prep", "数据能不能支撑这个设计",
     "这些清洗动作与变量口径，你认吗？哪一条要改？"),
    (4, "估计", "estimation", "跑出来的系数怎么读",
     "报告的那一级设定就是这一级吗？显著性换口气的那一级怎么处理？"),
    (5, "表与图", "tables-figures", "结果长成能投稿的样子",
     "表里的星号、标准误层级、表注，按你目标期刊的习惯吗？"),
    (6, "报告", "report", "把结果讲成一段可复现的话",
     "报告里「还缺什么」那一段，和你心里想的一致吗？"),
    (7, "写作", "writing", "写进稿子里",
     "摘要里识别策略那一句，是你愿意署名的说法吗？"),
    (8, "审稿回复", "review", "回应审稿人",
     "哪一条你决定不改？理由写清楚了吗？"),
]

ARTIFACTS = {
    0: ["feasibility-memo.md"],
    1: ["lit-matrix.csv"],
    2: ["identification-memo.md"],
    3: ["cleaning-log.md"],
    4: ["estimation-results.md"],
    5: ["table1.tex"],
    6: ["report.md"],
    7: ["abstract.md"],
    8: ["response-letter.md"],
}

MIN_ANSWER = 8  # 少于 8 个字符的回答不算回答（"好""行""嗯"不是确认）

T = {
    "zh": {
        "no_state": "还没有闸门状态。先跑：python scripts/gate.py start \"<你的题目>\"",
        "started": "已开闸门：%s\n当前停在第 %d 段（%s）。先做完这一段，再跑 gate.py pass \"<你的回答>\"。",
        "title": "八段闸门状态",
        "col": "| 段 | 这一段算什么 | 工序 | 状态 |",
        "now": "现在停在：第 %d 段 %s —— %s",
        "need_answer": "要往下走，需要你一句回答（跑 gate.py ask 看问的是哪句）。",
        "all_done": "八段都过了。剩下的是写正文和投稿，不归闸门管。",
        "ask": "第 %d 段（%s）要问你的：\n\n  %s\n\n答完跑：python scripts/gate.py pass \"<你的回答>\"",
        "passed": "第 %d 段放行。记录：%s",
        "too_short": "这句话太短，不算回答（至少 %d 个字）。真确认一下，别写「好」。",
        "no_spec": "还没有任务规格 `.econ-kit/spec.md`。先把规格与提示词草稿给用户看：\n    python scripts/spec.py \"<用户的原话>\"\n改完再 pass；确实要跳过，用 --force 并在回答里写清为什么。",
        "need_spec": "下一步：先把规格与提示词草稿给用户看（spec.py），不是直接开工。",
        "missing_art": "第 %d 段还缺产物：%s\n补齐再 pass；确实要先跳过，用 gate.py pass \"<回答>\" --force 并在这里写清为什么。",
        "forced": "第 %d 段带缺口放行（产物缺：%s）。这条会记在案上。",
        "blocked": "已标记暂停。原因：%s",
        "done": "八段全部通过。",
        "next_stage": "下一步：第 %d 段 %s —— %s",
    },
    "en": {
        "no_state": "No gate state yet. Run: python scripts/gate.py start \"<your question>\"",
        "started": "Gate opened for: %s\nStopped at stage %d (%s). Finish it, then run gate.py pass \"<your answer>\".",
        "title": "Eight-stage gate status",
        "col": "| Stage | What it decides | Skill | Status |",
        "now": "Now at: stage %d %s — %s",
        "need_answer": "To move on I need one answer from you (run gate.py ask to see the question).",
        "all_done": "All eight stages passed. What remains is drafting and submission, which the gate does not police.",
        "ask": "Stage %d (%s) asks you:\n\n  %s\n\nAfter answering: python scripts/gate.py pass \"<your answer>\"",
        "passed": "Stage %d passed. Recorded: %s",
        "too_short": "That is too short to count as an answer (min %d characters). Confirm for real.",
        "no_spec": "No task spec yet (`.econ-kit/spec.md`). Show the spec and prompt draft to the user first:\n    python scripts/spec.py \"<the user's words>\"\nThen pass; if you really must skip, use --force and write down why.",
        "need_spec": "Next: show the spec and prompt draft to the user (spec.py), do not start producing yet.",
        "missing_art": "Stage %d is missing artifacts: %s\nProduce them, or use --force and write down why you skipped.",
        "forced": "Stage %d passed with gaps (%s). This is on the record.",
        "blocked": "Marked as blocked. Reason: %s",
        "done": "All eight stages passed.",
        "next_stage": "Next: stage %d %s — %s",
    },
}


def load():
    if not os.path.exists(STATE_FILE):
        return None
    with io.open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def write_protocol():
    """把契约落到项目里：.econ-kit/PROTOCOL.md，并在 AGENTS.md 里留一个指针段。"""
    if not os.path.isdir(STATE_DIR):
        os.makedirs(STATE_DIR)
    with io.open(PROTOCOL_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(PROTOCOL)
    marker = "<!-- econ-research-kit:begin -->"
    body = ""
    if os.path.exists(AGENTS_FILE):
        with io.open(AGENTS_FILE, encoding="utf-8") as f:
            body = f.read()
    if marker not in body:
        with io.open(AGENTS_FILE, "a", encoding="utf-8", newline="\n") as f:
            f.write(AGENTS_SECTION)


def status_card(cur):
    """三行状态卡：现在哪一段 / 该产什么 / 停在哪。"""
    st = STAGES[cur] if cur < len(STAGES) else None
    art = ARTIFACTS.get(cur, [])
    print("")
    print("段   : [%d] %s" % (cur, st[1] if st else "done"))
    print("产物 : " + ("、".join(art) if art else "—"))
    print("停在哪: 等用户回答 `gate.py pass \"<原话>\"`" if st else "八段全部通过")
    print("")

def save(st):
    if not os.path.isdir(STATE_DIR):
        os.makedirs(STATE_DIR)
    with io.open(STATE_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    _refresh_panel()


def stage_row(i):
    return STAGES[i]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Eight-stage gate: nothing moves without a human answer.")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["start", "status", "ask", "pass", "block", "done", "reset"])
    ap.add_argument("text", nargs="?", default="")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--force", action="store_true", help="产物缺也放行（会记录在案）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    t = T["zh" if a.lang == "zh" else "en"]

    if a.cmd == "start":
        if not a.text.strip():
            print(t["no_state"])
            return 2
        st = {"question": a.text.strip(), "current": 0, "blocked": False,
              "stages": [{"stage": s[0], "name": s[1], "skill": s[2], "status": "open",
                          "answer": "", "answered_at": "", "forced_gaps": []} for s in STAGES]}
        save(st)
        write_protocol()
        print(t["started"] % (st["question"], 0, STAGES[0][1]))
        print(t["need_spec"])
        status_card(0)
        return 1

    if a.cmd == "reset":
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            print("已清除闸门状态。" if a.lang == "zh" else "Gate state cleared.")
            return 0
        print(t["no_state"])
        return 1

    st = load()
    if st is None:
        print(t["no_state"])
        return 2

    cur = st["current"]
    if a.cmd == "status" or a.cmd == "done":
        _refresh_panel()
        if a.json:
            print(json.dumps(st, ensure_ascii=False, indent=2))
            return 0 if cur >= len(STAGES) else 1
        print("# " + t["title"])
        print("")
        print("> " + st["question"])
        print("")
        print(t["col"])
        print("|---|---|---|---|")
        for s, rec in zip(STAGES, st["stages"]):
            mark = {"open": "⏳ 等回答" if a.lang == "zh" else "open",
                    "passed": "✅ 通过" if a.lang == "zh" else "passed",
                    "forced": "⚠️ 带缺口放行" if a.lang == "zh" else "forced"}.get(rec["status"], rec["status"])
            print("| %d | %s | %s | %s |" % (s[0], s[3], s[2], mark))
        print("")
        if cur >= len(STAGES):
            print(t["all_done"])
            return 0
        print(t["now"] % (cur, STAGES[cur][1], STAGES[cur][3]))
        if st.get("blocked"):
            print(("（已标记暂停）" if a.lang == "zh" else "(blocked)"))
        print(t["need_answer"])
        return 1

    if cur >= len(STAGES):
        print(t["all_done"])
        return 0

    s = STAGES[cur]
    rec = st["stages"][cur]

    if a.cmd == "ask":
        print(t["ask"] % (cur, s[1], s[4]))
        return 1

    if a.cmd == "block":
        st["blocked"] = True
        rec["blocked_reason"] = a.text.strip()
        st.setdefault("block_log", []).append({"stage": cur, "reason": a.text.strip()})
        save(st)
        print(t["blocked"] % (a.text.strip() or "-"))
        return 1

    if a.cmd == "pass":
        ans = a.text.strip()
        if len(ans) < MIN_ANSWER:
            print(t["too_short"] % MIN_ANSWER)
            return 1
        missing = [p for p in ARTIFACTS.get(cur, []) if not os.path.exists(p)]
        if not os.path.exists(SPEC_FILE):
            if not a.force:
                print(t["no_spec"])
                status_card(cur)
                return 1
            missing = missing + ["spec.md（没有规格草稿）"]
        if missing and not a.force:
            print(t["missing_art"] % (cur, "、".join(missing)))
            return 1
        import datetime
        rec["status"] = "forced" if missing else "passed"
        rec["answer"] = ans
        rec["answered_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        rec["forced_gaps"] = missing
        st["blocked"] = False
        st["current"] = cur + 1
        save(st)
        if missing:
            print(t["forced"] % (cur, "、".join(missing)))
        else:
            print(t["passed"] % (cur, ans[:60]))
        if st["current"] < len(STAGES):
            n = STAGES[st["current"]]
            print(t["next_stage"] % (n[0], n[1], n[3]))
        else:
            print(t["done"])
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
