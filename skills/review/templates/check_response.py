"""Machine check for a point-by-point response letter.

Five checks, one line each, so that the answer to "did you answer every
comment and say where you changed the paper" is a run rather than a memory:

    python skills/review/templates/check_response.py skills/review/expected/response-letter.md --lang en
    python skills/review/templates/check_response.py skills/review/expected/response-letter-zh.md --lang zh

Rules. Every ``### Comment N`` heading needs exactly one ``Response``
paragraph. That paragraph has to name a place in the manuscript - a page, a
section, a table, a figure or an appendix. At least one response has to be a
refusal or a partial acceptance that gives a reason, because a letter where
every comment is accepted hides the one disagreement the editor should see.
No sentence may dismiss the referee. The letter needs a summary paragraph
before the first comment.

Statuses: ``OK`` passes, ``WEAK`` present but incomplete, ``MISSING`` absent.
The exit code is 0 only when all five pass, and the last line always reads
``N/5 checks passed``.

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
HEADING = re.compile(r"^#{1,6}\s+\S")
COMMENT = re.compile(r"^#{1,6}\s*(?:comment|意见|审稿意见|referee\s+comment)\s*(\d+)?", re.I)
RESPONSE = re.compile(r"^\s*(?:\*\*)?(?:response|reply|回应|答复)(?:\*\*)?\s*[.:：]?\s*", re.I)
QUOTE = re.compile(r"^\s*>")

LOCATION_RES = [
    re.compile(r"\bp+\.\s*\d+", re.I),
    re.compile(r"\bpage\s+\d+", re.I),
    re.compile(r"第\s*\d+\s*页"),
    re.compile(r"\bsection\s+\d+", re.I),
    re.compile(r"\bappendix\b", re.I),
    re.compile(r"第[一二三四五六七八九十百\d]+\s*节"),
    re.compile(r"第\s*\d+\s*节"),
    re.compile(r"\btable\s+[A-Z]?\d+", re.I),
    re.compile(r"\bfigure\s+[A-Z]?\d+", re.I),
    re.compile(r"\bfig\.\s*[A-Z]?\d+", re.I),
    re.compile(r"表\s*[A-Z]?\d+"),
    re.compile(r"图\s*[A-Z]?\d+"),
    re.compile(r"附录\s*[A-Z一二三四五六]?\d*"),
    re.compile(r"\blines?\s+\d+", re.I),
    re.compile(r"第\s*\d+\s*行"),
]

REFUSAL_RES = [
    re.compile(r"\bwe\s+(?:do\s+not|don't|cannot|decline|keep|retain|maintain)", re.I),
    re.compile(r"\bnot\s+(?:appropriate|feasible|possible)\b", re.I),
    re.compile(r"\bpartially\s+accept", re.I),
    re.compile(r"\brespectfully\b", re.I),
    re.compile(r"不改"),
    re.compile(r"不修改"),
    re.compile(r"不接受"),
    re.compile(r"不予修改"),
    re.compile(r"保留原"),
    re.compile(r"部分接受"),
    re.compile(r"无法"),
    re.compile(r"难以"),
]

DISMISSIVE_EN = [
    "obviously",
    "clearly wrong",
    "misread",
    "absurd",
    "ridiculous",
    "embarrassing",
    "sloppy",
    "incompetent",
    "surprised that",
    "fails to appreciate",
    "as any reader knows",
    "simply wrong",
]
DISMISSIVE_ZH = [
    "显然",
    "误读",
    "荒谬",
    "可笑",
    "水平有限",
    "不专业",
    "令人失望",
    "无法理解",
    "常识性错误",
    "根本不懂",
]
THANKS_EN = re.compile(r"\b(?:thank|thanks|grateful|appreciate)", re.I)
THANKS_ZH = re.compile(r"感谢|致谢|谢谢")


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def split_blocks(text: str) -> tuple:
    """Return (preamble, [(comment_text, response_text), ...])."""
    lines = text.split("\n")
    preamble = []
    blocks = []
    current_comment = None
    current_response = None

    def flush() -> None:
        if current_comment is not None:
            blocks.append((current_comment, current_response or ""))

    for line in lines:
        stripped = line.strip()
        if COMMENT.match(stripped):
            flush()
            current_comment = stripped
            current_response = None
            continue
        if RESPONSE.match(stripped):
            current_response = [RESPONSE.sub("", stripped)]
            continue
        if current_comment is None:
            preamble.append(line)
            continue
        if current_response is None:
            if not QUOTE.match(stripped) and stripped:
                current_comment = f"{current_comment}\n{stripped}"
        else:
            if HEADING.match(stripped):
                flush()
                current_comment = None
                current_response = None
                preamble.append(line)
                continue
            current_response.append(stripped)
    flush()
    return "\n".join(preamble).strip(), [
        (c, "\n".join(r).strip() if isinstance(r, list) else r) for c, r in blocks
    ]


def has_location(text: str) -> bool:
    return any(pattern.search(text) for pattern in LOCATION_RES)


def count_words_or_chars(text: str, lang: str) -> int:
    return len(CJK.findall(text)) if lang == "zh" else len(WORD.findall(text))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a point-by-point response letter against five rules.")
    parser.add_argument("path", help="response letter file (.md or .txt)")
    parser.add_argument("--lang", choices=("en", "zh"), help="language of the letter")
    parser.add_argument("--style", choices=("en", "zh"), help="alias of --lang for the target journal")
    args = parser.parse_args()

    lang = args.style or args.lang or "en"
    text = read_text(args.path)
    preamble, blocks = split_blocks(text)

    results = []

    # 1. every comment answered by exactly one response
    comments = len(blocks)
    answered = sum(1 for _comment, response in blocks if response.strip())
    if comments == 0:
        results.append(("意见与回应成对", ("MISSING", "没有识别到 ### Comment 或 ### 意见 标题")))
    elif answered == comments:
        results.append(("意见与回应成对", ("OK", f"{comments} 条意见，{answered} 条回应")))
    else:
        results.append(
            ("意见与回应成对", ("MISSING", f"{answered}/{comments} 条意见有回应，缺 {comments - answered} 条"))
        )

    # 2. every response names where the manuscript changed
    located = sum(1 for _comment, response in blocks if response.strip() and has_location(response))
    if comments == 0:
        results.append(("回应指明改在何处", ("MISSING", "没有可检查的回应")))
    elif located == answered:
        results.append(("回应指明改在何处", ("OK", f"{located}/{answered} 条回应给出页码、节或表图号")))
    else:
        results.append(
            ("回应指明改在何处", ("WEAK", f"{located}/{answered} 条回应给出位置，其余只说已改"))
        )

    # 3. at least one refusal or partial acceptance with a reason
    refusals = [response for _comment, response in blocks if any(p.search(response) for p in REFUSAL_RES)]
    if refusals:
        results.append(("至少一条不改并说明理由", ("OK", f"{len(refusals)} 条属拒绝或部分接受")))
    elif comments:
        results.append(("至少一条不改并说明理由", ("MISSING", "每条意见都接受了，没有说明为何不改")))
    else:
        results.append(("至少一条不改并说明理由", ("MISSING", "没有可检查的回应")))

    # 4. no dismissive wording
    lowered = text.lower()
    hits = [word for word in DISMISSIVE_EN if word in lowered]
    hits += [word for word in DISMISSIVE_ZH if word in text]
    if hits:
        results.append(("无情绪化措辞", ("WEAK", "命中：" + "、".join(sorted(set(hits))[:5]))))
    else:
        results.append(("无情绪化措辞", ("OK", "没有贬低审稿人的措辞")))

    # 5. summary before the first comment
    size = count_words_or_chars(preamble, lang)
    thanks = THANKS_ZH if lang == "zh" else THANKS_EN
    unit = "个汉字" if lang == "zh" else "个英文词"
    floor = 100 if lang == "zh" else 50
    if size >= floor and thanks.search(preamble):
        results.append(("有总述段", ("OK", f"第一条意见前有 {size} {unit}")))
    elif size > 0 and thanks.search(preamble):
        results.append(("有总述段", ("WEAK", f"第一条意见前只有 {size} {unit}，不足 {floor}")))
    elif size > 0:
        results.append(("有总述段", ("WEAK", f"第一条意见前有 {size} {unit}，但没有致谢")))
    else:
        results.append(("有总述段", ("MISSING", "第一条意见前没有总述段")))

    print(f"check_response — lang={lang}, file={args.path}")
    passed = 0
    for index, (label, (verdict, detail)) in enumerate(results, 1):
        if verdict == "OK":
            passed += 1
        print(f"[{verdict}] {index}/5 {label}: {detail}")
    print(f"{passed}/5 checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
