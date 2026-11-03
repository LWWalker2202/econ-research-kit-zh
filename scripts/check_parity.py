#!/usr/bin/env python3
"""Parity check between the English edition and the Chinese mirror.

Rules enforced
--------------
1. Both repositories contain exactly the same set of files (same relative paths).
2. Files that must be byte-identical are byte-identical:
   VERSION, glossary.yaml, index/actions.csv, and everything under scripts/.
3. Every Markdown file has the same heading level sequence in both editions.
4. Files with a fixed section contract have the exact section titles
   (skills/, domains/, data-dict/, teaching/).
5. Every Markdown file has the same number of acceptance items ("- [ ]").
6. Every Markdown file uses the same set of {{placeholders}}.
7. Each skills/<name>/SKILL.md declares name: <name> in its front matter.

Usage
-----
    python scripts/check_parity.py
    python scripts/check_parity.py --en /path/to/en --zh /path/to/zh
"""

from __future__ import annotations

import argparse
import os
import re
import sys

try:  # make output readable on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

SKIP_DIRS = {".git", "__pycache__", ".idea", ".vscode", "node_modules"}
BYTE_IDENTICAL = ["VERSION", "glossary.yaml", "index/actions.csv"]

SKILL_EN = [
    "When to use this", "Inputs", "Procedure", "Outputs (artifacts)",
    "Acceptance", "Common failure modes", "Interfaces with other skills",
    "Where to look up domain details",
]
SKILL_ZH = [
    "什么时候进这里", "输入", "步骤", "输出（artifacts）", "验收",
    "常见失败模式", "与其它 skill 的接口", "领域细节去哪查",
]
INST_EN = ["Institutional background", "Timeline", "Ready-to-cite paragraphs", "Sources"]
INST_ZH = ["制度背景", "时间线", "可直接引用的段落", "引用来源"]
MEAS_EN = ["Constructing the treatment variable", "Identification assumptions by definition", "Common construction errors"]
MEAS_ZH = ["处理变量怎么构造", "各定义的识别假设", "常见构造错误"]
DATA_EN = ["Data sources", "Variables and definitions", "Coverage", "Known issues"]
DATA_ZH = ["数据来源", "变量与口径", "覆盖范围", "已知问题"]
PITF_EN = ["What referees ask", "How to respond", "Where it goes wrong"]
PITF_ZH = ["审稿人常问什么", "怎么回应", "容易翻车的地方"]
DICT_EN = ["Basic information", "Variables", "Known issues", "Access"]
DICT_ZH = ["基本信息", "变量表", "已知问题", "获取方式"]
TEACH_EN = ["How to use this at this level", "Which skills to use", "What not to do"]
TEACH_ZH = ["这一档的用法", "该用哪些 skill", "不该做的事"]


def norm(text: str) -> str:
    t = text.strip()
    t = t.replace("（", "(").replace("）", ")").replace("：", ":")
    t = re.sub(r"\s+", " ", t)
    return t.lower()


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def collect(root: str) -> dict:
    """relative path -> absolute path for every file under root."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            absolute = os.path.join(dirpath, name)
            rel = os.path.relpath(absolute, root).replace("\\", "/")
            out[rel] = absolute
    return out


def strip_non_content(text: str) -> str:
    """Remove YAML front matter and fenced code blocks."""
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                lines = lines[i + 1:]
                break
    kept, fence = [], False
    for line in lines:
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if not fence:
            kept.append(line)
    return "\n".join(kept)


def headings(text: str):
    out = []
    for line in strip_non_content(text).split("\n"):
        m = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        if m:
            out.append((len(m.group(1)), m.group(2)))
    return out


def acceptance_count(text: str) -> int:
    return len(re.findall(r"^\s*-\s*\[\s*\]", text, re.M))


def placeholders(text: str) -> set:
    return set(re.findall(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}", text))


def sha(path: str) -> str:
    import hashlib

    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def expected_sections(lang: str):
    """rel-path predicate -> canonical list of ## titles."""
    if lang == "en":
        table = [
            (lambda p: re.match(r"skills/[^/]+/SKILL\.md$", p), SKILL_EN),
            (lambda p: re.match(r"domains/[^/]+/institutional\.md$", p), INST_EN),
            (lambda p: re.match(r"domains/[^/]+/measures\.md$", p), MEAS_EN),
            (lambda p: re.match(r"domains/[^/]+/data\.md$", p), DATA_EN),
            (lambda p: re.match(r"domains/[^/]+/pitfalls\.md$", p), PITF_EN),
            (lambda p: re.match(r"data-dict/(?!README|_)[^/]+\.md$", p), DICT_EN),
            (lambda p: re.match(r"teaching/[^/]+\.md$", p), TEACH_EN),
        ]
    else:
        table = [
            (lambda p: re.match(r"skills/[^/]+/SKILL\.md$", p), SKILL_ZH),
            (lambda p: re.match(r"domains/[^/]+/institutional\.md$", p), INST_ZH),
            (lambda p: re.match(r"domains/[^/]+/measures\.md$", p), MEAS_ZH),
            (lambda p: re.match(r"domains/[^/]+/data\.md$", p), DATA_ZH),
            (lambda p: re.match(r"domains/[^/]+/pitfalls\.md$", p), PITF_ZH),
            (lambda p: re.match(r"data-dict/(?!README|_)[^/]+\.md$", p), DICT_ZH),
            (lambda p: re.match(r"teaching/[^/]+\.md$", p), TEACH_ZH),
        ]
    return table


