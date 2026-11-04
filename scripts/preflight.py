# -*- coding: utf-8 -*-
"""四槽位体检：把一句研究题目拆成四个槽，缺哪个就列出来。

用法：
    python scripts/preflight.py "我想研究家庭收入情况对阶层认同的影响"
    python scripts/preflight.py --lang en "the effect of family income on class identity"
    python scripts/preflight.py --json "..."

退出码：
    0  四槽齐全，可以进入工序第 2 步
    1  有缺项或只有推断，应先问用户
    2  用法错误

这个脚本不判断题目好坏，只判断"现在能不能开始动手"。
判断是规则的、确定的：同一句话跑两次，输出完全一样。
"""

import io
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PASS = 0
ASK = 1
USAGE = 2

# 槽位里出现这些词，就算"点了名"。中英混排，因为用户可能中英混着说。
UNIT_WORDS = [
    "家庭", "家户", "住户", "个体", "个人", "居民", "劳动者", "工人", "员工", "农户",
    "企业", "公司", "上市公司", "厂商", "银行", "网点", "学校", "学生", "班级", "医院",
    "县", "区县", "城市", "地级市", "省份", "省", "村", "村庄", "社区", "街道", "行业",
    "household", "family", "individual", "person", "respondent", "worker", "employee",
    "firm", "company", "listed", "plant", "bank", "school", "student", "hospital",
    "county", "city", "province", "village", "community", "industry",
]

TREATMENT_WORDS = [
    "收入", "工资", "教育", "培训", "补贴", "价格", "税收", "税率", "政策", "改革", "试点",
    "督察", "碳价", "碳定价", "碳市场", "距离", "搬迁", "通车", "高铁", "地铁", "医保",
    "低保", "新农合", "排污许可", "限产", "关税", "汇率", "利率", "信贷", "生育政策",
    "义务教育法", "户籍", "土地", "拆迁", "补助", "奖学金", "助学金", "是否参加",
    "income", "wage", "earnings", "education", "training", "subsidy", "price", "tax",
    "policy", "reform", "pilot", "distance", "rail", "transit", "insurance", "tariff",
    "interest", "credit", "quota", "permit",
]

OUTCOME_WORDS = [
    "认同", "阶层认同", "主观阶层", "幸福感", "满意度", "健康", "自评健康", "消费",
    "储蓄", "投资", "就业", "创业", "劳动供给", "工时", "成绩", "绩点", "升学", "生育",
    "迁移", "流动", "污染", "排放", "空气质量", "犯罪", "死亡率", "产量", "生产率",
    "出口", "进口", "创新", "专利", "信任", "态度",
    "identity", "happiness", "wellbeing", "satisfaction", "health", "consumption",
    "saving", "investment", "employment", "entrepreneurship", "fertility", "migration",
    "pollution", "emission", "crime", "mortality", "productivity", "export", "import",
    "innovation", "patent", "trust",
]

# 明确点出过"谁来比"的说法
COMPARE_GIVEN = [
    "对照", "控制组", "处理组", "比较组", "相比", "与非", "相比之", "相对于",
    "比较", "相比", "比一比", "没被覆盖", "未覆盖", "未受", "没有被", "对照组",
    "control group", "treated group", "comparison group", "counterfactual", "versus",
    "compare", "compared", " vs ", "compared with", "compared to", "not covered",
]

# 提了设计，但没说清谁是比照对象
COMPARE_IMPLIED = [
    "双重差分", "did", "DID", "diff-in-diff", "事件研究", "event study", "断点", "RDD",
    "工具变量", "IV", "合成控制", "synthetic control", "前后对比", "before and after",
]

ZH_SLOTS = [
    ("unit", "分析单元"),
    ("treatment", "处理变量"),
    ("outcome", "结果变量"),
    ("comparison", "对照组"),
]

STATUS_ZH = {"given": "见", "implied": "推", "missing": "缺"}
STATUS_EN = {"given": "yes", "implied": "assumed", "missing": "MISSING"}

