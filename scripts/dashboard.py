#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dashboard.py - one command that answers four questions.

为什么要有这个脚本
------------------
八个工序里已经有三件东西在记录状态：`state/progress.json`（库自己的构建账本）、
`.econ-kit/gate.json`（你的研究项目停在哪一段）、`output/`（跑出来的表与图）。
但没有人把它们放在一页上看过。这个脚本只做一件事：把这三处读出来，摊成一页。

它不判断对错，也不替你决定；它只把"现在在哪 / 接下来做什么 / 检查器过了几项 /
数据被改了多少"摆出来。判断仍然在人手里。

用法
----
    python scripts/dashboard.py                     # 终端状态板
    python scripts/dashboard.py --html dash.html    # 单文件看板（内联 CSS + 内联 SVG）
    python scripts/dashboard.py --json              # 机器读
    python scripts/dashboard.py --lang en           # 英文

退出码：0 正常；2 用法错（根目录找不到 state/progress.json）。

零第三方依赖；同一份输入永远输出同样的字节（不写时间戳，只用账本里的日期）。
"""

import argparse
import io
import json
import os
import re
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

STAGE_SKILLS = [
    "feasibility", "literature", "identification", "data-prep", "estimation",
    "tables-figures", "report", "writing", "review",
]

TEXT = {
    "zh": {
        "title": "经济学研究工序库",
        "subtitle": "八道工序 · 十二个领域 · 可跑的金样与检查器",
        "s1": "一、现在在哪",
        "s2": "二、接下来做什么",
        "s3": "三、检查器通过率与库规模",
        "s4": "四、数据处理进度",
        "version": "版本",
        "released": "已发布",
        "no_gate": "你的研究项目还没有开闸门（.econ-kit/gate.json 不在当前目录）。开一条：",
        "stage": "段",
        "status_open": "等回答",
        "status_passed": "已通过",
        "status_forced": "带缺口放行",
        "status_todo": "未开始",
        "question": "题目",
        "next": "下一段",
        "ask": "这一段的确认问话",
        "blocked": "现在被挡住，没有回答不许往下走",
        "gaps": "还开着的缺口",
        "no_gaps": "没有开着的缺口",
        "checks": "检查器",
        "no_checks": "没找到检查器金样（skills/*/expected/check-report*.txt）",
        "scale": "库规模",
        "files": "文件",
        "md": "篇 Markdown",
        "skills": "个 skill",
        "domains": "个领域",
        "dd": "个数据字典条目",
        "build": "库本身的构建账本",
        "steps_done": "步已完成",
        "cleaning": "清洗六步（进多少行到出多少行）",
        "ladder": "设定阶梯（系数与标准误，位移是重点）",
        "events": "事件研究",
        "searches": "文献检索记录",
        "no_data": "还没有跑过，所以没有数字可摊。跑这条命令再回来：",
        "hint_data": "python skills/data-prep/templates/clean_panel.py --decisions",
        "hint_ladder": "python skills/estimation/templates/estimate_main.py --ladder",
        "hint_start": 'python scripts/gate.py start "<你的题目>"',
        "html_note": "单文件看板：双击打开即可，不联网、不加载外部脚本。",
        "col_step": "步",
        "col_action": "动作",
        "col_rows": "进到出",
        "col_delta": "动了多少",
        "col_change": "相对上一级",
        "updated": "账本更新于",
    },
    "en": {
        "title": "Economics research kit",
        "subtitle": "Eight stages, twelve fields, runnable checks",
        "s1": "1. Where you are",
        "s2": "2. What comes next",
        "s3": "3. Checker pass rates and scale",
        "s4": "4. Data processing so far",
        "version": "version",
        "released": "released",
        "no_gate": "No gate state in the current directory (.econ-kit/gate.json). Start one:",
        "stage": "stage",
        "status_open": "open",
        "status_passed": "passed",
        "status_forced": "forced",
        "status_todo": "not started",
        "question": "question",
        "next": "next stage",
        "ask": "the question this stage asks",
        "blocked": "blocked: no answer, no next stage",
        "gaps": "gaps still open",
        "no_gaps": "no gap is open",
        "checks": "checkers",
        "no_checks": "no checker golden found (skills/*/expected/check-report*.txt)",
        "scale": "scale",
        "files": "files",
        "md": "markdown",
        "skills": "skills",
        "domains": "domains",
        "dd": "data-dict entries",
        "build": "the kit's own build ledger",
        "steps_done": "steps done",
        "cleaning": "six cleaning actions (rows in -> rows out)",
        "ladder": "specification ladder (coefficient and standard error)",
        "events": "event study",
        "searches": "literature searches logged",
        "no_data": "nothing has been run yet, so there are no numbers. Run this first:",
        "hint_data": "python skills/data-prep/templates/clean_panel.py --decisions",
        "hint_ladder": "python skills/estimation/templates/estimate_main.py --ladder",
        "hint_start": 'python scripts/gate.py start "<your question>"',
        "html_note": "Single file: open it directly. No network, no external script.",
        "col_step": "step",
        "col_action": "action",
        "col_rows": "in -> out",
        "col_delta": "moved",
        "col_change": "vs previous",
        "updated": "ledger updated",
    },
}

CHECK_NAMES = {
    "feasibility": ("可行性备忘录", "feasibility memo"),
    "identification": ("识别设计备忘录", "identification memo"),
    "literature": ("文献矩阵", "literature matrix"),
    "report": ("可复现报告", "report"),
    "review": ("审稿回复", "response letter"),
    "writing": ("摘要", "abstract"),
    "data-prep": ("清洗日志", "cleaning log"),
    "estimation": ("估计结果", "estimation results"),
    "tables-figures": ("三线表", "table"),
}


# --------------------------------------------------------------------------- #
# 读
# --------------------------------------------------------------------------- #
def read_text(path):
    """读文本：先按 UTF-8；不是 UTF-8 的（别人用 PowerShell 重定向写的 UTF-16 等）退到逐级解码，
    宁可显示怪字符也不要因为一份金样把整块看板打断。"""
    if not os.path.exists(path):
        return ""
    with io.open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8", "utf-8-sig", "utf-16", "gb18030"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode("utf-8", "replace")


def parse_progress(root):
    p = os.path.join(root, "state", "progress.json")
    if not os.path.exists(p):
        return None
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)


def parse_workflow(root):
    """手工解 main.yaml 里我们需要的几行（不为它引入 PyYAML）。"""
    text = read_text(os.path.join(root, "workflows", "main.yaml"))
    stages, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^\s*-\s*id:\s*(\d+)\s*$", line)
        if m:
            if cur:
                stages.append(cur)
            cur = {"id": int(m.group(1)), "name_zh": "", "name_en": "",
                   "skill": "", "gate_zh": "", "gate_en": "", "produces": []}
            continue
        if cur is None:
            continue
        m = re.match(r"^\s*(name_zh|name_en|skill|gate_zh|gate_en):\s*(.+?)\s*$", line)
        if m:
            key, val = m.group(1), m.group(2)
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            cur[key] = val
            continue
        m = re.match(r"^\s*-\s*([A-Za-z0-9_.\-]+\.(?:md|csv|json|tex|py))\s*$", line)
        if m:
            cur["produces"].append(m.group(1))
    if cur:
        stages.append(cur)
    return stages


def parse_gate(root):
    p = os.path.join(root, ".econ-kit", "gate.json")
    if not os.path.exists(p):
        return None
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)


def parse_check_report(path):
    text = read_text(path)
    for line in reversed([x.strip() for x in text.splitlines() if x.strip()]):
        m = re.search(r"(\d+)\s*/\s*(\d+)", line)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def coverage_of(project):
    """项目自查覆盖（调 coverage.py；失败返回 None，不影响看板）。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import coverage as _cov
        rows = _cov.check_project(project)
        ok = sum(1 for _k, good, _n in rows if good)
        return {"covered": ok, "total": len(rows)}
    except Exception:
        return None


