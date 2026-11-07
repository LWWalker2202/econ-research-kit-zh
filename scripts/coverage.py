# -*- coding: utf-8 -*-
"""coverage.py — 一个项目"该有的东西"到底齐不齐（只读，不改任何文件）。

用法：
    python scripts/coverage.py                 # 当前目录
    python scripts/coverage.py --project DIR   # 指定研究项目
    python scripts/coverage.py --json          # 给看板/CI 读

退出码：0 全部覆盖 / 1 有缺口 / 2 用法错误
末行固定：N/M covered
"""
import argparse, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = ".econ-kit"

CHECKS_ZH = [
    ("gate", "闸门已开（gate.json 存在）"),
    ("spec", "有任务规格（spec.md）"),
    ("ledger", "有账本（ledger.jsonl 至少一行）"),
    ("protocol", "契约已落盘（PROTOCOL.md）"),
    ("agents", "AGENTS.md 里有契约指针"),
    ("stages", "八段都走到（通过或带缺口放行）"),
    ("nogaps", "没有带缺口放行的段"),
    ("artifacts", "每段该交的文件都在"),
    ("numbers", "报告里有数字对账的痕迹（check_report --results）"),
    ("label", "表文件有 \\label"),
    ("panel", "看板数据不超过一天"),
    ("pinned", "估计结果写明了设定层级"),
    ("cross", "第二套实现重算过金样系数（crosscheck）"),
    ("tofill", "待填清单已分派（to-fill.csv）"),
    ("chain", "数字链对得上（verify_chain：原始行→清洗→回归→报告）"),
]
CHECKS_EN = [
    ("gate", "gate started (gate.json present)"),
    ("spec", "task spec exists (spec.md)"),
    ("ledger", "ledger has at least one line"),
    ("protocol", "contract written (PROTOCOL.md)"),
    ("agents", "AGENTS.md points at the contract"),
    ("stages", "all eight stages reached"),
    ("nogaps", "no stage passed with gaps"),
    ("artifacts", "every promised artifact exists"),
    ("numbers", "report shows number reconciliation"),
    ("label", "table files carry \\label"),
    ("panel", "board data is younger than a day"),
    ("pinned", "estimates record their specification level"),
    ("cross", "a second implementation recomputed the gold numbers"),
    ("tofill", "placeholders triaged into to-fill.csv"),
    ("chain", "the number chain holds (verify_chain: raw -> cleaned -> model -> report)"),
]


