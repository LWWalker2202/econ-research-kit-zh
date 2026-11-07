# -*- coding: utf-8 -*-
"""journal_pack.py — 把目标期刊的硬要求压成一张可勾的清单（只读，不改任何文件）。

用法：
    python scripts/journal_pack.py --list
    python scripts/journal_pack.py "QJE"
    python scripts/journal_pack.py "经济学季刊" --out .econ-kit/journal-pack.md
    python scripts/journal_pack.py "JEEM" --json

退出码：0 找到 / 1 没这本刊 / 2 用法错误
"""
import argparse, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "skills", "tables-figures", "data", "journal-packs.json")

CN = {
    "confidence": {"vendor": "须知", "measured": "实测", "unverified": "待核实"},
    "k": {"abstract": "摘要", "jel": "JEL", "tables": "表", "figures": "图",
          "title": "表题", "lines": "横线", "note": "表注", "decimals": "小数位",
          "punct": "标点", "references": "参考文献", "data": "数据",
          "appendix": "附录"},
    "title": "投稿清单",
    "tier": "层级",
    "lang": "语言",
    "check": "提交前逐条打勾",
    "verify": "标 [待核实] 的条目请对照该刊最新投稿须知确认，不要直接照抄。",
    "unknown": "没有这本刊：",
    "known": "现有：",
}


def load(path=DATA):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def find(data, query):
    q = (query or "").strip().lower().replace(" ", "")
    for j in data.get("journals", []):
        names = [j.get("name", ""), j.get("id", "")] + list(j.get("aliases") or [])
        if any(q == n.lower().replace(" ", "") for n in names if n):
            return j
    for j in data.get("journals", []):
        names = [j.get("name", "")] + list(j.get("aliases") or [])
        if any(q and q in n.lower().replace(" ", "") for n in names if n):
            return j
    return None


def render(j, lang="zh"):
    mark = CN["confidence"]
    out = []
    out.append("# %s · %s" % (j["name"], CN["title"]))
    out.append("")
    out.append("- %s：%s" % (CN["tier"], j.get("tier", "?")))
    out.append("- %s：%s" % (CN["lang"], j.get("lang", "?")))
    out.append("")
    out.append("| | 要求 | 依据 |")
    out.append("|---|---|---|")
    todos = []
    for it in j.get("items", []):
        c = it.get("confidence", "unverified")
        name = CN["k"].get(it.get("k", ""), it.get("k", ""))
        out.append("| %s | %s | [%s] |" % (name, it.get("v", ""), mark.get(c, c)))
        if c == "unverified":
            todos.append(it)
    out.append("")
    out.append("## %s" % CN["check"])
    out.append("")
    for it in j.get("items", []):
        name = CN["k"].get(it.get("k", ""), it.get("k", ""))
        out.append("- [ ] %s" % name)
    out.append("")
    if todos:
        out.append("## 待核实")
        out.append("")
        for it in todos:
            out.append("- %s：%s" % (CN["k"].get(it.get("k", ""), it.get("k", "")), it.get("v", "")))
        out.append("")
    out.append("> " + CN["verify"])
    out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="turn a journal's rules into a checklist")
    ap.add_argument("journal", nargs="?", help="journal name or alias")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--out", help="write the checklist to this path")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    try:
        data = load()
    except (OSError, ValueError) as e:
        print("cannot read %s: %s" % (DATA, e), file=sys.stderr)
        return 2

    if a.list or not a.journal:
        for j in data.get("journals", []):
            print("%-22s %-3s %s" % (j["name"], j.get("tier", "?"), "/".join(j.get("aliases") or [])[:40]))
        print("")
        print("%d journals" % len(data.get("journals", [])))
        return 0

    j = find(data, a.journal)
    if not j:
        print(CN["unknown"] + a.journal, file=sys.stderr)
        print(CN["known"] + ", ".join(x["name"] for x in data.get("journals", [])), file=sys.stderr)
        return 1

    if a.json:
        text = json.dumps(j, ensure_ascii=False, indent=2)
    else:
        text = render(j, a.lang)
    if a.out:
        out = os.path.abspath(a.out)
        d = os.path.dirname(out)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
        print("wrote %s" % out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())