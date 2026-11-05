#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""recall.py — 开新会话的第一件事：把「项目在哪、上次做了什么、还欠什么」一次说清。

为什么要有这个脚本：会话会被压缩，模型会忘事；新会话更是从零开始。
所以状态不能靠记性，只能靠文件。这个脚本就是那个文件的读法。

用法：
    python scripts/recall.py
    python scripts/recall.py --lang en
    python scripts/recall.py --brief      # 只打印五行
    python scripts/recall.py --json       # 机器读

退出码：0 正常 / 2 找不到账本
"""

import argparse
import io
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TEXT = {
    "zh": {
        "head": "【项目现状】",
        "about": "这是什么",
        "ver": "版本",
        "dev": "开发版",
        "rel": "最近发布",
        "stop": "上次停在",
        "next": "下一步",
        "done": "已完成步骤",
        "todo": "未完成步骤",
        "gaps": "没做完的事",
        "decisions": "决策记录",
        "cmds": "常用命令",
        "read_first": "先读这两页",
        "none": "（无）",
        "cmd_recall": "python scripts/recall.py                          # 我在哪",
        "cmd_preflight": "python scripts/preflight.py \"我现在想研究……的影响\"   # 该问什么",
        "cmd_stage": "python scripts/stage.py 3                           # 这一段停下来要问的那句话",
        "cmd_gate": "python scripts/gate.py 3                            # 这一段的确认点过没过",
        "cmd_review": "python scripts/review.py A2                         # 这一步做完了吗",
        "hint": "提醒：任何研究类请求，先跑 preflight，再动手。",
    },
    "en": {
        "head": "[Project state]",
        "about": "What this is",
        "ver": "Version",
        "dev": "In progress",
        "rel": "Last release",
        "stop": "Last stop",
        "next": "Next",
        "done": "Steps done",
        "todo": "Steps open",
        "gaps": "Open gaps",
        "decisions": "Decisions",
        "cmds": "Useful commands",
        "read_first": "Read these first",
        "none": "(none)",
        "cmd_recall": "python scripts/recall.py                          # where am I",
        "cmd_preflight": "python scripts/preflight.py \"I want to study the effect of ...\"",
        "cmd_stage": "python scripts/stage.py 3                           # the question this stage must ask",
        "cmd_gate": "python scripts/gate.py 3                            # did this stage get confirmed",
        "cmd_review": "python scripts/review.py A2                         # is this step done",
        "hint": "Reminder: for any research request, run preflight before doing anything.",
    },
}


def load():
    p = os.path.join(ROOT, "state", "progress.json")
    if not os.path.exists(p):
        print("找不到 state/progress.json —— 这个仓库的状态账本丢了。" if True else "", file=sys.stderr)
        sys.exit(2)
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(add_help=True, description="打印项目现状：版本、上次停在哪、还欠什么")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.json:
        print(json.dumps(load(), ensure_ascii=False, indent=2))
        return 0

    d = load()
    t = TEXT[a.lang]
    en = a.lang == "en"
    steps = d.get("steps") or []
    done = [s for s in steps if s.get("status") == "done"]
    todo = [s for s in steps if s.get("status") != "done"]
    gaps = [g for g in (d.get("gaps") or []) if g.get("status") == "open"]
    decs = d.get("decisions") or []

    print(t["head"])
    print("  %s: %s" % (t["about"], d.get("about_en") if en else d.get("about")))
    print("  %s: %s（%s %s）｜ %s: %s" % (t["ver"], d.get("version", "?"), t["rel"],
                                          d.get("released", "?"), t["dev"], d.get("version", "?")))
    last = done[-1] if done else {}
    nxt = todo[0] if todo else {}
    print("  %s: [%s] %s" % (t["stop"], last.get("id", "-"),
                              last.get("name_en") if en else last.get("name", "-")))
    print("  %s: [%s] %s" % (t["next"], nxt.get("id", "-"),
                              (nxt.get("name_en") if en else nxt.get("name", "-")) or t["none"]))
    print("  %s: %d ｜ %s: %d" % (t["done"], len(done), t["todo"], len(todo)))
    if a.brief:
        return 0

    if gaps:
        print("\n%s（%d）" % (t["gaps"], len(gaps)))
        for g in gaps:
            print("  - %s: %s" % (g["id"], g.get("name_en") if en else g.get("name")))
    if decs:
        print("\n%s" % t["decisions"])
        for x in decs:
            print("  - %s %s  (%s)" % (x["id"], x.get("title_en") if en else x.get("title"),
                                       x.get("file", "")))
    print("\n%s" % t["read_first"])
    print("  state/PROJECT_STATE.md   %s" % ("one page of account" if en else "一页账本"))
    print("  state/progress.json      %s" % ("the same ledger, machine readable" if en else "同一本账，机器读"))
    print("\n%s" % t["cmds"])
    for k in ("cmd_recall", "cmd_preflight", "cmd_stage", "cmd_gate", "cmd_review"):
        print("  " + t[k])
    print("\n" + t["hint"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