def main() -> int:
    ap = argparse.ArgumentParser()
    if REPO.endswith("-zh"):
        default_en, default_zh = REPO[: -len("-zh")], REPO
    else:
        default_en, default_zh = REPO, REPO + "-zh"
    ap.add_argument("--en", default=default_en)
    ap.add_argument("--zh", default=default_zh)
    args = ap.parse_args()

    en, zh = args.en, args.zh
    problems, warnings = [], []

    if not os.path.isdir(en):
        print(f"[FAIL] English repository not found: {en}")
        return 2
    if not os.path.isdir(zh):
        print(f"[FAIL] Chinese repository not found: {zh}")
        return 2

    files_en, files_zh = collect(en), collect(zh)

    only_en = sorted(set(files_en) - set(files_zh))
    only_zh = sorted(set(files_zh) - set(files_en))
    for path in only_en:
        problems.append(f"file only in EN: {path}")
    for path in only_zh:
        problems.append(f"file only in ZH: {path}")

    common = sorted(set(files_en) & set(files_zh))

    # 2. byte-identical set
    for path in BYTE_IDENTICAL:
        if path in files_en and path in files_zh:
            if sha(files_en[path]) != sha(files_zh[path]):
                problems.append(f"not byte-identical: {path}")
    for path in common:
        # scripts/ and the book PDFs are language-neutral: they must match byte for byte.
        # book/README.md is language-specific, so it is compared as markdown like the rest.
        if path.startswith("scripts/") or (path.startswith("book/") and path.endswith(".pdf")):
            if sha(files_en[path]) != sha(files_zh[path]):
                problems.append(f"not byte-identical: {path}")

    # 3-7. markdown structure
    md_files = [p for p in common if p.endswith(".md")]
    checked = 0
    for path in md_files:
        text_en, text_zh = read(files_en[path]), read(files_zh[path])
        h_en, h_zh = headings(text_en), headings(text_zh)

        if not h_en:
            problems.append(f"no heading: {path}")
        if [lvl for lvl, _ in h_en] != [lvl for lvl, _ in h_zh]:
            problems.append(
                f"heading level sequence differs: {path} "
                f"(EN {[l for l, _ in h_en]} vs ZH {[l for l, _ in h_zh]})"
            )

        if acceptance_count(text_en) != acceptance_count(text_zh):
            problems.append(
                f"acceptance count differs: {path} "
                f"(EN {acceptance_count(text_en)} vs ZH {acceptance_count(text_zh)})"
            )

        if placeholders(text_en) != placeholders(text_zh):
            problems.append(
                f"placeholder set differs: {path} "
                f"({sorted(placeholders(text_en) ^ placeholders(text_zh))})"
            )

        for lang, repo_path, text, hh in (("en", files_en[path], text_en, h_en), ("zh", files_zh[path], text_zh, h_zh)):
            for pred, canon in expected_sections(lang):
                if not pred(path):
                    continue
                got = [t for lvl, t in hh if lvl == 2]
                if len(got) != len(canon):
                    problems.append(
                        f"[{lang}] {path}: expected {len(canon)} level-2 sections, got {len(got)} -> {got}"
                    )
                else:
                    for i, (g, c) in enumerate(zip(got, canon)):
                        if norm(g) != norm(c):
                            problems.append(
                                f"[{lang}] {path}: section {i + 1} is '{g}', expected '{c}'"
                            )
        checked += 1

    # 7. skills front matter name
    for path in md_files:
        m = re.match(r"skills/([^/]+)/SKILL\.md$", path)
        if not m:
            continue
        name = m.group(1)
        for lang, repo_path in (("en", files_en[path]), ("zh", files_zh[path])):
            text = read(repo_path)
            fm = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
            if not fm:
                problems.append(f"[{lang}] {path}: missing front matter")
                continue
            nm = re.search(r"^name:\s*(\S+)\s*$", fm.group(1), re.M)
            if not nm:
                problems.append(f"[{lang}] {path}: front matter has no name")
            elif nm.group(1) != name:
                problems.append(
                    f"[{lang}] {path}: name '{nm.group(1)}' != directory '{name}'"
                )

    # VERSION consistency
    if "VERSION" in files_en and "VERSION" in files_zh:
        v_en = read(files_en["VERSION"]).strip()
        v_zh = read(files_zh["VERSION"]).strip()
        if v_en != v_zh:
            problems.append(f"VERSION differs: {v_en} vs {v_zh}")

    if warnings:
        print("WARNINGS")
        for item in warnings:
            print("  -", item)

    if problems:
        print(f"FAIL — {len(problems)} problem(s) across {checked} markdown files")
        for item in problems:
            print("  -", item)
        return 1

    print(f"OK — parity holds. {len(common)} files, {checked} markdown files compared.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
