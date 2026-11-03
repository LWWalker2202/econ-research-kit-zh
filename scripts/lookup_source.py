#!/usr/bin/env python3
"""Look up a data source in the Econ Datalab directory.

The directory itself lives at https://econ-data.github.io/ and holds one
summary per source, with access links and application papers. This script
exists so that a lookup can happen inside a research session instead of in a
browser tab.

Examples
--------
    python scripts/lookup_source.py CFPS
    python scripts/lookup_source.py --region 中国数据 --topic 环境数据
    python scripts/lookup_source.py --id 1.6.1
    python scripts/lookup_source.py --list-topics

The downloaded directory is cached for a week. Everything here is a lookup
aid: the numbered entries in data-dict/ remain the place where the details
that actually cost time are written down.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DATA_URL = "https://econ-data.github.io/data.json"
CACHE_TTL = 7 * 24 * 60 * 60
SITE = "https://econ-data.github.io/"

LABELS = {
    "en": {
        "topics": "topics",
        "regions": "regions",
        "summary": "summary",
        "links": "links",
        "access": "access",
        "refs": "application papers",
        "none": "No entry matched. Try --list-topics, or browse {site}",
        "hit": "{n} entry/entries matched.",
        "offline": "Could not download the directory and no cached copy exists.",
        "stale": "Showing the cached copy from {when}.",
        "refresh": "Refreshing the cached directory.",
    },
    "zh": {
        "topics": "话题",
        "regions": "地区",
        "summary": "概述",
        "links": "获取链接",
        "access": "使用条件",
        "refs": "应用文献",
        "none": "没有匹配的条目。可以试 --list-topics，或直接浏览 {site}",
        "hit": "命中 {n} 个条目。",
        "offline": "下载失败，且本地没有缓存。",
        "stale": "以下为 {when} 的缓存副本。",
        "refresh": "正在刷新缓存目录。",
    },
}


def cache_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
    folder = os.path.join(base, "econ-research-kit")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "econdata.json")


def load(refresh, labels):
    path = cache_path()
    fresh = os.path.exists(path) and (time.time() - os.path.getmtime(path) < CACHE_TTL)
    if refresh or not fresh:
        try:
            if refresh:
                print(labels["refresh"], file=sys.stderr)
            with urllib.request.urlopen(DATA_URL, timeout=30) as resp:
                payload = resp.read().decode("utf-8")
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(payload)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            if not os.path.exists(path):
                print("{} ({})".format(labels["offline"], exc), file=sys.stderr)
                print("Browse {} instead.".format(SITE), file=sys.stderr)
                return None
            when = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(path)))
            print(labels["stale"].format(when=when), file=sys.stderr)
    else:
        when = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(path)))
        if time.time() - os.path.getmtime(path) > CACHE_TTL // 2:
            print(labels["stale"].format(when=when), file=sys.stderr)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def matches(entry, words, region, topic):
    if region and region not in entry.get("regions", []):
        return False
    if topic and topic not in entry.get("topics", []):
        return False
    if not words:
        return True
    blob = " ".join(
        [entry.get("id", ""), entry.get("title", ""), entry.get("summary", "")]
        + entry.get("topics", [])
        + entry.get("regions", [])
    ).lower()
    return all(w.lower() in blob for w in words)


def sort_key(entry):
    try:
        return [int(p) for p in str(entry.get("id", "")).split(".")]
    except ValueError:
        return [10 ** 6]


def render(entry, labels):
    out = []
    out.append("{}  {}".format(entry.get("id", "?"), entry.get("title", "")))
    if entry.get("topics"):
        out.append("  {}: {}".format(labels["topics"], "、".join(entry["topics"])))
    if entry.get("regions"):
        out.append("  {}: {}".format(labels["regions"], "、".join(entry["regions"])))
    if entry.get("summary"):
        out.append("  {}: {}".format(labels["summary"], entry["summary"]))
    links = entry.get("links") or []
    if links:
        out.append("  {}:".format(labels["links"]))
        for link in links:
            out.append("    - {} {}".format(link.get("label", ""), link.get("url", "")))
    if entry.get("source"):
        out.append("  {}: {}".format(labels["access"], entry["source"]))
    refs = entry.get("references") or []
    if refs:
        out.append("  {} ({}):".format(labels["refs"], len(refs)))
        for ref in refs[:3]:
            out.append("    - {} ({}) {}".format(ref.get("title", ""), ref.get("year", ""), ref.get("journal", "")))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Look up a source in the Econ Datalab directory.")
    ap.add_argument("words", nargs="*", help="keywords matched against id, title, summary, topics, regions")
    ap.add_argument("--region", help="exact region label, e.g. 中国数据")
    ap.add_argument("--topic", help="exact topic label, e.g. 环境数据")
    ap.add_argument("--id", help="exact id, e.g. 1.6.1")
    ap.add_argument("--limit", type=int, default=8, help="maximum entries to print (default 8)")
    ap.add_argument("--json", action="store_true", help="print raw JSON instead of a summary")
    ap.add_argument("--refresh", action="store_true", help="re-download the directory")
    ap.add_argument("--list-topics", action="store_true", help="print every topic label with its count")
    ap.add_argument("--list-regions", action="store_true", help="print every region label with its count")
    ap.add_argument("--lang", choices=["en", "zh"], default="en", help="output language for labels")
    args = ap.parse_args()
    labels = LABELS[args.lang]

    data = load(args.refresh, labels)
    if data is None:
        return 1

    if args.list_topics or args.list_regions:
        key = "topics" if args.list_topics else "regions"
        counts = {}
        for entry in data:
            for value in entry.get(key, []):
                counts[value] = counts.get(value, 0) + 1
        for value, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            print("{}\t{}".format(count, value))
        return 0

    if args.id:
        hits = [d for d in data if str(d.get("id", "")) == args.id]
    else:
        hits = [d for d in data if matches(d, args.words, args.region, args.topic)]
    hits.sort(key=sort_key)

    if not hits:
        print(labels["none"].format(site=SITE))
        return 1

    if args.json:
        print(json.dumps(hits[: args.limit], ensure_ascii=False, indent=2))
        return 0

    print(labels["hit"].format(n=len(hits)))
    for entry in hits[: args.limit]:
        print()
        print(render(entry, labels))
    if len(hits) > args.limit:
        print()
        print("... {} more. Raise --limit or narrow the query.".format(len(hits) - args.limit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