def collect_checks(root):
    out = []
    base = os.path.join(root, "skills")
    if not os.path.isdir(base):
        return out
    for skill in sorted(os.listdir(base)):
        d = os.path.join(base, skill, "expected")
        if not os.path.isdir(d):
            continue
        best = None
        for name in sorted(os.listdir(d)):
            if name.startswith("check-report") and name.endswith(".txt"):
                got = parse_check_report(os.path.join(d, name))
                if got and (best is None or got[1] > best[1]):
                    best = got
        if best:
            out.append({"skill": skill, "passed": best[0], "total": best[1]})
    return out


def count_scale(root):
    files = md = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", ".econ-kit", "output")]
        for name in filenames:
            files += 1
            if name.endswith(".md"):
                md += 1
    skills = domains = dd = 0
    p = os.path.join(root, "skills")
    if os.path.isdir(p):
        skills = len([d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))])
    p = os.path.join(root, "domains")
    if os.path.isdir(p):
        domains = len([d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))])
    p = os.path.join(root, "data-dict")
    if os.path.isdir(p):
        dd = len([f for f in os.listdir(p) if f.endswith(".md")
                  and not f.startswith("_") and f != "README.md"])
    return {"files": files, "md": md, "skills": skills, "domains": domains, "datadict": dd}


def md_tables(text):
    """把 Markdown 里的管道表切成 [header, row...]，跳过分隔行。"""
    tables, cur = [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.match(r"^:?-{2,}:?$", c) for c in cells if c):
                continue
            cur.append(cells)
        else:
            if cur:
                tables.append(cur)
                cur = []
    if cur:
        tables.append(cur)
    return tables


def parse_cleaning(out_dir):
    text = read_text(os.path.join(out_dir, "cleaning-decisions.md"))
    if not text:
        return []
    rows = []
    for table in md_tables(text):
        head = table[0]
        if not any("动作" in h or "action" in h.lower() for h in head):
            continue
        for r in table[1:]:
            if len(r) < 5:
                continue
            def num(s):
                m = re.search(r"-?\d+", s or "")
                return int(m.group(0)) if m else None
            rows.append({
                "step": num(r[0]),
                "action": r[1],
                "before": num(r[2]),
                "after": num(r[3]),
                "delta": r[4],
            })
        break
    return rows


