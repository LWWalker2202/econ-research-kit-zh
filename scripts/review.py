#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""review.py — 每一步结束时复查：这一步真的做完了吗？

三类检查，缺一类都不算完：
  1. 账本：progress.json 里这一步声明的产物文件真的存在、不是空文件。
  2. 机器：内容红线（lint）与两仓一致性（parity）通过。
  3. 反查：前面步骤的产物没有被这一步弄丢。

用法：
    python scripts/review.py A2
    python scripts/review.py A2 --mark-done     # 通过后把状态写成 done
    python scripts/review.py A2 --skip-machine  # 只查账本（离线时用）
    python scripts/review.py --list

退出码：0 通过 / 1 不通过 / 2 用法错
"""

import argparse
import io
import json
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROGRESS = os.path.join(ROOT, "state", "progress.json")

TEXT = {
    "zh": {
        "head": "复查 [%s] %s",
        "c1": "1) 账本：这一步声明的产物",
        "c2": "2) 机器：内容红线与两仓一致性",
        "c3": "3) 反查：前面步骤的产物还在不在",
        "ok": "  [OK]",
        "bad": "  [X ]",
        "miss": "缺文件",
        "empty": "空文件",
        "pass": "通过",
        "fail": "不通过",
        "sum": "\n结论：%s（%d 项通过，%d 项不通过）",
        "mark": "已把 [%s] 标为 done，state/progress.json 已更新。",
        "next": "下一步：%s",
        "nomachine": "  [--] 跳过机器校验（--skip-machine）",
        "noexist": "progress.json 里没有这个步骤号：%s",
        "list": "步骤清单：",
    },
    "en": {
        "head": "Review [%s] %s",
        "c1": "1) Ledger: artifacts this step declares",
        "c2": "2) Machine: content rules and repository parity",
        "c3": "3) Regression: earlier artifacts still present",
        "ok": "  [OK]",
        "bad": "  [X ]",
        "miss": "missing",
        "empty": "empty",
        "pass": "PASS",
        "fail": "FAIL",
        "sum": "\nResult: %s (%d checks passed, %d failed)",
        "mark": "Marked [%s] as done and updated state/progress.json.",
        "next": "Next: %s",
        "nomachine": "  [--] machine checks skipped (--skip-machine)",
        "noexist": "No such step id in progress.json: %s",
        "list": "Steps:",
    },
}


def load():
    if not os.path.exists(PROGRESS):
        print("state/progress.json not found", file=sys.stderr)
        sys.exit(2)
    with io.open(PROGRESS, encoding="utf-8") as f:
        return json.load(f)


def save(d):
    with io.open(PROGRESS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")


def run(cmd):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()


def main():
    ap = argparse.ArgumentParser(add_help=True, description="每一步结束时的三类复查")
    ap.add_argument("step", nargs="?", default="", help="步骤号，例如 A2")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--mark-done", action="store_true")
    ap.add_argument("--skip-machine", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    d = load()
    t = TEXT[a.lang]
    steps = d.get("steps") or []

    if a.list or not a.step:
        print(t["list"])
        for s in steps:
            print("  [%-6s] %-4s %s" % (s.get("status", "?"), s.get("id", "?"), s.get("name", "")))
        return 0 if a.list else 2

    step = next((s for s in steps if s.get("id") == a.step), None)
    if step is None:
        print(t["noexist"] % a.step)
        return 2

    print(t["head"] % (step["id"], step.get("name", "")))
    fails = []
    oks = 0

    # 1) ledger
    print(t["c1"])
    arts = step.get("artifacts") or []
    if not arts:
        print(t["bad"] + " " + ("no artifacts declared" if a.lang == "en" else "没声明任何产物"))
        fails.append("no artifacts")
    for rel in arts:
        p = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.exists(p):
            print(t["bad"] + " %s — %s" % (rel, t["miss"]))
            fails.append("missing " + rel)
        elif os.path.getsize(p) == 0:
            print(t["bad"] + " %s — %s" % (rel, t["empty"]))
            fails.append("empty " + rel)
        else:
            oks += 1
            print(t["ok"] + " %s (%d B)" % (rel, os.path.getsize(p)))

    # 2) machine
    print(t["c2"])
    if a.skip_machine:
        print(t["nomachine"])
    else:
        rc, out = run([sys.executable, os.path.join(HERE, "lint_content.py"), "."])
        line = out.splitlines()[-1] if out else ""
        if rc == 0:
            oks += 1
            print(t["ok"] + " lint: " + line)
        else:
            print(t["bad"] + " lint: " + (line or "failed"))
            fails.append("lint")
        if os.path.exists(os.path.join(HERE, "check_parity.py")):
            rc, out = run([sys.executable, os.path.join(HERE, "check_parity.py")])
            line = out.splitlines()[-1] if out else ""
            if rc == 0:
                oks += 1
                print(t["ok"] + " parity: " + line)
            else:
                print(t["bad"] + " parity: " + (line or "failed"))
                fails.append("parity")

    # 3) regression
    print(t["c3"])
    idx = steps.index(step)
    earlier = [s for s in steps[:idx] if s.get("status") == "done"]
    lost = 0
    for s in earlier:
        for rel in s.get("artifacts") or []:
            if not os.path.exists(os.path.join(ROOT, rel.replace("/", os.sep))):
                print(t["bad"] + " %s : %s — %s" % (s["id"], rel, t["miss"]))
                fails.append("lost " + rel)
                lost += 1
    if not lost:
        oks += 1
        print(t["ok"] + " " + ("all %d earlier artifacts present" % sum(
            len(s.get("artifacts") or []) for s in earlier) if a.lang == "en"
            else "前面 %d 个产物都还在" % sum(len(s.get("artifacts") or []) for s in earlier)))

    verdict = t["pass"] if not fails else t["fail"]
    print(t["sum"] % (verdict, oks, len(fails)))

    if fails:
        print("   " + "; ".join(fails))
        return 1

    if a.mark_done:
        step["status"] = "done"
        step["at"] = __import__("datetime").date.today().isoformat()
        save(d)
        print(t["mark"] % step["id"])
        nxt = next((s for s in steps if s.get("status") != "done"), None)
        if nxt:
            print(t["next"] % ("[%s] %s" % (nxt["id"], nxt.get("name_en") if a.lang == "en"
                                            else nxt.get("name", ""))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
