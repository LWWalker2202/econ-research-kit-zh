#!/usr/bin/env python3
"""Content lint for econ-research-kit (runs on one repository at a time).

Checks that are mechanical and cheap. Nothing here judges whether the
economics is right; it only catches the failures that a human reviewer
would catch in ten minutes and that an author always misses.

    python scripts/lint_content.py .
"""

from __future__ import annotations

import os
import re
import sys

try:  # make Chinese output readable on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SKIP_DIRS = {".git", "__pycache__", ".idea", ".vscode", "node_modules", "vendor", "output", "cache", "local"}
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF"
    "\U00002190-\U000021FF\U00002B00-\U00002BFF]"
)
DOI = re.compile(r"10\.\d{4,9}/[^\s)|<>\"]+")
VERSION_NUMBER = re.compile(r"\b\d+\.\d+\.\d+\b")
BANNED = [
    "根据具体情况调整", "注意数据质量", "根据需要调整", "视情况而定",
    "adjust as needed", "depending on the situation", "various factors",
    "TODO", "TBD", "FIXME", "xxx", "XXX",
]
PLACEHOLDER_FILL = re.compile(r"\[(待填|待核实|to fill|verify)\]")


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def strip_front_matter(text: str):
    fm = ""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[1], parts[2].lstrip("\n")
    return fm, text


def check_table_pipes(rel: str, text: str, problems: list):
    """Inside a markdown table block every row must have the same pipe count."""
    block, start = [], 0

    def flush():
        if len(block) < 2:
            return
        counts = {len(re.findall(r"(?<!\\)\|", row)) for row in block}
        if len(counts) > 1:
            problems.append(
                f"{rel}: table starting at line {start} has inconsistent pipe counts {sorted(counts)}"
            )

    for i, line in enumerate(text.split("\n"), 1):
        if line.strip().startswith("|"):
            if not block:
                start = i
            block.append(line)
        else:
            flush()
            block = []
    flush()


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    problems, stats = [], {"files": 0, "todo": 0}

    # The project's own version is legitimate to mention; software package
    # versions are not.
    own_version = ""
    version_file = os.path.join(root, "VERSION")
    if os.path.exists(version_file):
        own_version = read(version_file).strip()

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            absolute = os.path.join(dirpath, name)
            rel = os.path.relpath(absolute, root).replace("\\", "/")
            text = read(absolute)
            stats["files"] += 1

            if not text.strip():
                problems.append(f"{rel}: empty file")
                continue

            if not text.endswith("\n"):
                problems.append(f"{rel}: file does not end with a newline")

            fm, body = strip_front_matter(text)

            # emoji
            hit = EMOJI.search(body)
            if hit:
                problems.append(f"{rel}: emoji character {hit.group(0)!r}")

            # banned filler
            for phrase in BANNED:
                if phrase in body:
                    problems.append(f"{rel}: banned filler or placeholder text {phrase!r}")

            # version numbers (software versions age badly). Catalog ids such as
            # 1.6.1 look like versions but are indexing numbers, and they are
            # confined to the meta files that start with an underscore.
            # DOIs also look like versions (10.1080/13504851.2013.799752), so any
            # line carrying a DOI is exempt.
            for m in VERSION_NUMBER.finditer(body):
                if own_version and m.group(0) == own_version:
                    continue
                if rel.startswith("data-dict/_"):
                    continue
                # the ledger and the decision log quote version numbers on purpose
                if rel.startswith("state/") or rel.startswith("decisions/"):
                    continue
                line_start = body.rfind("\n", 0, m.start()) + 1
                line_end = body.find("\n", m.end())
                line = body[line_start:line_end if line_end != -1 else len(body)]
                if DOI.search(line):
                    continue
                problems.append(f"{rel}: version number {m.group(0)!r} — do not pin versions")

            # tables
            check_table_pipes(rel, body, problems)

            # headings: must not skip levels (## -> #### without ###)
            levels = [len(m.group(1)) for m in re.finditer(r"^(#{1,6})\s+\S", body, re.M)]
            for prev, cur in zip(levels, levels[1:]):
                if cur > prev + 1:
                    problems.append(f"{rel}: heading level jumps from {prev} to {cur}")

            # H1 must be first non-empty line of body
            first = next((ln for ln in body.split("\n") if ln.strip()), "")
            if first and not first.startswith("# "):
                problems.append(f"{rel}: first body line is not an H1 heading")

            # skills front matter
            m = re.match(r"skills/([^/]+)/SKILL\.md$", rel)
            if m:
                if not fm:
                    problems.append(f"{rel}: missing YAML front matter")
                else:
                    nm = re.search(r"^name:\s*(\S+)\s*$", fm, re.M)
                    desc = re.search(r"^description:\s*(.+)$", fm, re.M)
                    if not nm:
                        problems.append(f"{rel}: front matter missing 'name'")
                    elif nm.group(1) != m.group(1):
                        problems.append(f"{rel}: name '{nm.group(1)}' != directory '{m.group(1)}'")
                    if not desc:
                        problems.append(f"{rel}: front matter missing 'description'")
                    else:
                        d = desc.group(1)
                        if not re.search(r"[\u4e00-\u9fff]", d):
                            problems.append(f"{rel}: description has no Chinese triggers")
                        if not re.search(r"[A-Za-z]", d):
                            problems.append(f"{rel}: description has no English triggers")

            # acceptance items must be checkable: no vague wording
            for line in body.split("\n"):
                if re.match(r"^\s*-\s*\[\s*\]", line):
                    low = line.lower()
                    if "适当" in low or "良好" in low or "reasonable" in low or "good" in low:
                        problems.append(f"{rel}: vague acceptance item {line.strip()[:60]!r}")

            todo_count = len(PLACEHOLDER_FILL.findall(body))
            stats["todo"] += todo_count

    if problems:
        print(f"FAIL — {len(problems)} problem(s) in {stats['files']} markdown files")
        for item in problems:
            print("  -", item)
        return 1

    print(f"OK — {stats['files']} markdown files clean ({stats['todo']} explicit to-fill markers).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