def parse_ladder(out_dir):
    text = read_text(os.path.join(out_dir, "spec-ladder.md"))
    if not text:
        return [], []
    ladder, events = [], []
    for table in md_tables(text):
        head = " ".join(table[0])
        if "相对上一级" in head or "vs previous" in head.lower():
            for r in table[1:]:
                if len(r) < 7:
                    continue
                m = re.search(r"(-?\d+\.\d+)\s*\(\s*(\d+\.\d+)\s*\)", r[6])
                if not m:
                    continue
                ladder.append({
                    "step": r[0], "what": r[1], "cluster": r[3],
                    "coef": float(m.group(1)), "se": float(m.group(2)),
                    "change": r[7] if len(r) > 7 else "",
                })
        elif "系数" in head or "coefficient" in head.lower():
            for r in table[1:]:
                if len(r) < 2:
                    continue
                m = re.search(r"(-?\d+\.\d+)\s*\(\s*(\d+\.\d+)\s*\)", r[1])
                if m:
                    events.append({"term": r[0], "coef": float(m.group(1)),
                                   "se": float(m.group(2))})
    return ladder, events


def count_searches(out_dir):
    p = os.path.join(out_dir, "search-log.csv")
    text = read_text(p)
    if not text:
        return 0
    return max(0, len([x for x in text.splitlines() if x.strip()]) - 1)


