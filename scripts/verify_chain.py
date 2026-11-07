# -*- coding: utf-8 -*-
"""verify_chain.py - does the number chain hold from raw rows to the report?

Three links are checked:

  raw -> cleaning   rows_written - duplicates - missing == rows_after_cleaning
  cleaning -> model  the N in the estimation output equals the cleaned N
  model -> report    every decimal in the report is in the results file

Two modes:

  kit mode (default)  checks the shipped goldens: skills/data-prep/expected,
                      skills/estimation/expected, skills/report/expected
  project mode        --project DIR reads output/cleaning-summary.csv,
                      output/estimation-results.json, output/report.md

Exit 0 all links hold, 1 a link is broken, 2 usage error.

Usage
  python scripts/verify_chain.py
  python scripts/verify_chain.py --project /path/to/research-project
  python scripts/verify_chain.py --lang zh
"""

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEC = re.compile(r"-?\d+\.\d{2,}")

TEXT = {
    "zh": {
        "title": "数字链复核：原始行 → 清洗后 → 回归 → 报告",
        "link1": "链一 原始 → 清洗",
        "link2": "链二 清洗 → 回归",
        "link3": "链三 回归 → 报告",
        "ok": "对得上",
        "bad": "对不上",
        "skip": "文件不在，跳过",
        "rows": "生成行数",
        "dup": "删重复",
        "miss": "缺字段删除",
        "kept": "清洗后行数",
        "est_n": "回归样本量",
        "decs": "报告里的小数",
        "found": "能在结果里找到",
        "summary": "%d/%d 条对上",
        "why1": "245 - 5 - 7 应当等于 233",
        "why2": "回归用的样本量应当等于清洗后的行数",
        "why3": "报告里每个小数都应当来自结果文件，不能手打",
        "next": "下一步：先查这一步的代码与说明书，再往下走",
        "pass": "全部对上，可以往下走",
    },
    "en": {
        "title": "Number chain: raw rows -> cleaned -> model -> report",
        "link1": "Link 1  raw -> cleaning",
        "link2": "Link 2  cleaning -> model",
        "link3": "Link 3  model -> report",
        "ok": "holds",
        "bad": "BROKEN",
        "skip": "files absent, skipped",
        "rows": "rows written",
        "dup": "duplicates removed",
        "miss": "dropped for missing key",
        "kept": "rows after cleaning",
        "est_n": "estimation N",
        "decs": "decimals in the report",
        "found": "found in the results",
        "summary": "%d/%d links hold",
        "why1": "245 - 5 - 7 should equal 233",
        "why2": "the estimation N should equal the cleaned row count",
        "why3": "every decimal in the report should come from the results file",
        "next": "Fix this link before moving on: read the code, then the skill page",
        "pass": "all links hold, safe to move on",
    },
}


def read(path):
    try:
        return io.open(path, encoding="utf-8").read()
    except OSError:
        return None


def csv_map(path):
    t = read(path)
    if t is None:
        return None
    out = {}
    for line in t.splitlines()[1:]:
        if "," not in line:
            continue
        k, v = line.split(",", 1)
        try:
            out[k.strip()] = float(v.strip())
        except ValueError:
            out[k.strip()] = v.strip()
    return out


def gather_numbers(obj, out):
    if isinstance(obj, dict):
        for v in obj.values():
            gather_numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            gather_numbers(v, out)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out.append(float(obj))


