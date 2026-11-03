"""Machine check for an abstract, before it goes into the submission system.

Seven checks, one line each. This exists so that the abstract rule in
``skills/writing/SKILL.md`` can be run against a real file instead of being
read and forgotten:

    python skills/writing/templates/check_abstract.py skills/writing/expected/abstract.md --lang en
    python skills/writing/templates/check_abstract.py skills/writing/expected/abstract-zh.md --lang zh

Thresholds: 100 to 150 words for an English abstract, 200 to 300 characters
for a Chinese one (the default in SKILL.md, which is the two Chinese-journal
practice this kit was built from), 3 to 5 keywords, JEL codes on an English
submission, 中图分类号 on a Chinese one.

Statuses: ``OK`` passes, ``WEAK`` is present but not what the rule asks for,
``MISSING`` is absent. The exit code is 0 only when all seven pass, and the
last line always reads ``N/7 checks passed``.

A quantified result written as ``[待核实]`` plus a unit passes the number
check on purpose: the point of the run is to catch a missing magnitude, not
to force the author to invent one. The report flags every placeholder so it
can be filled before submission.

Pure standard library, no network, deterministic output.
"""

from __future__ import annotations

import argparse
import re
import sys

try:  # make Chinese output readable on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CJK = re.compile(r"[\u4e00-\u9fff]")
WORD = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)*")
DIGIT = re.compile(r"\d")
FIRST_PERSON_EN = re.compile(r"(?<![A-Za-z])I(?![A-Za-z])")
FIRST_PERSON_ZH = re.compile(r"我(?!们)")
SELF_REFERENCE = [r"this paper", r"this study", r"this article", r"本文", r"本研究"]

METHODS = [
    r"difference[- ]in[- ]differences?",
    r"\bDID\b",
    r"\bDD\b",
    r"event[- ]study",
    r"staggered",
    r"instrumental[- ]variables?",
    r"\bIV\b",
    r"two[- ]stage[- ]least[- ]squares?",
    r"\b2SLS\b",
    r"regression[- ]discontinuity",
    r"\bRDD\b",
    r"synthetic[- ]control",
    r"propensity[- ]score",
    r"randomi[sz]ed",
    r"fixed[- ]effects?",
    r"双重差分",
    r"倍差法",
    r"事件研究",
    r"动态效应",
    r"工具变量",
    r"两阶段最小二乘",
    r"断点回归",
    r"合成控制",
    r"倾向得分",
    r"双重机器学习",
    r"随机对照",
    r"准自然实验",
    r"固定效应",
]

UNITS = (
    r"percentage\s+points?|percent|%|pp\b"
    r"|个百分点|百分点|倍|元|亿元|万元|美元|系数|标准差"
)
PLACEHOLDER = r"\[\s*(?:待核实|待填|to\s*fill|verify)\s*\]"
QUANT_REAL = re.compile(r"\d+(?:\.\d+)?\s*(?:" + UNITS + r")", re.I)
QUANT_PLACEHOLDER = re.compile(r"(?:" + PLACEHOLDER + r")\s*(?:" + UNITS + r")", re.I)
PLACEHOLDER_ANY = re.compile(PLACEHOLDER, re.I)

KEYWORD_LINE = re.compile(r"^\s*\**\s*(?:key\s*words?|keywords?|关键词)\s*\**\s*[:：]\s*(.+)$", re.I)
JEL_LINE = re.compile(r"JEL", re.I)
CLC_LINE = re.compile(r"中图分类号")
JEL_CODE = re.compile(r"\b[A-Z]\d{1,2}\b")
CLC_CODE = re.compile(r"\b[A-Z]{1,2}\d+(?:\.\d+)?\b")
HEADING = re.compile(r"^#{1,6}\s+\S")
ABSTRACT_HEADING = re.compile(r"^#{1,6}\s*\**\s*(?:abstract|摘要)\s*\**\s*$", re.I)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def split_parts(text: str) -> dict:
    """Separate body, keyword line, and classification line."""
    lines = text.split("\n")
    body, keywords, jel, clc = [], "", "", ""
    start = 0
    for i, line in enumerate(lines):
        if ABSTRACT_HEADING.match(line.strip()):
            start = i + 1
            break
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped:
            body.append("")
            continue
        match = KEYWORD_LINE.match(stripped)
        if match:
            keywords = match.group(1)
            continue
        if JEL_LINE.search(stripped) and re.search(r"[:：]", stripped):
            jel = stripped
            continue
        if CLC_LINE.search(stripped):
            clc = stripped
            continue
        if HEADING.match(stripped):
            break
        body.append(stripped)
    return {
        "body": "\n".join(body).strip(),
        "keywords": keywords.strip(),
        "jel": jel,
        "clc": clc,
    }