ZH_QUESTIONS = {
    "unit": "你的分析单元是什么？换句话说，你手上那批数据的一行，是一条家庭、一个人、一家企业，还是一个县？",
    "treatment": "让一部分人处在处理状态的那件事，具体是哪一件？它是从哪一年、对哪一批单位开始的？",
    "outcome": "你要解释的那件事，在数据里是哪一列、或者哪一道问卷题？它的取值是什么样子？",
    "comparison": "谁来当对照组？是同一批人政策前后的变化，是没被覆盖的单位，还是相邻地区、相近的人？",
}

ZH_HINT = {
    "unit": "没说一行数据是什么",
    "treatment": "没点明哪件事把人分成了两类",
    "outcome": "没说要看哪个结果",
    "comparison": "没说谁跟谁比",
}

EN_QUESTIONS = {
    "unit": "What is the unit of analysis? In other words, one row of your data is one household, one person, one firm, or one county?",
    "treatment": "What puts some units in the treated state? Which specific event, starting in which year, for which units?",
    "outcome": "Which column, or which survey item, measures the thing you are trying to explain, and what do its values look like?",
    "comparison": "Who is the comparison group: the same units before and after, units the policy never covered, or neighbouring units and similar people?",
}

EN_HINT = {
    "unit": "no statement of what one row of data is",
    "treatment": "no statement of what sorts units into treated and untreated",
    "outcome": "no statement of which outcome is being explained",
    "comparison": "no statement of who is being compared with whom",
}

ZH_TITLE = "preflight 四槽位体检"
EN_TITLE = "preflight: four-slot check"


def words_in(text, words):
    """返回 (第一个命中的词, 命中词的位置)；没命中返回 (None, -1)。"""
    low = text.lower()
    best = (None, 10 ** 9)
    for w in words:
        i = low.find(w.lower())
        if i >= 0 and i < best[1]:
            best = (w, i)
    return best


FILLER = (
    "我现在想研究", "我现在想看看", "我想研究", "我想看看", "我想知道", "我想做",
    "我想问", "研究一下", "研究", "分析一下", "分析", "考察一下", "考察",
    "看看", "探讨", "估计一下", "估计", "测算", "评估一下", "评估",
    "i want to study", "i want to look at", "i want to", "study of", "study",
    "the effect of", "the impact of", "effect of", "impact of",
)


def strip_filler(s):
    s = s.strip().strip("，,。.：:；;的 ")
    changed = True
    while changed:
        changed = False
        low = s.lower()
        for f in FILLER:
            if low.startswith(f):
                s = s[len(f):].strip("，,。.：:；;的 ")
                changed = True
                break
    return s


def split_by_dui(text):
    """中文里 "X 对 Y 的影响" 是最强的信号：X 是处理，Y 是结果。"""
    k = -1
    for marker in ("的影响", "的作用", "的效应", "影响", "作用", "效应"):
        k = text.find(marker)
        if k > 0:
            break
        k = -1
    left = text if k < 0 else text[:k]
    j = left.rfind("对")
    if j <= 0 or j >= len(left) - 1:
        return None, None
    x = left[:j]
    for sep in ("，", ",", "；", ";", "。", "、", "　"):
        if sep in x:
            x = x.rsplit(sep, 1)[1]
    return strip_filler(x), strip_filler(left[j + 1:])


def split_by_of_on(text):
    low = text.lower()
    for kw in ("effect of", "impact of", "influence of", "effects of", "impacts of"):
        k = low.find(kw)
        if k >= 0:
            rest = text[k + len(kw):]
            j = rest.lower().find(" on ")
            if j > 0:
                return strip_filler(rest[:j]), strip_filler(rest[j + 4:])
    return None, None


