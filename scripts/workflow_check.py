#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""workflow_check.py — 检查 workflows/main.yaml 的交接契约成不成立。

查五件事：
  1. 段号从 0 开始连续、入口存在；
  2. 每一段 requires 的文件，必须是前面某一段 produces 过的（不是凭空出现）；
  3. 同一段不能 require 自己 produce 的东西；
  4. produces 里没有跨段重复（一个文件只能由一段负责）；
  5. 每段的 skill 目录存在且带 SKILL.md，中英各有一句 gate 问话。

零第三方依赖：为这一个文件格式写了二十行的解析，不用 PyYAML。
退出码：0 契约成立 / 1 有断裂 / 2 文件找不到或读不懂。
"""

import io
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, "workflows", "main.yaml")

T = {
    "zh": dict(title="交接契约检查：workflows/main.yaml", ok="契约成立：%d 段，%d 个产物，无断裂。",
               bad="断裂 %d 处：", seq="段号必须是 0..N 连续，实际：%s",
               entry="入口段 %s 不存在", unknown="第 %d 段 require 了 %s，但前面没有任何一段 produce 它",
               selfdep="第 %d 段自己 require 自己 produce 的 %s",
               dup="%s 被多段 produce：%s", noskill="第 %d 段的 skill 目录不存在或缺 SKILL.md：%s",
               nogate="第 %d 段缺中文或英文的 gate 问话", onmissing="第 %d 段的 on_missing 只能是 stop 或 back，实际 %s"),
    "en": dict(title="Handoff contract check: workflows/main.yaml", ok="Contract holds: %d stages, %d artifacts, no break.",
               bad="%d break(s):", seq="Stage ids must be 0..N contiguous, got: %s",
               entry="Entry stage %s does not exist", unknown="Stage %d requires %s but no earlier stage produces it",
               selfdep="Stage %d requires its own output %s",
               dup="%s produced by several stages: %s", noskill="Stage %d skill dir missing or has no SKILL.md: %s",
               nogate="Stage %d lacks a Chinese or English gate question", onmissing="Stage %d on_missing must be stop or back, got %s"),
}


def parse(path):
    """只认这个文件用到的语法：key: value、- id: n 起一个 stage、缩进的 - item 列表、| 块。"""
    stages, cur, field = [], None, None
    with io.open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if line.startswith("version:") or line.startswith("id:") or line.startswith("name_") or line.startswith("entry:"):
                if line.startswith("entry:"):
                    stages.append({"__entry__": line.split(":", 1)[1].strip()})
                continue
            stripped = line.strip()
            if stripped.startswith("- id:"):
                if cur:
                    stages.append(cur)
                cur = {"id": int(stripped.split(":", 1)[1].strip()), "requires": [], "produces": []}
                field = None
                continue
            if cur is None:
                continue
            if stripped.startswith("- "):
                if field:
                    cur[field].append(stripped[2:].strip())
                continue
            if ":" in stripped:
                key, val = stripped.split(":", 1)
                key, val = key.strip(), val.strip()
                if key in ("requires", "produces"):
                    field = key
                    cur.setdefault(key, [])
                    continue
                field = None
                if key in ("id",):
                    continue
                cur[key] = val
    if cur:
        stages.append(cur)
    return stages


def main(argv=None):
    lang = "zh"
    args = list(argv if argv is not None else sys.argv[1:])
    if "--lang" in args:
        i = args.index("--lang")
        if i + 1 < len(args):
            lang = args[i + 1]
    t = T["en" if lang == "en" else "zh"]

    if not os.path.exists(WF):
        print(("找不到 %s" if lang == "zh" else "not found: %s") % WF)
        return 2
    try:
        parsed = parse(WF)
    except Exception as e:
        print(("读不懂 main.yaml：%s" if lang == "zh" else "cannot parse main.yaml: %s") % e)
        return 2

    entry = None
    stages = []
    for p in parsed:
        if "__entry__" in p:
            entry = p["__entry__"]
        else:
            stages.append(p)

    errs = []
    ids = [s["id"] for s in stages]
    if ids != list(range(len(ids))):
        errs.append(t["seq"] % ids)
    if entry is not None and entry not in [str(i) for i in ids]:
        errs.append(t["entry"] % entry)

    produced_by = {}
    for s in stages:
        for p in s["produces"]:
            produced_by.setdefault(p, []).append(s["id"])
        if set(s["requires"]) & set(s["produces"]):
            for p in sorted(set(s["requires"]) & set(s["produces"])):
                errs.append(t["selfdep"] % (s["id"], p))
        for r in s["requires"]:
            ok = any(r in prev["produces"] for prev in stages if prev["id"] < s["id"])
            if not ok:
                errs.append(t["unknown"] % (s["id"], r))
        skill = s.get("skill", "")
        sdir = os.path.join(ROOT, "skills", skill)
        if not os.path.isfile(os.path.join(sdir, "SKILL.md")):
            errs.append(t["noskill"] % (s["id"], skill))
        if not s.get("gate_zh") or not s.get("gate_en"):
            errs.append(t["nogate"] % s["id"])
        om = s.get("on_missing", "")
        if om not in ("stop", "back"):
            errs.append(t["onmissing"] % (s["id"], om))

    for p, owners in sorted(produced_by.items()):
        if len(owners) > 1:
            errs.append(t["dup"] % (p, owners))

    print("# " + t["title"])
    print("")
    if errs:
        print(t["bad"] % len(errs))
        for e in errs:
            print("  - " + e)
        return 1
    print(t["ok"] % (len(stages), sum(len(s["produces"]) for s in stages)))
    for s in stages:
        print("  %d. %-12s requires %-34s produces %s" % (
            s["id"], s.get("skill", ""), "、".join(s["requires"]) or "—", "、".join(s["produces"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
