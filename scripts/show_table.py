#!/usr/bin/env python3
"""Render index/actions.csv as a checklist.

The same CSV is read by the agent and rendered for humans here. One source,
two presentations — editing the CSV is the only way to change either.

    python scripts/show_table.py              # all stages, Chinese
    python scripts/show_table.py --lang en    # English
    python scripts/show_table.py --stage 3    # only the data stage
    python scripts/show_table.py --skill estimation
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import OrderedDict

try:  # make Chinese output readable on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(os.path.dirname(HERE), "index", "actions.csv")

SKILL_LABEL = {
    "feasibility": ("可行性闸门", "feasibility gate"),
    "identification": ("识别设计", "identification design"),
    "data-prep": ("数据整理", "data preparation"),
    "estimation": ("估计与稳健性", "estimation"),
    "tables-figures": ("表与图", "tables and figures"),
    "report": ("可复现报告", "reproducible report"),
    "writing": ("写作与投稿", "writing"),
    "review": ("审稿回复", "referee response"),
}


def load():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"actions.csv not found at {CSV_PATH}")
    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--stage", type=int, default=None, help="only this stage id")
    ap.add_argument("--skill", default=None, help="only rows handled by this skill")
    args = ap.parse_args()

    rows = load()
    if args.stage is not None:
        rows = [r for r in rows if int(r["stage_id"]) == args.stage]
    if args.skill:
        rows = [r for r in rows if r["skill"] == args.skill]
    if not rows:
        print("No matching actions.")
        return 1

    zh = args.lang == "zh"
    stages = OrderedDict()
    for row in rows:
        stages.setdefault(row["stage_id"], (row["stage_zh"], row["stage_en"]))

    title = "你这一步打算做什么？（可多选）" if zh else "What do you want to do at this step? (multi-select)"
    print(title)
    print()

    width = max(len(r["id"]) for r in rows)
    for sid in sorted({r["stage_id"] for r in rows}, key=int):
        name_zh, name_en = stages[sid]
        print(f"[{sid}] {name_zh if zh else name_en}")
        for row in rows:
            if row["stage_id"] != sid:
                continue
            action = row["action_zh"] if zh else row["action_en"]
            example = row["example_zh"] if zh else row["example_en"]
            print(f"  [ ] {row['id']:<{width}}  {action:<22}  {example}")
        print()

    print("  [ ] 我不确定 → 进可行性闸门" if zh else "  [ ] Not sure → go to the feasibility gate")
    print()
    labels = sorted({r["skill"] for r in rows})
    print(("对应 skill：" if zh else "Handled by: ") + ", ".join(
        SKILL_LABEL.get(s, (s, s))[0 if zh else 1] for s in labels
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