def analyse(text, lang):
    slots = {}
    treat_phrase, out_phrase = split_by_dui(text)
    if not treat_phrase:
        treat_phrase, out_phrase = split_by_of_on(text)

    unit_word, unit_at = words_in(text, UNIT_WORDS)
    if unit_word:
        # 这个词如果只出现在处理变量那几个字里（"家庭收入"里的"家庭"），算推断，不算用户点明。
        inside = treat_phrase and (unit_word.lower() in treat_phrase.lower())
        slots["unit"] = ("implied", unit_word) if inside else ("given", unit_word)
    else:
        slots["unit"] = ("missing", "")

    if treat_phrase:
        slots["treatment"] = ("given", treat_phrase[:40])
    else:
        w, _ = words_in(text, TREATMENT_WORDS)
        slots["treatment"] = ("implied", w) if w else ("missing", "")

    if out_phrase:
        slots["outcome"] = ("given", out_phrase[:40])
    else:
        w, _ = words_in(text, OUTCOME_WORDS)
        slots["outcome"] = ("implied", w) if w else ("missing", "")

    w, _ = words_in(text, COMPARE_GIVEN)
    if w:
        slots["comparison"] = ("given", w.strip())
    else:
        w, _ = words_in(text, COMPARE_IMPLIED)
        slots["comparison"] = ("implied", w) if w else ("missing", "")

    # 提问顺序：先问"一行数据是什么"，再问"谁跟谁比"（最常被忘掉），最后问变量。
    order = ["unit", "comparison", "treatment", "outcome"]
    todo = [s for s in order if slots[s][0] != "given"]
    bank = ZH_QUESTIONS if lang == "zh" else EN_QUESTIONS
    questions = [bank[s] for s in todo[:3]]
    return slots, todo, questions


def render(text, slots, todo, questions, lang):
    zh = lang == "zh"
    names = {k: (n if zh else n) for k, n in ZH_SLOTS}
    if not zh:
        names = {"unit": "unit", "treatment": "treatment", "outcome": "outcome",
                 "comparison": "comparison"}
    status = STATUS_ZH if zh else STATUS_EN
    hint = ZH_HINT if zh else EN_HINT
    filled = sum(1 for k in slots if slots[k][0] == "given")

    print("=" * 68)
    print((ZH_TITLE if zh else EN_TITLE))
    print("=" * 68)
    print(("题目：" if zh else "Question: ") + text)
    print("")
    for key, label in ZH_SLOTS:
        st, val = slots[key]
        shown = val if val else (hint[key] if zh else hint[key])
        line = "  %-8s [%s]  %s" % (label if zh else names[key], status[st], shown)
        print(line)
    print("")
    if zh:
        print("四槽里已经说清的：%d / 4" % filled)
    else:
        print("Slots given explicitly: %d / 4" % filled)

    if not todo:
        print("")
        print("四槽齐全。" if zh else "All four slots are filled.")
        print(("可以进入工序第 2 步；下一步是数据覆盖矩阵，不是写代码。" if zh
               else "You may enter step 2 of the skill; next is the data coverage matrix, not code."))
        return PASS

    print("")
    if zh:
        print("还差 %d 项。先问下面这 %d 个问题，一次问完，问完停下等回答：" % (len(todo), len(questions)))
    else:
        print("%d slot(s) still open. Ask these %d question(s), all at once, then stop and wait:"
              % (len(todo), len(questions)))
    for i, q in enumerate(questions, 1):
        print("  %d. %s" % (i, q))
    if len(todo) > 3:
        print(("  （另外 %d 项等这三问有答案之后再问，别一次抛太多。）" % (len(todo) - 3)) if zh
              else ("  (%d more slot(s); ask them after these are answered, do not dump them all.)"
                    % (len(todo) - 3)))
    print("")
    print("结论：先问再答。四槽没齐之前不要进入工序第 2 步。" if zh
          else "Verdict: ask before you answer. Do not enter step 2 with a slot still open.")
    print(("preflight: %d/4 slots filled" % filled))
    return ASK


def main(argv):
    lang = "zh"
    as_json = False
    parts = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--lang" and i + 1 < len(argv):
            lang = argv[i + 1].lower()
            i += 2
            continue
        if a == "--json":
            as_json = True
            i += 1
            continue
        if a in ("-h", "--help"):
            print(__doc__)
            return PASS
        parts.append(a)
        i += 1

    text = " ".join(parts).strip().strip('"').strip("'")
    if not text:
        print(__doc__)
        return USAGE

    slots, todo, questions = analyse(text, lang)

    if as_json:
        out = {
            "question": text,
            "slots": {k: {"status": v[0], "value": v[1]} for k, v in slots.items()},
            "filled": sum(1 for k in slots if slots[k][0] == "given"),
            "open": todo,
            "questions": questions,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return PASS if not todo else ASK

    return render(text, slots, todo, questions, lang)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
