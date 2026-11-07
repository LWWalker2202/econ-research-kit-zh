#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""litsearch.py — 从一个话题出发，真的去检索文献，把题目、摘要、被引、OA 链接带回来。

设计原则（与这个库其它脚本一致）：
  1. 零第三方依赖，只用标准库。
  2. 检索结果本身不可复现（数据库天天变），所以**把过程落成文件**：
     search-log.csv 记查询原话、时间、各源命中数；lit-search.json 记全部原始记录。
     想复现同一份表，用 --from-file 重放那个 json，输出逐字节相同。
  3. 不碰任何需要绕过付费墙的渠道，只走 Crossref / OpenAlex 的公开元数据与 OA 链接。

典型用法
  python skills/literature/templates/litsearch.py "最低工资对青少年就业的影响"
  python skills/literature/templates/litsearch.py "minimum wage teenage employment" --year-from 2015 --top 20
  python skills/literature/templates/litsearch.py --from-file output/lit-search.json
  python skills/literature/templates/litsearch.py --verify my-citations.csv
  python skills/literature/templates/litsearch.py "..." --fetch-pdf --pages 3

退出码：0 成功 / 1 没找到东西或核验失败 / 2 用法或网络错误
"""

import argparse
import csv
import io
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

def _kit_version():
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "..", "..", "..", "VERSION")
    try:
        return io.open(p, encoding="utf-8").read().strip() or "0"
    except OSError:
        return "0"

VERSION = _kit_version()
DEFAULT_MAILTO = os.environ.get("ECON_KIT_MAILTO", "2764002263@qq.com")
UA = "econ-research-kit/%s (mailto:%s)" % (VERSION, DEFAULT_MAILTO)
CROSSREF = "https://api.crossref.org/works"
OPENALEX = "https://api.openalex.org/works"
ARXIV = "http://export.arxiv.org/api/query"

TEXT = {
    "zh": {
        "searching": "正在检索 Crossref：%s",
        "hits": "Crossref 命中 %d 条，取前 %d 条。",
        "enrich": "正在用 OpenAlex 按 DOI 补摘要与被引（%d 条）。",
        "no_hits": "没有检索到结果。先放宽年份或换同义词；也可以只跑 python scripts/preflight.py 看题目是不是还没说清。",
        "wrote": "已写出：",
        "log_note": "检索结果会随数据库更新而变化；要复现这张表，用 --from-file 重放 lit-search.json。",
        "next": "下一步：把 lit-hits.csv 逐行补成文献矩阵的七列，然后跑 check_matrix.py。",
        "verify_head": "引用核验（%d 条）",
        "verify_ok": "存在且标题对得上",
        "verify_title": "存在，但标题对不上",
        "verify_missing": "查不到这个 DOI",
        "verify_no_doi": "这一行没有 DOI",
        "verify_sum": "%d/%d 条核验通过。",
        "pdf_skip": "跳过正文抽取（没装 PyMuPDF，或这篇没有 OA 链接）。",
        "pdf_ok": "已抽取正文前 %d 页：",
    },
    "en": {
        "searching": "Searching Crossref: %s",
        "hits": "Crossref returned %d hits; keeping the top %d.",
        "enrich": "Enriching %d records with OpenAlex (abstract, citations).",
        "no_hits": "Nothing found. Widen the year range or add synonyms; or run python scripts/preflight.py to check the question itself.",
        "wrote": "Wrote:",
        "log_note": "Live results change as the databases change; to reproduce this exact table, replay the JSON with --from-file.",
        "next": "Next: fill the candidates into the seven-column matrix, then run check_matrix.py.",
        "verify_head": "Citation check (%d rows)",
        "verify_ok": "exists, title matches",
        "verify_title": "exists, title differs",
        "verify_missing": "no such DOI",
        "verify_no_doi": "row has no DOI",
        "verify_sum": "%d/%d rows verified.",
        "pdf_skip": "Skipping full-text extraction (PyMuPDF missing, or no open-access link).",
        "pdf_ok": "Extracted the first %d pages:",
    },
}


def T(lang, key):
    return TEXT[lang if lang in TEXT else "zh"][key]


# ---------------------------------------------------------------- 期刊分层

JOURNALS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "journals.json")


def load_journals():
    """期刊名 -> 层级。表在 skills/literature/journals.json，改表不用改代码。"""
    try:
        with io.open(JOURNALS_PATH, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return {}, [], []
    name2tier, wp_prefix, wp_venue = {}, [], []
    for tier in ("A", "B"):
        for name in (d.get("general") or {}).get(tier) or []:
            name2tier[clean_ws(name).lower()] = tier
    for dom in (d.get("domains") or {}).values():
        for tier in ("A", "B"):
            for name in dom.get(tier) or []:
                name2tier.setdefault(clean_ws(name).lower(), tier)
    wp_prefix = d.get("working_paper_doi_prefixes") or []
    wp_venue = [clean_ws(v).lower() for v in (d.get("working_paper_venues") or [])]
    return name2tier, wp_prefix, wp_venue


TIER_ORDER = {"A": 0, "B": 1, "C": 2, "WP": 3, "": 4}
_JOURNALS = None


def journals():
    """延迟加载：等 clean_ws 定义好、第一次判层级时再读表。"""
    global _JOURNALS
    if _JOURNALS is None:
        _JOURNALS = load_journals()
    return _JOURNALS


def tier_of(rec):
    name2tier, wp_prefix, wp_venue = journals()
    doi = (rec.get("doi") or "").lower()
    venue = clean_ws(rec.get("venue") or "").lower()
    if any(doi.startswith(p) for p in wp_prefix) or venue in wp_venue:
        return "WP"
    tier = name2tier.get(venue, "")
    return tier or "C"


# ---------------------------------------------------------------- HTTP

class Fetcher(object):
    def __init__(self, proxy=None, mailto=DEFAULT_MAILTO, timeout=25):
        self.mailto = mailto or DEFAULT_MAILTO
        self.timeout = timeout
        handlers = []
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        self.opener = urllib.request.build_opener(*handlers)
        self.calls = 0

    def get(self, url, as_json=True, tries=3):
        last = None
        for i in range(tries):
            req = urllib.request.Request(url, headers={
                "User-Agent": "econ-research-kit/%s (mailto:%s)" % (VERSION, self.mailto),
                "Accept": "application/json" if as_json else "*/*",
            })
            try:
                self.calls += 1
                with self.opener.open(req, timeout=self.timeout) as r:
                    raw = r.read()
                return json.loads(raw.decode("utf-8")) if as_json else raw
            except urllib.error.HTTPError as e:
                last = "HTTP %s %s" % (e.code, e.reason)
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(2 + 3 * i)
                    continue
                raise SystemExit("  !! %s -> %s" % (url[:80], last))
            except Exception as e:
                last = "%s: %s" % (type(e).__name__, e)
                time.sleep(2 + 2 * i)
        raise SystemExit("  !! 取不到数据（%s）。检查网络或代理：%s" % (last, url[:100]))


# ---------------------------------------------------------------- 记录整形

def clean_ws(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def crossref_record(it):
    """把一条 Crossref 记录整成我们自己的形状。"""
    doi = (it.get("DOI") or "").lower()
    title = clean_ws((it.get("title") or [""])[0])
    authors = []
    for a in it.get("author") or []:
        name = clean_ws(("%s %s" % (a.get("given") or "", a.get("family") or "")).strip())
        if name:
            authors.append(name)
    year = None
    for key in ("published-print", "published-online", "issued", "created"):
        parts = (it.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            year = int(parts[0][0])
            break
    venue = clean_ws((it.get("container-title") or [""])[0]) or clean_ws(it.get("publisher") or "")
    return {
        "doi": doi,
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue,
        "type": it.get("type") or "",
        "cited_by": it.get("is-referenced-by-count"),
        "abstract": clean_ws(re.sub(r"<[^>]+>", " ", it.get("abstract") or "")),
        "oa_url": "",
        "pdf_url": "",
        "landing": ("https://doi.org/" + doi) if doi else "",
        "source": "crossref",
    }


def openalex_abstract(inv):
    """OpenAlex 把摘要存成「词 -> 位置列表」，这里还原成正常句子。"""
    if not inv:
        return ""
    pos = {}
    for word, places in inv.items():
        for p in places:
            pos[p] = word
    return clean_ws(" ".join(pos[k] for k in sorted(pos)))


def enrich(fetcher, records, lang, mailto):
    """按 DOI 批量向 OpenAlex 要摘要、被引数、OA 链接。一次 25 个 DOI，避开搜索接口的限流。"""
    dois = [r["doi"] for r in records if r.get("doi")]
    if not dois:
        return records
    print(T(lang, "enrich") % len(dois))
    by_doi = {}
    for i in range(0, len(dois), 25):
        chunk = dois[i:i + 25]
        url = ("%s?filter=doi:%s&per-page=50&select=id,doi,title,abstract_inverted_index,"
               "cited_by_count,best_oa_location,publication_year&mailto=%s"
               % (OPENALEX, "|".join(chunk), urllib.parse.quote(mailto)))
        data = fetcher.get(url)
        for w in data.get("results") or []:
            d = (w.get("doi") or "").replace("https://doi.org/", "").lower()
            if d:
                by_doi[d] = w
        time.sleep(0.3)
    for r in records:
        w = by_doi.get(r.get("doi") or "")
        if not w:
            continue
        r["abstract"] = r.get("abstract") or openalex_abstract(w.get("abstract_inverted_index"))
        if w.get("cited_by_count") is not None:
            r["cited_by"] = w.get("cited_by_count")
        oa = w.get("best_oa_location") or {}
        r["oa_url"] = oa.get("landing_page_url") or ""
        r["pdf_url"] = oa.get("pdf_url") or ""
        r["source"] = "crossref+openalex"
    return records


def search_crossref(fetcher, query, rows, year_from, year_to, mailto, types, sort):
    params = {
        "query.bibliographic": query,
        "rows": str(rows),
        "select": "DOI,title,author,issued,published-print,published-online,container-title,"
                  "publisher,type,is-referenced-by-count,abstract",
        "mailto": mailto,
    }
    if sort == "citations":
        params["sort"] = "is-referenced-by-count"
        params["order"] = "desc"
    else:
        params["sort"] = "relevance"
    filters = []
    if types:
        filters.append("type:" + ",type:".join(types))
    if year_from:
        filters.append("from-pub-date:%d-01-01" % year_from)
    if year_to:
        filters.append("until-pub-date:%d-12-31" % year_to)
    if filters:
        params["filter"] = ",".join(filters)
    url = CROSSREF + "?" + urllib.parse.urlencode(params)
    data = fetcher.get(url)
    msg = data.get("message") or {}
    total = msg.get("total-results") or 0
    recs = [crossref_record(it) for it in msg.get("items") or []]
    return total, [r for r in recs if r["title"]]


def dedupe(records):
    """同一篇论文常以「预印本 + 正式发表」两条记录出现。按规范化标题前 8 个词归组，
    组内留被引最多的那一条（被引一样时优先正式发表期刊）。
    """
    groups = {}
    order = []
    for r in records:
        key = " ".join(norm_title(r.get("title") or "")[:8]) or r.get("doi") or str(len(order))
        if key not in groups:
            groups[key] = r
            order.append(key)
            continue
        cur = groups[key]
        better = ((r.get("cited_by") or 0), r.get("type") == "journal-article") > \
                 ((cur.get("cited_by") or 0), cur.get("type") == "journal-article")
        if better:
            groups[key] = r
    return [groups[k] for k in order]


def blend_rank(records, query):
    """Crossref 的相关度排名不看被引，也看不懂中文；再排一次：
    相关度位置（越靠前越好）+ 被引（取对数，压住百年老文）+ 题目与查询词的词面重合。
    """
    q = set(norm_title(query))
    for i, r in enumerate(records):
        pos = 1.0 / (1.0 + i)
        cites = math.log1p(max(0, r.get("cited_by") or 0)) / 6.0
        words = set(norm_title(r.get("title") or ""))
        hit = (len(q & words) / float(len(q))) if q else 0.0
        bonus = {"A": 2.0, "B": 1.0, "WP": 0.4}.get(r.get("tier") or "", 0.0)
        r["_score"] = 2.0 * pos + 1.2 * min(cites, 1.5) + 3.0 * hit + bonus
    return sorted(records, key=lambda r: (-r["_score"], r.get("doi") or ""))


# ---------------------------------------------------------------- 输出

def slugify(s, limit=40):
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", (s or "").strip()).strip("-")
    return (s[:limit] or "query")


def write_outputs(records, out_dir, query, lang, log_rows, mailto, stamp=None):
    annotate(records)
    os.makedirs(out_dir, exist_ok=True)
    stamp = stamp or datetime.now().strftime("%Y-%m-%d %H:%M")
    js = os.path.join(out_dir, "lit-search.json")
    with io.open(js, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"query": query, "mailto": mailto,
                   "generated": datetime.now().isoformat(timespec="seconds"),
                   "records": records}, f, ensure_ascii=False, indent=2)

    csv_path = os.path.join(out_dir, "lit-hits.csv")
    with io.open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "doi", "title", "authors", "year", "venue", "cited_by",
                    "oa_url", "pdf_url", "abstract"])
        for i, r in enumerate(records, 1):
            w.writerow([i, r.get("doi", ""), r.get("title", ""), "; ".join(r.get("authors") or []),
                        r.get("year") or "", r.get("venue", ""), r.get("cited_by") or "",
                        r.get("oa_url", ""), r.get("pdf_url", ""), r.get("abstract", "")])

    md = os.path.join(out_dir, "lit-hits.md")
    zh = lang == "zh"
    with io.open(md, "w", encoding="utf-8", newline="\n") as f:
        f.write(u"# 检索结果\n\n" if zh else u"# Search results\n\n")
        f.write((u"> 查询：**%s**\n>\n" if zh else u"> Query: **%s**\n>\n") % query)
        f.write(u"> 生成时间：%s ｜ 条数：%d\n\n" % (stamp, len(records))
                if zh else u"> Generated: %s | %d records\n\n" % (stamp, len(records)))
        f.write((u"| # | 层级 | 年份 | 题目 | 出处 | 被引 | DOI |\n|---|---|---|---|---|---|---|\n" if zh else
                 u"| # | Tier | Year | Title | Venue | Cites | DOI |\n|---|---|---|---|---|---|---|\n"))
        for i, r in enumerate(records, 1):
            f.write("| %d | %s | %s | %s | %s | %s | %s |\n" % (
                i, r.get("tier") or "-", r.get("year") or "-",
                (r.get("title") or "").replace("|", "/")[:110],
                (r.get("venue") or "-").replace("|", "/")[:60],
                r.get("cited_by") if r.get("cited_by") is not None else "-",
                ("[%s](%s)" % (r["doi"], r["landing"])) if r.get("doi") else "-"))
        f.write(u"\n## 摘要\n\n" if zh else u"\n## Abstracts\n\n")
        for i, r in enumerate(records, 1):
            ab = r.get("abstract") or (u"（这条没有摘要字段，去原文看）" if zh else "(no abstract in the metadata; read the paper)")
            f.write(u"**[%d] %s**\n\n" % (i, r.get("title") or ""))
            if r.get("authors"):
                f.write(u"%s\n\n" % ", ".join(r["authors"][:6]) + (u" 等" if zh and len(r["authors"]) > 6 else
                                                                  (" et al." if len(r["authors"]) > 6 else "")))
            f.write(("%s\n\n" % ab[:1200]))
            if r.get("pdf_url"):
                f.write((u"[开放获取全文](%s)\n\n" if zh else u"[Open-access PDF](%s)\n\n") % r["pdf_url"])
    log = os.path.join(out_dir, "search-log.csv")
    new = not os.path.exists(log)
    with io.open(log, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "source", "query", "params", "hits", "kept"])
        for row in log_rows:
            w.writerow(row)
    return [js, md, csv_path, log]


def annotate(records):
    """给每条记录补层级；重放旧快照时也能补上，幂等。"""
    for r in records:
        if not r.get("tier"):
            r["tier"] = tier_of(r)
    return records


def print_table(records, lang):
    annotate(records)
    zh = lang == "zh"
    print("\n" + (u"%-3s %-4s %-5s %-44s %-5s %s" % ("#", "层", "年份" if zh else "Year",
                                                   "题目" if zh else "Title",
                                                   "被引" if zh else "Cites", "DOI")
                  if zh else "%-3s %-3s %-5s %-44s %-5s %s" % ("#", "T", "Year", "Title", "Cites", "DOI")))
    for i, r in enumerate(records, 1):
        print("%-3d %-4s %-5s %-44s %-5s %s" % (
            i, r.get("tier") or "-", r.get("year") or "-", (r.get("title") or "")[:42],
            r.get("cited_by") if r.get("cited_by") is not None else "-", r.get("doi") or "-"))
    tally = {}
    for r in records:
        tally[r.get("tier") or "?"] = tally.get(r.get("tier") or "?", 0) + 1
    parts = [u"%s 级 %d 篇" % (k, v) for k, v in sorted(tally.items(), key=lambda kv: TIER_ORDER.get(kv[0], 9))]
    print((u"层级分布：" if zh else "Tier mix: ") + " ｜ ".join(parts))


# ---------------------------------------------------------------- 核验

TITLE_STOP = set("a an the of on in for to and with from by at as is are be this that these those "
                 "does do effect impact evidence new".split())


def norm_title(s):
    s = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", (s or "").lower())
    return [w for w in s.split() if w and w not in TITLE_STOP]


def overlap(a, b):
    A, B = set(norm_title(a)), set(norm_title(b))
    if not A or not B:
        return 0.0
    return len(A & B) / float(min(len(A), len(B)))


def verify(fetcher, path, lang):
    zh = lang == "zh"
    rows = []
    with io.open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rows.append({(k or "").strip().lower(): (v or "").strip() for k, v in row.items()})
    print(T(lang, "verify_head") % len(rows))
    ok = 0
    out = []
    for row in rows:
        doi = (row.get("doi") or row.get("DOI") or "").lower()
        doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
        title = row.get("title") or row.get("题目") or row.get("citation") or ""
        if not doi:
            out.append((title, "no-doi", ""))
            print(u"  [—] %s  %s" % (T(lang, "verify_no_doi"), title[:60]))
            continue
        try:
            data = fetcher.get("%s/doi:%s?mailto=%s" % (OPENALEX, urllib.parse.quote(doi, safe="/:;._-()"),
                                                       urllib.parse.quote(DEFAULT_MAILTO)))
            real = clean_ws(data.get("title") or "")
        except SystemExit:
            real = ""
        if not real:
            out.append((title, "missing", ""))
            print(u"  [X] %s  %s" % (T(lang, "verify_missing"), doi))
            continue
        score = overlap(title, real)
        if score >= 0.5:
            ok += 1
            out.append((title, "ok", real))
            print(u"  [OK] %s  %s" % (T(lang, "verify_ok"), doi))
        else:
            out.append((title, "title-differs", real))
            print(u"  [?] %s  %s -> %s" % (T(lang, "verify_title"), doi, real[:50]))
        time.sleep(0.2)
    print("\n" + T(lang, "verify_sum") % (ok, len(rows)))
    return 0 if ok == len(rows) and rows else 1


# ---------------------------------------------------------------- 正文

def fetch_pdf_text(record, pages, lang):
    url = record.get("pdf_url") or ""
    if not url:
        print("  " + T(lang, "pdf_skip"))
        return ""
    try:
        import fitz  # PyMuPDF，可选依赖
    except Exception:
        print("  " + T(lang, "pdf_skip"))
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        os.makedirs(".cache", exist_ok=True)
        tmp = os.path.join(".cache", "litsearch-%s.pdf" % re.sub(r"\W+", "", record.get("doi") or "x")[:24])
        with urllib.request.urlopen(req, timeout=40) as r, open(tmp, "wb") as f:
            f.write(r.read())
        doc = fitz.open(tmp)
        text = "\n".join(doc[i].get_text() for i in range(min(pages, len(doc))))
        doc.close()
        print("  " + T(lang, "pdf_ok") % pages)
        return text
    except Exception as e:
        print("  !! 正文抽取失败：%s" % e)
        return ""


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(add_help=True, description="检索文献：题目、摘要、被引、OA 链接")
    ap.add_argument("query", nargs="?", default="", help="话题或一句话")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--year-from", type=int, default=None)
    ap.add_argument("--year-to", type=int, default=None)
    ap.add_argument("--sort", choices=["relevance", "citations"], default="relevance",
                    help="relevance=按相关度再按被引重排（默认）；citations=直接按被引排")
    ap.add_argument("--types", default="journal-article,posted-content,report",
                    help="Crossref 类型过滤，逗号分隔；传空串表示不过滤")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--mailto", default=DEFAULT_MAILTO, help="Crossref/OpenAlex 要求的联系邮箱")
    ap.add_argument("--proxy", default=os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
                    or os.environ.get("ALL_PROXY") or "")
    ap.add_argument("--out-dir", default=os.path.join("output"))
    ap.add_argument("--from-file", default="", help="重放之前保存的 lit-search.json（离线、可复现）")
    ap.add_argument("--verify", default="", help="核验一个 csv 里的 DOI 与标题")
    ap.add_argument("--fetch-pdf", action="store_true", help="抽第一篇有 OA 链接的正文前几页")
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--no-enrich", action="store_true", help="不向 OpenAlex 补摘要与被引")
    ap.add_argument("--min-tier", choices=["A", "B", "C"], default="C",
                    help="只要 A 级刊 / A+B 级刊 / 全要（默认全要，C 级排在后面而不是删掉）")
    a = ap.parse_args()

    if a.verify:
        return verify(Fetcher(a.proxy, a.mailto), a.verify, a.lang)

    if a.from_file:
        data = json.load(io.open(a.from_file, encoding="utf-8"))
        records, query = data.get("records") or [], data.get("query") or ""
        print(u"重放 %s（%d 条，查询：%s）" % (a.from_file, len(records), query)
              if a.lang == "zh" else "Replayed %s (%d records, query: %s)"
              % (a.from_file, len(records), query))
        files = write_outputs(records, a.out_dir, query, a.lang,
                              [(datetime.now().strftime("%Y-%m-%d %H:%M"), "replay", query, a.from_file,
                                len(records), len(records))], a.mailto,
                              stamp=(data.get("generated") or "")[:16].replace("T", " "))
        print_table(records, a.lang)
        print("\n" + T(a.lang, "wrote"))
        for p in files:
            print("  " + p)
        return 0 if records else 1

    if not a.query.strip():
        ap.print_help()
        return 2

    fetcher = Fetcher(a.proxy, a.mailto)
    if re.search(u"[\u4e00-\u9fff]", a.query):
        print(u"提示：中文句子在 Crossref 里命中很多低门槛期刊，检索质量会差。" if a.lang == "zh"
              else "Note: Chinese sentences match many low-tier journals in Crossref; retrieval quality will be poor.")
        print(u"      更稳的做法是把话题翻成 3–5 个英文关键词再检索（经济学文献绝大多数以英文登记）。" if a.lang == "zh"
              else "      Better: translate the topic into 3-5 English keywords (most economics papers are indexed in English).")
    print(T(a.lang, "searching") % a.query)
    types = [t.strip() for t in (a.types or "").split(",") if t.strip()]
    rows = a.top if a.sort == "citations" else min(100, max(a.top * 6, a.top))
    total, records = search_crossref(fetcher, a.query, rows, a.year_from, a.year_to, a.mailto, types, a.sort)
    print(T(a.lang, "hits") % (total, len(records)))
    if not records:
        print(T(a.lang, "no_hits"))
        return 1

    if not a.no_enrich:
        records = enrich(fetcher, records, a.lang, a.mailto)

    records = dedupe(records)
    for r in records:
        r["tier"] = tier_of(r)
    if a.min_tier != "C":
        keep = {"A"} if a.min_tier == "A" else {"A", "B"}
        before = len(records)
        records = [r for r in records if r.get("tier") in keep]
        print(("按层级过滤：%d -> %d 条（只要 %s 级）" if a.lang == "zh"
               else "Tier filter: %d -> %d records (%s only)")
              % (before, len(records), a.min_tier if a.min_tier == "A" else "A+B"))
        if not records:
            print(("没有 %s 级的命中。去掉 --min-tier 看看这个话题是不是只有小刊在做。" if a.lang == "zh"
                   else "No hits at that tier. Drop --min-tier to see whether only smaller journals cover it.")
                  % a.min_tier)
            return 1
    if a.sort == "relevance":
        records = blend_rank(records, a.query)
    else:
        records = sorted(records, key=lambda r: -(r.get("cited_by") or 0))
    records = records[:a.top]

    if a.fetch_pdf:
        for r in records:
            if r.get("pdf_url"):
                text = fetch_pdf_text(r, a.pages, a.lang)
                if text:
                    p = os.path.join(a.out_dir, "lit-fulltext-%s.txt" % slugify(r.get("doi") or "x", 30))
                    os.makedirs(a.out_dir, exist_ok=True)
                    io.open(p, "w", encoding="utf-8", newline="\n").write(text)
                    print("  " + p)
                break

    params = "top=%d;year=%s-%s" % (a.top, a.year_from or "", a.year_to or "")
    files = write_outputs(records, a.out_dir, a.query, a.lang,
                          [(datetime.now().strftime("%Y-%m-%d %H:%M"), "crossref+openalex", a.query,
                            params, total, len(records))], a.mailto)
    print_table(records, a.lang)
    print("\n" + T(a.lang, "wrote"))
    for p in files:
        print("  " + p)
    print("\n" + T(a.lang, "log_note"))
    print(T(a.lang, "next"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