def status(ok: bool, weak: bool = False) -> str:
    if ok:
        return "OK"
    return "WEAK" if weak else "MISSING"


def check_length(body: str, lang: str) -> tuple:
    if lang == "zh":
        count = len(CJK.findall(body))
        label = f"{count} 个汉字"
        ok, weak = 200 <= count <= 300, 0 < count
        detail = f"{label}（区间 200 到 300）"
    else:
        count = len(WORD.findall(body))
        label = f"{count} 个英文词"
        ok, weak = 100 <= count <= 150, 0 < count
        detail = f"{label}（区间 100 到 150）"
    return status(ok, weak), detail


def check_method(body: str) -> tuple:
    for pattern in METHODS:
        match = re.search(pattern, body, re.I)
        if match:
            return "OK", match.group(0)
    return "MISSING", "没有出现识别策略或估计方法的名字"


def check_quantity(body: str) -> tuple:
    match = QUANT_REAL.search(body)
    if match:
        return "OK", match.group(0).strip()
    match = QUANT_PLACEHOLDER.search(body)
    if match:
        return "OK", f"{match.group(0).strip()}（占位，提交前填实际数值）"
    if DIGIT.search(body):
        return "WEAK", "有数字但没有单位，读不出量级"
    return "MISSING", "没有量化结果"


def check_self_reference(body: str) -> tuple:
    for pattern in SELF_REFERENCE:
        match = re.search(pattern, body, re.I)
        if match:
            return "OK", match.group(0)
    return "WEAK", "没有用「本文」或「this paper」作主语"


def check_first_person(body: str, lang: str) -> tuple:
    patterns = [FIRST_PERSON_ZH, FIRST_PERSON_EN] if lang == "zh" else [FIRST_PERSON_EN, FIRST_PERSON_ZH]
    for pattern in patterns:
        match = pattern.search(body)
        if match:
            return "WEAK", f"出现第一人称 {match.group(0)!r}"
    return "OK", "没有第一人称"


def check_keywords(keywords: str) -> tuple:
    if not keywords:
        return "MISSING", "没有关键词行"
    parts = [p.strip(" .。;；") for p in re.split(r"[,，、;；]", keywords)]
    parts = [p for p in parts if p]
    ok = 3 <= len(parts) <= 5
    return status(ok, bool(parts)), f"{len(parts)} 个关键词（要求 3 到 5 个）"


def check_codes(parts: dict, lang: str) -> tuple:
    if lang == "zh":
        codes = CLC_CODE.findall(parts["clc"])
        if not parts["clc"]:
            return "MISSING", "没有中图分类号行"
        if not codes:
            return "WEAK", "有中图分类号行但没有分类号"
        return "OK", "、".join(codes)
    codes = JEL_CODE.findall(parts["jel"])
    if not parts["jel"]:
        return "MISSING", "没有 JEL codes 行"
    if not codes:
        return "WEAK", "有 JEL 行但没有分类码"
    return "OK", "、".join(codes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check an abstract against seven mechanical rules.")
    parser.add_argument("path", help="abstract file (.md or .txt)")
    parser.add_argument("--lang", choices=("en", "zh"), help="language of the abstract")
    parser.add_argument("--style", choices=("en", "zh"), help="alias of --lang for the target journal")
    args = parser.parse_args()

    lang = args.style or args.lang or "en"
    text = read_text(args.path)
    parts = split_parts(text)
    body = parts["body"]

    results = [
        ("字数区间", check_length(body, lang)),
        ("识别策略或方法", check_method(body)),
        ("量化结果", check_quantity(body)),
        ("自称方式", check_self_reference(body)),
        ("第一人称", check_first_person(body, lang)),
        ("关键词个数", check_keywords(parts["keywords"])),
        ("分类号", check_codes(parts, lang)),
    ]

    print(f"check_abstract — lang={lang}, file={args.path}")
    passed = 0
    for index, (label, (verdict, detail)) in enumerate(results, 1):
        if verdict == "OK":
            passed += 1
        print(f"[{verdict}] {index}/7 {label}: {detail}")

    placeholders = len(PLACEHOLDER_ANY.findall(body))
    if placeholders:
        print(f"note: {placeholders} 处占位符待填，提交前必须替换")
    print(f"{passed}/7 checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