def parse_skill_flow(root, skill):
    """从该工序的 SKILL.md 里抓最多 6 条做法，给面板点开后的"操作流程"。"""
    if not skill:
        return []
    text = read_text(os.path.join(root, "skills", skill, "SKILL.md"))
    if not text:
        return []
    want = ("步骤", "流程", "怎么做", "procedure", "process", "steps", "workflow", "how to")
    out, inside = [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            head = s.lstrip("#").strip().lower()
            inside = any(head.startswith(w) for w in want)
            continue
        if not inside or not s:
            continue
        if s.startswith(("- ", "* ")) or (s[0].isdigit() and s.split(".")[0].isdigit()):
            item = re.sub(r"^([-*]\s+|\d+[.)]\s*)", "", s).strip()
            item = re.sub(r"\*\*(.+?)\*\*", r"\1", item)
            item = re.sub(r"`([^`]*)`", r"\1", item)
            if item:
                out.append(item[:140])
        if len(out) >= 6:
            break
    return out


def read_ledger(project, limit=400):
    """读 .econ-kit/ledger.jsonl（C6 账本）。坏行跳过，读不到就返回空。"""
    path = os.path.join(os.path.abspath(project), ".econ-kit", "ledger.jsonl")
    out = []
    if not os.path.isfile(path):
        return out
    try:
        with io.open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return out[-limit:]


def stage_details(root, wf, gate, checks, project):
    """每一段的点开视图：状态 / 闸门问句 / 你的回答 / 该交的文件在不在 / 流程要点 / 检查器。"""
    by_stage = {}
    for rec in stage_records(gate):
        by_stage[int(rec["stage"])] = rec
    named = dict((c.get("name"), c) for c in (checks or []))
    ledger = read_ledger(project)
    out = []
    for i, w in enumerate(wf or []):
        sid = int(w.get("id", i))
        rec = by_stage.get(sid, {})
        files = []
        for rel in (w.get("produces") or []):
            files.append({"path": rel, "exists": os.path.exists(os.path.join(project, rel))})
        out.append({
            "id": sid,
            "name_zh": w.get("name_zh", ""),
            "name_en": w.get("name_en", ""),
            "skill": w.get("skill", ""),
            "gate_zh": w.get("gate_zh", ""),
            "gate_en": w.get("gate_en", ""),
            "status": rec.get("status", "todo"),
            "answer": rec.get("answer", ""),
            "answered_at": rec.get("answered_at", ""),
            "forced_gaps": rec.get("forced_gaps") or [],
            "files": files,
            "flow": parse_skill_flow(root, w.get("skill", "")),
            "beyond_zh": list(w.get("beyond_zh") or []),
            "beyond_en": list(w.get("beyond_en") or []),
            "check": named.get(w.get("skill", "")),
            "log": [e for e in ledger if str(e.get("stage")) == str(sid)][-4:],
        })
    return out


def parse_spec(project):
    """读 .econ-kit/spec.md：原话 / 四槽 / 待确认问题 / 提示词草稿。

    这份文件由 scripts/spec.py 生成，格式是固定的几节；这里只认那几节，
    读不到就返回 {}，让面板显示"还没有规格草稿"。"""
    p = os.path.join(project, ".econ-kit", "spec.md")
    text = read_text(p)
    if not text:
        return {}
    out = {"path": p.replace(os.sep, "/"), "quote": "", "slots": [], "questions": [], "prompt": ""}
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("> ") and not out["quote"]:
            out["quote"] = s[2:].strip()
        if s.startswith("| ") and s.count("|") >= 4 and "---" not in s:
            cells = [c.strip() for c in s.strip("|").split("|")]
            if cells and cells[0] not in ("槽位", "slot", "Slot"):
                if len(cells) >= 3:
                    out["slots"].append({"name": cells[0], "state": cells[1], "value": cells[2]})
        m = re.match(r"^(\d+)\.\s+(.+)$", s)
        if m and len(out["questions"]) < 3:
            out["questions"].append(m.group(2).strip())
    m = re.search(r"```text\n(.*?)```", text, re.S)
    if m:
        out["prompt"] = m.group(1).strip()
    return out


def collect(root, out_dir, lang, project=None):
    t = TEXT[lang]
    prog = parse_progress(root)
    board = {
        "root": root,
        "project": os.path.abspath(project or root),
        "lang": lang,
        "version": (prog or {}).get("version", ""),
        "released": (prog or {}).get("released", ""),
        "released_at": (prog or {}).get("released_at", ""),
        "updated_at": (prog or {}).get("updated_at", ""),
        "about": (prog or {}).get("about" if lang == "zh" else "about_en", ""),
        "steps": (prog or {}).get("steps", []),
        "gaps": (prog or {}).get("gaps", []),
        "workflow": parse_workflow(root),
        "gate": parse_gate(project or root),
        "checks": collect_checks(root),
        "scale": count_scale(root),
        "coverage": coverage_of(project),
        "cleaning": parse_cleaning(out_dir),
        "ladder": parse_ladder(out_dir)[0],
        "events": parse_ladder(out_dir)[1],
        "searches": count_searches(out_dir),
        "labels": t,
        "spec": parse_spec(project or root),
    }
    done = len([s for s in board["steps"] if s.get("status") == "done"])
    board["build_done"] = done
    board["build_total"] = len(board["steps"])
    board["stages"] = stage_details(root, board["workflow"], board["gate"],
                                    board["checks"], board["project"])
    return board


# --------------------------------------------------------------------------- #
# 终端状态板
# --------------------------------------------------------------------------- #
W = 78


def rule(ch="-" * W):
    return ch


def bar(frac, width=28, fill="=", empty="."):
    n = int(round(max(0.0, min(1.0, frac)) * width))
    return fill * n + empty * (width - n)


def stage_records(gate):
    """把 gate 里的 stages 归一成 [{"stage": int, ...}]，dict 与 list 两种写法都吃。"""
    raw = (gate or {}).get("stages") or {}
    if isinstance(raw, dict):
        pairs = list(raw.items())
    elif isinstance(raw, list):
        pairs = list(enumerate(raw))
    else:
        return []
    out = []
    for key, rec in pairs:
        if not isinstance(rec, dict):
            continue
        try:
            sid = int(rec.get("stage", key))
        except (TypeError, ValueError):
            continue
        item = dict(rec)
        item["stage"] = sid
        out.append(item)
    return out


def stage_status(board, sid):
    g = board["gate"]
    if not g:
        return "todo", ""
    cur = g.get("current", 0)
    for rec in stage_records(g):
        if rec.get("stage") == sid:
            status = rec.get("status", "open")
            if status == "open" and sid > cur:
                return "todo", ""
            return status, rec.get("answer", "")
    return "todo", ""


def render_text(board):
    t = board["labels"]
    L = []
    head = " %s  |  %s" % (t["title"], t["subtitle"])
    L.append("=" * W)
    L.append(head[:W])
    L.append(" %s %s   |   %s %s (%s)" % (
        t["version"], board["version"] or "?", t["released"],
        board["released"] or "?", board["released_at"] or "?"))
    if board["updated_at"]:
        L.append(" %s %s" % (t["updated"], board["updated_at"]))
    L.append("=" * W)

    # 一、现在在哪
    L.append("")
    L.append(" " + t["s1"])
    L.append(rule())
    for i, s in enumerate(board["workflow"][:9]):
        sid = s["id"]
        status, answer = stage_status(board, sid)
        name = s["name_zh"] if board["lang"] == "zh" else s["name_en"]
        label = {"passed": t["status_passed"], "forced": t["status_forced"],
                 "open": t["status_open"], "todo": t["status_todo"]}.get(status, status)
        mark = {"passed": "[x]", "forced": "[~]", "open": "[?]", "todo": "[ ]"}.get(status, "[ ]")
        L.append(" %s [%d] %s %s %s" % (mark, sid, pad(name, 18), pad(s["skill"], 15), label))
    if not board["gate"]:
        L.append("")
        L.append(" " + t["no_gate"])
        L.append("   " + t["hint_start"])
    else:
        L.append("")
        L.append(" %s: %s" % (t["question"], board["gate"].get("question", "")))
        if board["gate"].get("blocked"):
            L.append(" " + t["blocked"])

    # 二、接下来做什么
    L.append("")
    L.append(" " + t["s2"])
    L.append(rule())
    nxt = 0 if not board["gate"] else board["gate"].get("current", 0)
    nxt = min(nxt, max(0, len(board["workflow"]) - 1)) if board["workflow"] else 0
    if board["workflow"]:
        s = board["workflow"][nxt]
        L.append(" %s%s[%d] %s" % (t["next"], "：" if board["lang"] == "zh" else ": ", s["id"],
                                   s["name_zh"] if board["lang"] == "zh" else s["name_en"]))
        L.append(" %s:" % t["ask"])
        gate_text = s["gate_zh"] if board["lang"] == "zh" else s["gate_en"]
        for chunk in wrap(gate_text, W - 4):
            L.append("   " + chunk)
    open_gaps = [g for g in board["gaps"] if g.get("status") in ("open", "partial")]
    if open_gaps:
        L.append("")
        L.append(" %s:" % t["gaps"])
        for g in open_gaps:
            title = g.get("title") or g.get("name") or g.get("desc") or ""
            head = "   %s  %s " % (g.get("id", "?"), pad(g.get("status", "?"), 8))
            for i, chunk in enumerate(wrap(title, W - dwidth(head))):
                L.append(head + chunk if i == 0 else " " * dwidth(head) + chunk)
    else:
        L.append("")
        L.append(" %s." % t["no_gaps"])

    # 三、检查器与规模
    L.append("")
    L.append(" " + t["s3"])
    L.append(rule())
    if board["checks"]:
        for c in board["checks"]:
            zh, en = CHECK_NAMES.get(c["skill"], (c["skill"], c["skill"]))
            name = zh if board["lang"] == "zh" else en
            frac = (c["passed"] / c["total"]) if c["total"] else 0
            L.append(" %s %d/%d  %s" % (pad(name, 18), c["passed"], c["total"], bar(frac, 24)))
    else:
        L.append(" " + t["no_checks"])
    sc = board["scale"]
    L.append("")
    L.append(" %s: %d %s / %d %s / %d %s / %d %s / %d %s" % (
        t["scale"], sc["files"], t["files"], sc["md"], t["md"], sc["skills"],
        t["skills"], sc["domains"], t["domains"], sc["datadict"], t["dd"]))
    if board["build_total"]:
        L.append(" %s: %d/%d %s  %s" % (
            t["build"], board["build_done"], board["build_total"], t["steps_done"],
            bar(board["build_done"] / board["build_total"], 24)))

    # 四、数据处理进度
    L.append("")
    L.append(" " + t["s4"])
    L.append(rule())
    if board["cleaning"]:
        L.append(" " + t["cleaning"])
        for r in board["cleaning"]:
            before = r["before"] if r["before"] is not None else 0
            after = r["after"] if r["after"] is not None else 0
            L.append("   %s %s %4d -> %4d   %s" % (
                pad(str(r["step"]), 3), pad(r["action"], 30), before, after, r["delta"]))
        rows = [(r["after"] or 0) for r in board["cleaning"]]
        if rows:
            top = max(rows) or 1
            L.append("   " + bar(rows[-1] / top, 44, "#", ".") + "  %d" % rows[-1])
    else:
        L.append(" " + t["no_data"])
        L.append("   " + t["hint_data"])

    if board["ladder"]:
        L.append("")
        L.append(" " + t["ladder"])
        for r in board["ladder"]:
            L.append("   %s %s %.4f (%.4f)   %s" % (
                pad(str(r["step"]), 3), pad(r["what"], 32), r["coef"], r["se"], r["change"]))
    if board["events"]:
        L.append("")
        L.append(" " + t["events"])
        for e in board["events"]:
            L.append("   %s %.4f (%.4f)" % (pad(e["term"], 13), e["coef"], e["se"]))
    if board["searches"]:
        L.append("")
        L.append(" %s: %d" % (t["searches"], board["searches"]))

    L.append("")
    L.append("=" * W)
    return "\n".join(L)


def dwidth(s):
    """显示宽度：中日韩字符占两格。"""
    import unicodedata
    w = 0
    for ch in s:
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F", "A") else 1
    return w


def pad(s, width, align="left"):
    """按显示宽度补齐或截断，中英混排也能对齐。"""
    out = ""
    w = 0
    for ch in s:
        cw = 2 if __import__("unicodedata").east_asian_width(ch) in ("W", "F", "A") else 1
        if w + cw > width:
            break
        out += ch
        w += cw
    return out + " " * (width - w) if align == "left" else " " * (width - w) + out


def wrap(text, width):
    out, line = [], ""
    for ch in text:
        line += ch
        if len(line) >= width:
            out.append(line)
            line = ""
    if line:
        out.append(line)
    return out or [""]


# --------------------------------------------------------------------------- #
# 单文件看板（内联 CSS + 内联 SVG，无外部资源、无脚本）
# --------------------------------------------------------------------------- #
def svg_stage_funnel(board, width=680, height=88):
    t = board["labels"]
    n = max(1, len(board["workflow"][:9]))
    gap = 8
    cw = (width - gap * (n - 1)) / n
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" role="img">' % (width, height, height)]
    for i, s in enumerate(board["workflow"][:9]):
        status, _ = stage_status(board, s["id"])
        fill = {"passed": "#1f3864", "forced": "#b58105", "open": "#7fa3d8", "todo": "#e6ebf4"}[status]
        fg = "#ffffff" if status in ("passed", "forced", "open") else "#5a6b86"
        x = i * (cw + gap)
        parts.append('<rect x="%.1f" y="10" width="%.1f" height="42" rx="7" fill="%s"></rect>'
                     % (x, cw, fill))
        label = s["name_zh"] if board["lang"] == "zh" else s["name_en"]
        parts.append('<text x="%.1f" y="30" text-anchor="middle" font-size="10.5" fill="%s">%s</text>'
                     % (x + cw / 2, fg, esc(label[:8])))
        parts.append('<text x="%.1f" y="45" text-anchor="middle" font-size="9" fill="%s">%d</text>'
                     % (x + cw / 2, fg, s["id"]))
        mark = {"passed": "done", "forced": "forced", "open": "open", "todo": "todo"}[status]
        mark_txt = {"passed": t["status_passed"], "forced": t["status_forced"],
                    "open": t["status_open"], "todo": t["status_todo"]}[status]
        parts.append('<text x="%.1f" y="68" text-anchor="middle" font-size="9.5" fill="#5a6b86">%s</text>'
                     % (x + cw / 2, esc(mark_txt[:10])))
        parts.append('<text x="%.1f" y="81" text-anchor="middle" font-size="8" fill="#98a6bd">%s</text>'
                     % (x + cw / 2, mark))
    parts.append("</svg>")
    return "".join(parts)


def svg_check_bars(board, width=680):
    rows = board["checks"]
    if not rows:
        return ""
    row_h, pad = 26, 6
    height = row_h * len(rows) + pad * 2
    label_w = 150
    bar_w = width - label_w - 70
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" role="img">' % (width, height, height)]
    for i, c in enumerate(rows):
        zh, en = CHECK_NAMES.get(c["skill"], (c["skill"], c["skill"]))
        name = zh if board["lang"] == "zh" else en
        frac = (c["passed"] / c["total"]) if c["total"] else 0
        y = pad + i * row_h
        parts.append('<text x="0" y="%d" font-size="11" fill="#243b61">%s</text>'
                     % (y + 12, esc(name[:16])))
        parts.append('<rect x="%d" y="%d" width="%d" height="13" rx="6.5" fill="#e6ebf4"></rect>'
                     % (label_w, y + 2, bar_w))
        good = (frac >= 0.999)
        parts.append('<rect x="%d" y="%d" width="%.1f" height="13" rx="6.5" fill="%s"></rect>'
                     % (label_w, y + 2, bar_w * frac, "#2e7d32" if good else "#b58105"))
        parts.append('<text x="%d" y="%d" font-size="10.5" fill="#5a6b86">%d/%d</text>'
                     % (label_w + bar_w + 8, y + 12, c["passed"], c["total"]))
    parts.append("</svg>")
    return "".join(parts)


def svg_cleaning(board, width=680, height=210):
    rows = board["cleaning"]
    if not rows:
        return ""
    vals = [(r["after"] or 0) for r in rows]
    top = max(vals) or 1
    n = len(rows)
    gap = 14
    bw = (width - gap * (n + 1)) / n
    base = height - 40
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" role="img">' % (width, height, height)]
    for i, r in enumerate(rows):
        v = r["after"] or 0
        h = (base - 20) * (v / top)
        x = gap + i * (bw + gap)
        y = base - h
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="5" fill="#1f3864"></rect>'
                     % (x, y, bw, h))
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="10.5" fill="#243b61">%d</text>'
                     % (x + bw / 2, y - 5, v))
        parts.append('<text x="%.1f" y="%d" text-anchor="middle" font-size="9.5" fill="#5a6b86">%s</text>'
                     % (x + bw / 2, base + 14, esc(str(r["step"]))))
        if r["delta"]:
            parts.append('<text x="%.1f" y="%d" text-anchor="middle" font-size="8.5" fill="#98a6bd">%s</text>'
                         % (x + bw / 2, base + 27, esc(r["delta"][:10])))
    parts.append("</svg>")
    return "".join(parts)


