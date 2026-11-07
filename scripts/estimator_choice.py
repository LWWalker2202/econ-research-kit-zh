# -*- coding: utf-8 -*-
"""estimator_choice.py — 按数据结构挑估计量，并把"什么时候会错"一起印出来（只读）。

用法：
    python scripts/estimator_choice.py --list
    python scripts/estimator_choice.py --data panel
    python scripts/estimator_choice.py --data cross --family iv
    python scripts/estimator_choice.py --json

退出码：0 有输出 / 2 用法错
"""
import argparse, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "skills", "estimation", "data", "estimators.json")
DATA_KINDS = {
    "cross": "横截面（每人/每单位一条）",
    "panel": "面板（同一单位多期）",
    "experiment": "随机实验",
}


def load():
    with io.open(DATA, encoding="utf-8") as f:
        return json.load(f)


def render(rows, kinds):
    out = []
    out.append("| 估计量 | 识别的是什么 | 关键假设 | 什么时候会错 | Stata | Python |")
    out.append("|---|---|---|---|---|---|")
    for e in rows:
        out.append("| **%s** | %s | %s | %s | `%s` | `%s` |" % (
            e["zh"], e["estimand"], "、".join(e["assumptions"]),
            e["fails_when"], e["stata"], e["python"]))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="pick an estimator by data shape")
    ap.add_argument("--data", choices=sorted(DATA_KINDS), help="what shape your data is")
    ap.add_argument("--family")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        d = load()
    except (OSError, ValueError) as e:
        print("cannot read %s: %s" % (DATA, e), file=sys.stderr)
        return 2
    rows = d.get("estimators", [])
    if a.data:
        rows = [e for e in rows if a.data in (e.get("data") or [])]
    if a.family:
        rows = [e for e in rows if e.get("family") == a.family]
    if not rows:
        print("没有匹配的估计量（试试 --list）", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if a.list:
        fam = {}
        for e in rows:
            fam.setdefault(e.get("family", "?"), []).append(e["zh"])
        for k in sorted(fam):
            print("%-14s %s" % (k, "、".join(fam[k])))
        print("")
        print("%d estimators" % len(rows))
        return 0
    if a.data:
        print("# 数据结构：%s" % DATA_KINDS[a.data])
        print("")
    print(render(rows, DATA_KINDS))
    print("")
    print("> 这张表只负责「该选哪个」，不负责「跑得对不对」；跑完用 `python scripts/crosscheck.py` 对一次账。")
    return 0


if __name__ == "__main__":
    sys.exit(main())