def read(path):
    try:
        with io.open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def gate_of(project):
    raw = read(os.path.join(project, STATE, "gate.json"))
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def check_project(project):
    """返回 [(key, ok, note)]；note 只用一句话说明现状。"""
    p = os.path.abspath(project)
    st = gate_of(p)
    raw = (st or {}).get("stages") or {}
    if isinstance(raw, dict):
        stages = [dict(v, stage=k) for k, v in raw.items() if isinstance(v, dict)]
    else:
        stages = list(raw)
    passed = [s for s in stages if s.get("status") in ("passed", "forced")]
    forced = [s for s in stages if s.get("status") == "forced"]
    out = []

    out.append(("gate", st is not None, "gate.json" if st else "缺少 .econ-kit/gate.json"))
    spec = os.path.exists(os.path.join(p, STATE, "spec.md"))
    out.append(("spec", spec, "spec.md" if spec else "缺少 spec.md（先跑 spec.py）"))

    ledger_lines = 0
    lf = os.path.join(p, STATE, "ledger.jsonl")
    if os.path.isfile(lf):
        ledger_lines = sum(1 for line in read(lf).splitlines() if line.strip())
    out.append(("ledger", ledger_lines > 0, "%d 条记录" % ledger_lines))

    proto = os.path.exists(os.path.join(p, STATE, "PROTOCOL.md"))
    out.append(("protocol", proto, "PROTOCOL.md" if proto else "没有 PROTOCOL.md（gate.py start 会写）"))

    agents = "econ-research-kit:begin" in read(os.path.join(p, "AGENTS.md"))
    out.append(("agents", agents, "AGENTS.md 有指针" if agents else "AGENTS.md 没有契约段"))

    n = len(stages)
    out.append(("stages", n > 0 and len(passed) == n, "%d/%d 段到位" % (len(passed), n or 8)))
    out.append(("nogaps", not forced, ("%d 段带缺口放行" % len(forced)) if forced else "无缺口"))

    missing = []
    for s in passed:
        name = s.get("name") or ""
        art = ARTIFACT.get(name, [])
        for rel in art:
            if not os.path.exists(os.path.join(p, rel)):
                missing.append(rel)
    out.append(("artifacts", not missing, ("缺 " + "、".join(missing[:3])) if missing else "都齐"))

    rep = read(os.path.join(p, "report.md"))
    numbers = ("对账" in rep) or ("reconcil" in rep.lower()) or ("checks passed" in rep)
    out.append(("numbers", numbers, "报告里提到对账" if numbers else "报告没提数字对账"))

    tex = []
    for name in os.listdir(p) if os.path.isdir(p) else []:
        if name.endswith(".tex"):
            tex.append(name)
    labelled = bool(tex) and all("\\label" in read(os.path.join(p, t)) for t in tex)
    out.append(("label", labelled, ("%d 个 .tex" % len(tex)) if tex else "没有 .tex 表文件"))


    cross = [f for f in (os.listdir(p) if os.path.isdir(p) else []) if "crosscheck" in f.lower()]
    out.append(("cross", bool(cross), ", ".join(cross[:2]) if cross else "-"))
    tf = os.path.join(p, STATE, "to-fill.csv")
    tf_rows = max(0, len(read(tf).splitlines()) - 1) if os.path.isfile(tf) else 0
    out.append(("tofill", tf_rows > 0, ("%d" % tf_rows) if tf_rows else "-"))
    panel = os.path.join(p, STATE, "dashboard.json")
    fresh = False
    if os.path.isfile(panel):
        fresh = (time.time() - os.path.getmtime(panel)) < 86400
    out.append(("panel", fresh, "面板数据是今天的" if fresh else "面板数据超过一天或不存在"))

    vc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_chain.py")
    chain_ok, chain_note = False, "-"
    if os.path.isfile(vc) and os.path.isfile(os.path.join(p, "output", "estimation-results.json")):
        import subprocess
        import sys as _sys
        r = subprocess.run([_sys.executable, vc, "--project", p, "--lang", "en"],
                           capture_output=True, text=True)
        chain_ok = r.returncode == 0
        chain_note = "3/3" if chain_ok else "有链断了"
    else:
        chain_note = "没有回归结果"
    out.append(("chain", chain_ok, chain_note))

    lad = read(os.path.join(p, "estimation-results.md"))
    pinned = ("设定" in lad) or ("ladder" in lad.lower()) or ("specification" in lad.lower())
    out.append(("pinned", pinned, "写明设定层级" if pinned else "没写设定层级"))
    return out


ARTIFACT = {
    "可行性": ["feasibility-memo.md"],
    "问题与文献": ["lit-matrix.csv"],
    "识别设计": ["identification-memo.md"],
    "数据": ["cleaning-log.md"],
    "估计": ["estimation-results.md"],
    "表与图": ["table1.tex"],
    "报告": ["report.md"],
    "写作": ["abstract.md"],
    "审稿回复": ["response-letter.md"],
    "feasibility": ["feasibility-memo.md"],
    "literature": ["lit-matrix.csv"],
    "identification": ["identification-memo.md"],
    "data": ["cleaning-log.md"],
    "estimation": ["estimation-results.md"],
    "tables": ["table1.tex"],
    "report": ["report.md"],
    "writing": ["abstract.md"],
    "review": ["response-letter.md"],
}


def main(argv=None):
    ap = argparse.ArgumentParser(description="how much of the project is actually there")
    ap.add_argument("--project", default=".")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    project = os.path.abspath(a.project)
    if not os.path.isdir(project):
        print("not a directory: %s" % project, file=sys.stderr)
        return 2
    rows = check_project(project)
    names = dict(CHECKS_ZH if a.lang == "zh" else CHECKS_EN)
    ok = sum(1 for _, good, _ in rows if good)
    total = len(rows)
    if a.json:
        print(json.dumps({"project": project, "covered": ok, "total": total,
                          "items": [{"key": k, "ok": g, "label": names.get(k, k), "note": n}
                                    for k, g, n in rows]}, ensure_ascii=False, indent=2))
    else:
        title = "项目自查覆盖" if a.lang == "zh" else "Project coverage"
        print("# %s  %s" % (title, project))
        print("")
        for k, good, note in rows:
            mark = "[x]" if good else "[ ]"
            print("%s %-14s %s" % (mark, names.get(k, k), note))
        print("")
        print("%d/%d covered" % (ok, total))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())