def svg_ladder(board, width=680, height=220):
    rows = board["ladder"]
    if not rows:
        return ""
    lo = min(r["coef"] - r["se"] for r in rows)
    hi = max(r["coef"] + r["se"] for r in rows)
    span = (hi - lo) or 1.0
    n = len(rows)
    gap = 40
    cw = (width - gap * (n + 1)) / n
    top, bottom = 20, height - 40
    def y_of(v):
        return bottom - (bottom - top) * ((v - lo) / span)
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" role="img">' % (width, height, height)]
    parts.append('<line x1="0" y1="%.1f" x2="%d" y2="%.1f" stroke="#cfd9e8" stroke-width="1"></line>'
                 % (y_of(0), width, y_of(0)))
    for i, r in enumerate(rows):
        x = gap + i * (cw + gap) + cw / 2
        y1, y2 = y_of(r["coef"] - r["se"]), y_of(r["coef"] + r["se"])
        parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#7fa3d8" stroke-width="2"></line>'
                     % (x, y1, x, y2))
        parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#7fa3d8" stroke-width="2"></line>'
                     % (x - 6, y1, x + 6, y1))
        parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#7fa3d8" stroke-width="2"></line>'
                     % (x - 6, y2, x + 6, y2))
        parts.append('<circle cx="%.1f" cy="%.1f" r="4.5" fill="#1f3864"></circle>'
                     % (x, y_of(r["coef"])))
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="10" fill="#243b61">%.4f</text>'
                     % (x, y_of(r["coef"]) - 10, r["coef"]))
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="9.5" fill="#5a6b86">%s</text>'
                     % (x, bottom + 15, esc(str(r["step"]))))
        if r["change"]:
            parts.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="8.5" fill="#98a6bd">%s</text>'
                         % (x, bottom + 28, esc(r["change"][:9])))
    parts.append("</svg>")
    return "".join(parts)


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def render_html(board):
    t = board["labels"]
    sc = board["scale"]
    stage_svg = svg_stage_funnel(board)
    check_svg = svg_check_bars(board) or '<p class="dim">%s</p>' % esc(t["no_checks"])
    clean_svg = svg_cleaning(board) or ('<p class="dim">%s</p><pre>%s</pre>'
                                        % (esc(t["no_data"]), esc(t["hint_data"])))
    ladder_svg = svg_ladder(board) or ('<p class="dim">%s</p><pre>%s</pre>'
                                       % (esc(t["no_data"]), esc(t["hint_ladder"])))

    order = []
    if board["gate"] and board["workflow"]:
        cur = board["gate"].get("current", 0)
        cur = min(cur, len(board["workflow"]) - 1)
        order.append(board["workflow"][cur])
    open_gaps = [g for g in board["gaps"] if g.get("status") in ("open", "partial")]
    todos = []
    for g in open_gaps:
        title = g.get("title") or g.get("name") or ""
        todos.append('<li><b>%s</b> <span class="pill">%s</span> %s</li>'
                     % (esc(str(g.get("id", ""))), esc(str(g.get("status", ""))), esc(title)))
    next_html = ""
    if order:
        s = order[0]
        name = s["name_zh"] if board["lang"] == "zh" else s["name_en"]
        gate_text = s["gate_zh"] if board["lang"] == "zh" else s["gate_en"]
        next_html = ('<div class="card"><h3>%s [%d] %s</h3><p class="ask">%s</p><p class="dim">%s</p></div>'
                     % (esc(t["next"]), s["id"], esc(name), esc(gate_text), esc(t["ask"])))
    else:
        next_html = ('<div class="card"><p class="dim">%s</p><pre>%s</pre></div>'
                     % (esc(t["no_gate"]), esc(t["hint_start"])))

    gaps_html = "".join(todos) or ('<li class="dim">%s</li>' % esc(t["no_gaps"]))

    return """<!DOCTYPE html>
<html lang="%(lang)s"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s · dashboard</title>
<style>
:root { --ink:#16233c; --dim:#6b7a95; --line:#e2e8f2; --bg:#f6f8fc; --navy:#1f3864; }
* { box-sizing: border-box; }
body { margin:0; padding:28px 22px 60px; background:var(--bg); color:var(--ink);
  font:15px/1.65 "Segoe UI","Microsoft YaHei",system-ui,sans-serif; }
.wrap { max-width: 820px; margin: 0 auto; }
header h1 { margin:0 0 4px; font-size:24px; letter-spacing:.3px; }
header p { margin:0; color:var(--dim); font-size:13px; }
.meta { margin:14px 0 22px; font-size:12.5px; color:var(--dim); }
.card { background:#fff; border:1px solid var(--line); border-radius:12px;
  padding:18px 20px; margin:0 0 16px; box-shadow:0 1px 2px rgba(22,35,60,.04); }
.card h3 { margin:0 0 10px; font-size:15px; color:var(--navy); }
.ask { margin:6px 0 8px; padding:10px 12px; background:#f2f6fd; border-left:3px solid var(--navy);
  border-radius:6px; font-size:14px; }
.dim { color:var(--dim); font-size:12.5px; }
pre { background:#f5f7fb; border:1px solid var(--line); border-radius:8px;
  padding:10px 12px; font-size:12.5px; overflow-x:auto; }
ul { margin:6px 0 0; padding-left:20px; }
li { margin:4px 0; }
.pill { display:inline-block; padding:1px 7px; border-radius:999px; background:#eef2f9;
  color:#41527a; font-size:11px; margin-right:6px; }
.grid { display:flex; gap:14px; flex-wrap:wrap; }
.kv { flex:1 1 130px; background:#fff; border:1px solid var(--line); border-radius:10px; padding:12px 14px; }
.kv b { display:block; font-size:20px; color:var(--navy); }
.kv span { font-size:12px; color:var(--dim); }
nav { display:flex; gap:8px; flex-wrap:wrap; margin:0 0 18px; }
nav a { text-decoration:none; font-size:13px; color:#41527a; background:#fff;
  border:1px solid var(--line); border-radius:999px; padding:6px 14px; }
nav a:hover { border-color:var(--navy); color:var(--navy); }
section { scroll-margin-top: 14px; }
footer { margin-top:26px; font-size:12px; color:var(--dim); }
</style></head>
<body><div class="wrap">
<header>
  <h1>%(title)s</h1>
  <p>%(subtitle)s</p>
</header>
<div class="meta">%(version_label)s %(version)s &nbsp;|&nbsp; %(released_label)s %(released)s (%(released_at)s)
 &nbsp;|&nbsp; %(updated)s %(updated_at)s</div>

<nav>
  <a href="#s1">%(s1)s</a><a href="#s2">%(s2)s</a><a href="#s3">%(s3)s</a><a href="#s4">%(s4)s</a>
</nav>

<section id="s1" class="card">
  <h3>%(s1)s</h3>
  %(stage_svg)s
  %(gate_html)s
</section>

<section id="s2" class="card">
  <h3>%(s2)s</h3>
  %(next_html)s
  <h3 style="margin-top:16px">%(gaps)s</h3>
  <ul>%(gaps_html)s</ul>
</section>

<section id="s3" class="card">
  <h3>%(s3)s</h3>
  <div class="grid">
    <div class="kv"><b>%(n_files)d</b><span>%(l_files)s</span></div>
    <div class="kv"><b>%(n_md)d</b><span>%(l_md)s</span></div>
    <div class="kv"><b>%(n_skills)d</b><span>%(l_skills)s</span></div>
    <div class="kv"><b>%(n_domains)d</b><span>%(l_domains)s</span></div>
  </div>
  <h3 style="margin-top:16px">%(checks)s</h3>
  %(check_svg)s
</section>

<section id="s4" class="card">
  <h3>%(s4)s</h3>
  <h3>%(cleaning)s</h3>
  %(clean_svg)s
  <h3 style="margin-top:16px">%(ladder)s</h3>
  %(ladder_svg)s
</section>

<footer>%(html_note)s &middot; %(updated)s %(updated_at)s</footer>
</div></body></html>
""" % {
        "lang": "zh" if board["lang"] == "zh" else "en",
        "title": esc(t["title"]), "subtitle": esc(t["subtitle"]),
        "version_label": esc(t["version"]), "released_label": esc(t["released"]),
        "updated": esc(t["updated"]), "version": esc(board["version"]),
        "released": esc(board["released"]), "released_at": esc(board["released_at"]),
        "updated_at": esc(board["updated_at"]),
        "s1": esc(t["s1"]), "s2": esc(t["s2"]), "s3": esc(t["s3"]), "s4": esc(t["s4"]),
        "gaps": esc(t["gaps"]), "gaps_html": gaps_html,
        "stage_svg": stage_svg,
        "gate_html": ('<p class="ask">%s</p>' % esc(board["gate"].get("question", "")))
                     if board["gate"] else "",
        "next_html": next_html,
        "checks": esc(t["checks"]), "check_svg": check_svg,
        "cleaning": esc(t["cleaning"]), "clean_svg": clean_svg,
        "ladder": esc(t["ladder"]), "ladder_svg": ladder_svg,
        "n_files": sc["files"], "n_md": sc["md"], "n_skills": sc["skills"], "n_domains": sc["domains"],
        "l_files": esc(t["files"]), "l_md": esc(t["md"]),
        "l_skills": esc(t["skills"]), "l_domains": esc(t["domains"]),
        "html_note": esc(t["html_note"]),
    }


