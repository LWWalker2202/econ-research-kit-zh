# -*- coding: utf-8 -*-
"""to_fill.py — 把库里所有占位符摊开、分派给人或脚本（只读，只写一份清单）。

占位符记号的四种写法：`[待填]` / `[to fill]` / `[待核实]` / `[verify]`。
三种归属：
    author  只有拿得到数据的人能填（样本量、覆盖年份、政策批次）
    script  跑一遍现成脚本就有（金样数字、表体、看板数据）
    tutor   要拍板的口径（识别假设、聚类层级、表里放哪几列）

用法：
    python scripts/to_fill.py                        # 扫当前目录，写 state/to-fill.csv
    python scripts/to_fill.py --root <仓库根> --out <csv>
    python scripts/to_fill.py --by author            # 只看某一类
    python scripts/to_fill.py --json

退出码：0 一定有输出（这是清单，不是判分），只有输入错才 2
"""
import argparse, csv, io, json, os, re, sys

MARKERS = [
    (re.compile(r"\[待填\]"), "fill"),
    (re.compile(r"\[to fill\]", re.I), "fill"),
    (re.compile(r"\[待核实\]"), "verify"),
    (re.compile(r"\[verify\]", re.I), "verify"),
]
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".econ-kit", "vendor"}
TEXT_EXT = {".md", ".tex", ".py", ".do", ".csv", ".yaml", ".yml", ".json"}
SKIP_FILES = {"to-fill.csv"}

ZH = {
    "author": "作者填",
    "script": "脚本填",
    "tutor": "待拍板",
    "unknown": "待定",
}
WHY = {
    "author": "需要你的数据或样本信息",
    "script": "跑模板脚本即可生成",
    "tutor": "口径/取舍，需要人拍板",
    "unknown": "路径没规则，人工看一眼",
}


def classify(rel, kind):
    p = "/" + rel.replace("\\", "/").lower()
    if kind == "verify":
        return "tutor"
    if "/templates/" in p or "/expected/" in p or p.startswith("scripts/"):
        return "script"
    if "/domains/" in p or "/data-dict/" in p:
        return "author"
    if "/overrides/" in p or p.endswith("skill.md") or "/chapter" in p:
        return "tutor"
    return "unknown"


def scan(root):
    items = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if os.path.splitext(fn)[1].lower() not in TEXT_EXT or fn in SKIP_FILES:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                text = io.open(full, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                for pat, kind in MARKERS:
                    for m in pat.finditer(line):
                        ctx = line.strip()
                        if len(ctx) > 110:
                            ctx = ctx[:107] + "..."
                        items.append({
                            "path": rel, "line": lineno, "kind": kind,
                            "marker": m.group(0),
                            "by": classify(rel, kind),
                            "context": ctx,
                        })
    return items


def main(argv=None):
    ap = argparse.ArgumentParser(description="list every placeholder and who should fill it")
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=os.path.join(".econ-kit", "to-fill.csv"))
    ap.add_argument("--by", choices=["author", "script", "tutor", "unknown"])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    root = os.path.abspath(a.root)
    if not os.path.isdir(root):
        print("not a directory: %s" % root, file=sys.stderr)
        return 2
    items = scan(root)
    if a.by:
        items = [i for i in items if i["by"] == a.by]

    buckets = {k: 0 for k in ("author", "script", "tutor", "unknown")}
    for i in items:
        buckets[i["by"]] += 1
    per_file = {}
    for i in items:
        per_file[i["path"]] = per_file.get(i["path"], 0) + 1

    if a.json:
        print(json.dumps({"total": len(items), "buckets": buckets, "items": items},
                         ensure_ascii=False, indent=2))
        return 0

    out = os.path.join(root, a.out)
    parent = os.path.dirname(out)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["repo", "path", "line", "marker", "by", "why", "context", "done"])
        for i in items:
            w.writerow([os.path.basename(root), i["path"], i["line"], i["marker"],
                        i["by"], WHY[i["by"]], i["context"], ""])

    print("# 占位符清单  %s" % root)
    print("")
    for k in ("author", "script", "tutor", "unknown"):
        print("%-8s %-6s %4d  %s" % (k, ZH[k], buckets[k], WHY[k]))
    print("")
    print("共 %d 处，落在 %d 个文件" % (len(items), len(per_file)))
    print("")
    for path, n in sorted(per_file.items(), key=lambda kv: -kv[1])[:8]:
        print("  %3d  %s" % (n, path))
    print("")
    print("written: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())