def fmt(x):
    if isinstance(x, float) and x.is_integer():
        return "%d" % int(x)
    return "%s" % x


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--project", default="", help="research project directory (output/ inside)")
    ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    ap.add_argument("--root", default=ROOT, help="kit root")
    a = ap.parse_args()
    tx = TEXT[a.lang if a.lang in TEXT else "zh"]

    if a.project:
        base = os.path.join(a.project, "output")
        clean_p = os.path.join(base, "cleaning-summary.csv")
        est_p = os.path.join(base, "estimation-results.json")
        rep_p = os.path.join(base, "report.md")
    else:
        base = a.root
        clean_p = os.path.join(base, "skills", "data-prep", "expected", "clean_panel_summary.csv")
        est_p = os.path.join(base, "skills", "estimation", "expected", "estimation-results.json")
        rep_p = os.path.join(base, "skills", "report", "expected", "report.md")

    if not os.path.exists(clean_p) and not os.path.exists(est_p):
        sys.stderr.write("no cleaning or estimation output at %s\n" % base)
        return 2

    results = []
    print("=" * 64)
    print(tx["title"])
    print("=" * 64)

    # link 1: arithmetic inside the cleaning summary
    cm = csv_map(clean_p)
    if not cm:
        print("\n%-24s %s" % (tx["link1"], tx["skip"]))
        results.append(("skip", tx["link1"]))
        cleaned = None
    else:
        rows = cm.get("rows_written_by_generator")
        dup = cm.get("duplicate_rows_removed")
        miss = cm.get("rows_dropped_missing_key")
        kept = cm.get("rows_after_cleaning")
        print("\n%s" % tx["link1"])
        print("  %-22s %s" % (tx["rows"], fmt(rows)))
        print("  %-22s -%s" % (tx["dup"], fmt(dup)))
        print("  %-22s -%s" % (tx["miss"], fmt(miss)))
        print("  %-22s %s" % (tx["kept"], fmt(kept)))
        ok1 = rows is not None and dup is not None and miss is not None and kept is not None and (rows - dup - miss) == kept
        print("  -> %s" % (tx["ok"] if ok1 else tx["bad"] + "  (" + tx["why1"] + ")"))
        results.append(("ok" if ok1 else "bad", tx["link1"]))
        cleaned = kept

    # link 2: estimation N versus cleaned N
    jt = read(est_p)
    est_n = None
    if jt is None:
        print("\n%-24s %s" % (tx["link2"], tx["skip"]))
        results.append(("skip", tx["link2"]))
    else:
        j = json.loads(jt)
        ns = []
        for spec in (j.get("specifications") or []):
            if isinstance(spec.get("n_obs"), (int, float)):
                ns.append(float(spec["n_obs"]))
        if isinstance((j.get("panel") or {}).get("n_obs"), (int, float)):
            ns.append(float((j.get("panel") or {})["n_obs"]))
        est_n = ns[0] if ns else None
        same_ns = len(set(ns)) <= 1
        print("\n%s" % tx["link2"])
        print("  %-22s %s" % (tx["kept"], fmt(cleaned) if cleaned is not None else "?"))
        print("  %-22s %s" % (tx["est_n"], fmt(est_n) if est_n is not None else "?"))
        if cleaned is None:
            print("  -> %s (cleaning summary missing)" % tx["skip"])
            results.append(("skip", tx["link2"]))
        elif a.project:
            same = (est_n is not None and abs(est_n - cleaned) < 1e-9)
            print("  -> %s%s" % (tx["ok"] if same else tx["bad"] + "  (" + tx["why2"] + ")", ""))
            results.append(("ok" if same else "bad", tx["link2"]))
        else:
            # different fixtures by design in the kit demo: report but only fail on internal inconsistency
            consist = same_ns
            print("  -> %s%s" % (tx["ok"] if consist else tx["bad"],
                                 "" if consist else "  (" + tx["why2"] + ")"))
            print("     " + ("kit demo: the two goldens use different fixtures by design; "
                                "with --project the N must equal the cleaned rows"))
            results.append(("ok" if consist else "bad", tx["link2"]))

    # link 3: every decimal in the report exists in the results file
    rep = read(rep_p)
    if rep is None or jt is None:
        print("\n%-24s %s" % (tx["link3"], tx["skip"]))
        results.append(("skip", tx["link3"]))
    else:
        nums = []
        gather_numbers(json.loads(jt), nums)
        cands = set()
        for x in nums:
            for nd in range(2, 7):
                cands.add(("%." + str(nd) + "f") % x)
                cands.add("%.0f" % x if float(x).is_integer() else "")
        body = re.sub(r"```.*?```", "", rep, flags=re.S)
        decs = DEC.findall(body)
        found = [d for d in decs if d in cands]
        print("\n%s" % tx["link3"])
        print("  %-22s %d" % (tx["decs"], len(decs)))
        print("  %-22s %d" % (tx["found"], len(found)))
        ok3 = len(found) == len(decs)
        missing = [d for d in decs if d not in cands][:5]
        print("  -> %s%s" % (tx["ok"] if ok3 else tx["bad"] + "  (" + tx["why3"] + ")",
                             "" if ok3 else "  " + ", ".join(missing)))
        results.append(("ok" if ok3 else "bad", tx["link3"]))

    okn = sum(1 for s, _ in results if s == "ok")
    badn = sum(1 for s, _ in results if s == "bad")
    total = okn + badn
    print("\n" + "=" * 64)
    print((tx["pass"] if badn == 0 else tx["next"]) + "  |  " + (tx["summary"] % (okn, total if total else 0)))
    print("=" * 64)
    return 0 if badn == 0 else 1


if __name__ == "__main__":
    sys.exit(main())