# --------------------------------------------------------------------------- #
def generated_at():
    """面板专用的生成时间（ISO8601，UTC，秒级）。只进面板文件，不进 stdout。"""
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def panel_path(project):
    """看板数据落点：<项目>/.econ-kit/dashboard.json"""
    return os.path.join(os.path.abspath(project), ".econ-kit", "dashboard.json")


def write_panel(root, out_dir, lang, project):
    """把同一份数据写进项目里，返回落点路径。"""
    board = collect(root, out_dir, lang, project)
    slim = dict(board)
    slim.pop("labels", None)
    slim["generated_at"] = generated_at()
    target = panel_path(project)
    parent = os.path.dirname(target)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    text = json.dumps(slim, ensure_ascii=False, indent=2) + "\n"
    targets = [target]
    # 研究项目常在工作区下面几层；会话的工作区根才是面板真正读的地方，
    # 所以凡祖先目录里已经有 .econ-kit/ 的，一并写一份（最多上溯 3 层）。
    here = os.path.dirname(os.path.abspath(project))
    for _ in range(3):
        hub = os.path.join(here, ".econ-kit")
        if os.path.isdir(hub):
            extra = os.path.join(hub, "dashboard.json")
            if os.path.abspath(extra) not in [os.path.abspath(t) for t in targets]:
                targets.append(extra)
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    for t in targets:
        d = os.path.dirname(t)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(t, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return target


def write_panel_near(kit_root, project=None, lang="zh"):
    """给 gate.py / spec.py 用：猜出 out_dir，再写看板数据。

    猜法：项目里有 output/ 就用它，否则用库自带的 output/。
    任何异常都吞掉——看板数据不该拖垮闸门。
    """
    try:
        proj = os.path.abspath(project or os.getcwd())
        cand = os.path.join(proj, "output")
        out_dir = cand if os.path.isdir(cand) else os.path.join(kit_root, "output")
        return write_panel(kit_root, out_dir, lang, proj)
    except Exception:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="one page: where you are, what comes next")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--root", default=ROOT, help="kit root (default: parent of scripts/)")
    ap.add_argument("--out-dir", default=None, help="where the runnable scripts wrote output/")
    ap.add_argument("--project", default=".",
                    help="the research project directory holding .econ-kit/ (default: cwd)")
    ap.add_argument("--html", default=None, help="write a single-file dashboard here")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--json-out", default=None,
                    help="write the JSON here instead of <project>/.econ-kit/dashboard.json")
    ap.add_argument("--no-panel", action="store_true",
                    help="do not touch <project>/.econ-kit/dashboard.json")
    a = ap.parse_args(argv)

    root = os.path.abspath(a.root)
    if not os.path.exists(os.path.join(root, "state", "progress.json")):
        print("not a kit root: %s" % root, file=sys.stderr)
        print("expected: state/progress.json under it", file=sys.stderr)
        return 2
    out_dir = os.path.abspath(a.out_dir) if a.out_dir else os.path.join(root, "output")

    project = os.path.abspath(a.project)
    board = collect(root, out_dir, a.lang, project)

    target = None
    if not a.no_panel:
        if a.json_out:
            target = os.path.abspath(a.json_out)
            slim = dict(board)
            slim.pop("labels", None)
            slim["generated_at"] = generated_at()
            parent = os.path.dirname(target)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            with io.open(target, "w", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(slim, ensure_ascii=False, indent=2) + "\n")
        else:
            # 默认走 write_panel：带 generated_at，并同时写进上层已有的 .econ-kit
            target = write_panel(root, out_dir, a.lang, project)
        board["panel_path"] = target

    if a.json:
        slim = dict(board)
        slim.pop("labels", None)
        print(json.dumps(slim, ensure_ascii=False, indent=2))
        return 0

    if a.html:
        html = render_html(board)
        target = os.path.abspath(a.html)
        parent = os.path.dirname(target)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with io.open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
        print("wrote %s (%d bytes)" % (target, os.path.getsize(target)))
        return 0

    print(render_text(board))
    if target:
        print("")
        print("panel data: %s" % target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
