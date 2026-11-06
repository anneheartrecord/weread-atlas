#!/usr/bin/env python3
"""Validate .atlas/topics.json, then write topic cards, book note topics and 总览.md.

topics.json is written by the agent (format in references/vault-format.md).
Validation lists every problem and writes nothing when there is any.

Writes:
  主题/<name>.md     one card per topic; my thoughts and representative highlights
                     are picked by bigram overlap with the topic's own text; related
                     topics are undirected, so a relation shows on both cards
  书/<file>.md       领域 / 主题 frontmatter and the topic line at the top of the block
  总览.md            reading summary plus every domain with its topics
"""

import argparse
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import atlas_lib as lib  # noqa: E402
from digest import all_thoughts, highlight_score  # noqa: E402
from notes import write_book_note  # noqa: E402

MAX_ONELINER = 40
MAX_WHY = 26
MIN_VIEWPOINTS, MAX_VIEWPOINTS = 2, 8
MAX_THOUGHTS, THOUGHTS_PER_BOOK, THOUGHT_FLOOR = 3, 1, 0.3
MAX_HIGHLIGHTS, HIGHLIGHTS_PER_BOOK = 10, 2

# common two-character words that say nothing about a topic
STOP_BIGRAMS = {"我们", "一个", "自己", "他们", "没有", "什么", "这个", "就是", "因为", "所以", "如果",
                "可以", "不是", "但是", "时候", "已经", "这些", "那些", "这样", "那么", "还是", "只是"}


# ---------------------------------------------------------------- validation

def _is_text(v):
    return isinstance(v, str) and v.strip() != ""


def resolver(books):
    by_file = {b["fileName"]: b for b in books}
    by_title = {}
    for b in books:
        by_title.setdefault(b.get("title"), b)

    def resolve(name):
        if not isinstance(name, str):
            return None
        name = lib.unwikilink(name)
        return by_file.get(name) or by_title.get(name)
    return resolve


def _suggest(name, books):
    hits = difflib.get_close_matches(str(name), [b["fileName"] for b in books], n=1, cutoff=0.5)
    return "，是不是「%s」？" % hits[0] if hits else ""


def validate(data, books):
    """Returns (errors, warnings)."""
    errors, warnings = [], []
    if not isinstance(data, dict):
        return ["topics.json 顶层必须是对象"], warnings
    resolve = resolver(books)

    domains = data.get("domains")
    if not isinstance(domains, list) or not domains or not all(_is_text(d) for d in domains):
        errors.append("domains 必须是非空的字符串列表")
        domains = [d for d in domains or [] if _is_text(d)] if isinstance(domains, list) else []
    for d in sorted({d for d in domains if domains.count(d) > 1}):
        errors.append("领域重名：%s" % d)

    topics = data.get("topics")
    if not isinstance(topics, list) or not topics:
        errors.append("topics 必须是非空列表")
        topics = []
    names = {t.get("name") for t in topics if isinstance(t, dict) and _is_text(t.get("name"))}
    seen = {}
    for i, t in enumerate(topics, 1):
        if not isinstance(t, dict):
            errors.append("第 %d 个主题不是对象" % i)
            continue
        name = t.get("name")
        label = "主题「%s」" % name if _is_text(name) else "第 %d 个主题" % i
        if not _is_text(name):
            errors.append("%s缺少 name" % label)
        else:
            if lib.sanitize_filename(name) != name:
                errors.append("%s的名字含有文件名不能用的字符（%s）或首尾空格、点号" % (label, " ".join(lib.FORBIDDEN_CHARS)))
            key = name.casefold()
            if key in seen:
                errors.append("主题重名：%s" % name)
            seen[key] = True
        if t.get("domain") not in domains:
            errors.append("%s的领域「%s」不在 domains 里" % (label, t.get("domain")))
        one = t.get("oneLiner")
        if not _is_text(one):
            errors.append("%s缺少 oneLiner" % label)
        elif len(one.strip()) > MAX_ONELINER:
            errors.append("%s的 oneLiner 有 %d 个字，超过 %d 个字" % (label, len(one.strip()), MAX_ONELINER))
        tb = t.get("books")
        if not isinstance(tb, list) or not tb:
            errors.append("%s的 books 必须是非空列表" % label)
        else:
            for b in tb:
                if resolve(b) is None:
                    errors.append("%s的书名找不到：%s%s" % (label, b, _suggest(b, books)))
        vps = t.get("viewpoints")
        if not isinstance(vps, list):
            errors.append("%s缺少 viewpoints" % label)
        else:
            if not MIN_VIEWPOINTS <= len(vps) <= MAX_VIEWPOINTS:
                errors.append("%s有 %d 条观点，应在 %d 到 %d 条之间" % (label, len(vps), MIN_VIEWPOINTS, MAX_VIEWPOINTS))
            for j, v in enumerate(vps, 1):
                if not isinstance(v, dict) or not _is_text(v.get("claim")):
                    errors.append("%s的第 %d 条观点缺少 claim" % (label, j))
                    continue
                vb = v.get("books", [])
                if not isinstance(vb, list):
                    errors.append("%s的第 %d 条观点 books 必须是列表" % (label, j))
                    continue
                for b in vb:
                    if resolve(b) is None:
                        warnings.append("%s的观点来源不在书架上，会写成《%s》%s" % (label, b, _suggest(b, books)))
        _check_related(t, label, names, errors, warnings)

    assign = data.get("assign", {})
    if not isinstance(assign, dict):
        errors.append("assign 必须是对象")
    else:
        for b, d in assign.items():
            if resolve(b) is None:
                errors.append("assign 里的书名找不到：%s%s" % (b, _suggest(b, books)))
            if d not in domains:
                errors.append("assign 里「%s」的领域「%s」不在 domains 里" % (b, d))
    return errors, warnings


def _check_related(t, label, names, errors, warnings):
    rel = t.get("related")
    if rel is None:
        warnings.append("%s没有 related，书房页上它不会和其他主题连线" % label)
        return
    if not isinstance(rel, list):
        errors.append("%s的 related 必须是列表" % label)
        return
    for j, r in enumerate(rel, 1):
        if not isinstance(r, dict):
            errors.append("%s的第 %d 条 related 不是对象" % (label, j))
            continue
        other, why = r.get("topic"), r.get("why")
        if not _is_text(other):
            errors.append("%s的第 %d 条 related 缺少 topic" % (label, j))
        elif other == t.get("name"):
            errors.append("%s的 related 指向了自己" % label)
        elif other not in names:
            hits = difflib.get_close_matches(other, sorted(names), n=1, cutoff=0.5)
            errors.append("%s的 related 主题找不到：%s%s" % (label, other, "，是不是「%s」？" % hits[0] if hits else ""))
        if not _is_text(why):
            errors.append("%s的第 %d 条 related 缺少 why" % (label, j))
        elif len(why.strip()) > MAX_WHY:
            errors.append("%s和「%s」的 why 有 %d 个字，超过 %d 个字" % (label, other, len(why.strip()), MAX_WHY))


def relations(topics, log=None):
    """Undirected relations from every topic's `related`, de-duplicated.

    Returns {name: [(other, why), ...]} so each card lists every relation it
    takes part in: the ones it declares, in order, then the ones declared on it.
    When both sides declare the pair, the first declaration's why wins.
    """
    pairs = {}
    order = []
    for t in topics:
        for r in t.get("related") or []:
            a, b, why = t["name"], r["topic"], r["why"].strip()
            key = tuple(sorted((a, b)))
            if key in pairs:
                if pairs[key][2] != why and log:
                    log("提醒：主题「%s」和「%s」两边都写了 related，用先写的理由：%s" % (key[0], key[1], pairs[key][2]))
                continue
            pairs[key] = (a, b, why)
            order.append(key)
    out = {t["name"]: [] for t in topics}
    for key in order:
        a, b, why = pairs[key]
        out[a].append((b, why))
    for key in order:
        a, b, why = pairs[key]
        out[b].append((a, why))
    return out


# ---------------------------------------------------------------- relevance picking

def bigrams(text):
    t = re.sub(r"[^一-鿿A-Za-z]", "", text or "")
    return {t[k:k + 2] for k in range(len(t) - 1)} - STOP_BIGRAMS


def relevance(ref, text):
    g = bigrams(text)
    return len(g & ref) / (1 + len(g)) ** 0.5


def _pick(cands, limit, per_book):
    """cands: (score, order, book fileName, item). Highest score first, capped per book."""
    out, used = [], {}
    for c in sorted(cands, key=lambda c: (-c[0], c[1])):
        if len(out) >= limit:
            break
        if used.get(c[2], 0) >= per_book:
            continue
        used[c[2]] = used.get(c[2], 0) + 1
        out.append(c)
    return out


def pick_for_topic(topic, topic_books, exclude):
    ref = bigrams(topic["name"] + topic.get("oneLiner", "")
                  + "".join(v.get("claim", "") + v.get("text", "") for v in topic.get("viewpoints", [])))
    th, hl, order = [], [], 0
    for b in topic_books:
        for text, quote in all_thoughts(b):
            order += 1
            if len(text) < 6 or lib.excluded(text, exclude) or lib.excluded(quote, exclude):
                continue
            s = relevance(ref, text + quote)
            if s > THOUGHT_FLOOR:
                th.append((s, order, b["fileName"], (text, quote)))
        for ch in b.get("chapters", []):
            for h in ch.get("highlights", []):
                order += 1
                t = h.get("text") or ""
                if "[插图]" in t or not 15 <= len(t) <= 200 or lib.excluded(t, exclude):
                    continue
                s = relevance(ref, t)
                if s > 0:
                    hl.append((s + highlight_score(h) * 0.01, order, b["fileName"], t))
    return _pick(th, MAX_THOUGHTS, THOUGHTS_PER_BOOK), _pick(hl, MAX_HIGHLIGHTS, HIGHLIGHTS_PER_BOOK)


# ---------------------------------------------------------------- rendering

def source_links(names, resolve):
    out = []
    for n in names or []:
        b = resolve(n)
        out.append(lib.wikilink(b["fileName"]) if b else "《%s》" % lib.unwikilink(n))
    return " · ".join(out)


def render_card(topic, thoughts, highlights, resolve, related=()):
    parts = ["## 一句话结论\n\n" + lib.md_text(topic["oneLiner"])]
    lines = ["## 核心观点", ""]
    for i, v in enumerate(topic["viewpoints"], 1):
        line = "%d. **%s**" % (i, lib.md_text(v["claim"]))
        if lib.one_line(v.get("text")):
            line += "：" + lib.md_text(v.get("text"))
        src = source_links(v.get("books"), resolve)
        if src:
            line += " —— " + src
        lines.append(line)
    parts.append("\n".join(lines))
    lines = ["## 我的想法", ""]
    for _, _, fname, (text, quote) in thoughts:
        lines.append("- %s —— %s" % (lib.md_text(text), lib.wikilink(fname)))
        if quote:
            lines.append("  > " + lib.md_text(quote))
    parts.append("\n".join(lines).rstrip())
    lines = ["## 代表划线", ""]
    for _, _, fname, text in highlights:
        lines.append("- %s —— %s" % (lib.md_text(text), lib.wikilink(fname)))
    parts.append("\n".join(lines).rstrip())
    if related:
        lines = ["## 相关主题", ""]
        for other, why in related:
            lines.append("- %s：%s" % (lib.wikilink(other), lib.md_text(why)))
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def render_overview(stats, books, domains, topics, topic_books, book_domains):
    parts = []
    if stats:
        parts.append("自 %s 起累计阅读 %s 小时、%s 天，读过 %s 本，读完 %s 本，笔记 %s 条。"
                     % (stats.get("since") or "注册", stats.get("totalHours", 0), stats.get("readDays", 0),
                        stats.get("readBooks", 0), stats.get("finishedBooks", 0), stats.get("notes", 0)))
    placed = sum(1 for b in books if book_domains.get(b["fileName"]))
    in_topics = len({b["fileName"] for bs in topic_books.values() for b in bs})
    parts.append("书脉收录有笔记的书 %d 本，%d 本归入主题，%d 本已分到领域。"
                 % (len(books), in_topics, placed))
    for d in domains:
        dbooks = [b for b in books if d in book_domains.get(b["fileName"], [])]
        hours = round(sum(b.get("hours") or 0 for b in dbooks), 1)
        lines = ["## " + d, "", "%d 本书，%s 小时。" % (len(dbooks), hours)]
        dtopics = [t for t in topics if t["domain"] == d]
        if dtopics:
            lines.append("")
            for t in dtopics:
                lines.append("- %s · %d 本" % (lib.wikilink(t["name"]), len(topic_books[t["name"]])))
        parts.append("\n".join(lines))
    rest = [b for b in books if not book_domains.get(b["fileName"])]
    if rest:
        parts.append("## 未归类\n\n%d 本书。" % len(rest))
    return "\n\n".join(parts)


# ---------------------------------------------------------------- main flow

def run(paths, check_only=False, log=print):
    books = lib.load_books(paths)
    data = lib.read_json(paths.topics_json)
    if data is None:
        log("找不到 %s" % paths.topics_json)
        return 1
    errors, warnings = validate(data, books)
    for w in warnings:
        log("提醒：" + w)
    if errors:
        log("topics.json 有 %d 个问题，没有写入任何文件：" % len(errors))
        for i, e in enumerate(errors, 1):
            log("  %d. %s" % (i, e))
        return 1
    if check_only:
        log("topics.json 校验通过：%d 个领域，%d 个主题。" % (len(data["domains"]), len(data["topics"])))
        return 0

    cfg = lib.load_config(paths.root)
    resolve = resolver(books)
    domains, topics = data["domains"], data["topics"]
    assign = data.get("assign") or {}

    topic_books = {}
    book_topics, book_domains = {}, {}
    for t in topics:
        tb = []
        for n in t["books"]:
            b = resolve(n)
            if b["fileName"] not in {x["fileName"] for x in tb}:
                tb.append(b)
        tb.sort(key=lambda b: -(b.get("hours") or 0))
        topic_books[t["name"]] = tb
        for b in tb:
            book_topics.setdefault(b["fileName"], []).append(t["name"])
            book_domains.setdefault(b["fileName"], set()).add(t["domain"])
    for n, d in assign.items():
        f = resolve(n)["fileName"]
        if f not in book_domains:
            book_domains[f] = {d}
    book_domains = {f: [d for d in domains if d in ds] for f, ds in book_domains.items()}

    related = relations(topics, log=log)
    cards = {"created": 0, "updated": 0, "unchanged": 0}
    for t in topics:
        tb = topic_books[t["name"]]
        thoughts, highlights = pick_for_topic(t, tb, cfg.get("exclude") or [])
        fields = {
            "主题": t["name"],
            "领域": t["domain"],
            "书目": [lib.wikilink(b["fileName"]) for b in tb],
            "时长": float(round(sum(b.get("hours") or 0 for b in tb), 1)),
        }
        path = paths.topic_card(t["name"])
        existing = lib.read_text(path)
        text = lib.merge_note(existing, render_card(t, thoughts, highlights, resolve, related[t["name"]]), fields)
        changed = lib.write_text_if_changed(path, text)
        cards["created" if existing is None else ("updated" if changed else "unchanged")] += 1

    notes = {"created": 0, "updated": 0, "unchanged": 0}
    for b in books:
        f = b["fileName"]
        notes[write_book_note(paths, b, topics=book_topics.get(f, []), domains=book_domains.get(f, []))] += 1

    stats = lib.read_json(paths.stats_json)
    overview = render_overview(stats, books, domains, topics, topic_books, book_domains)
    lib.write_text_if_changed(paths.overview, lib.merge_note(lib.read_text(paths.overview), overview, {}))

    log("主题卡片 %d 张：新建 %d，更新 %d，未变化 %d；主题之间的关系 %d 条"
        % (len(topics), cards["created"], cards["updated"], cards["unchanged"], sum(len(v) for v in related.values()) // 2))
    log("书的笔记 %d 篇：新建 %d，更新 %d，未变化 %d；归入主题 %d 本，分到领域 %d 本"
        % (len(books), notes["created"], notes["updated"], notes["unchanged"], len(book_topics),
           sum(1 for v in book_domains.values() if v)))
    log("总览已写入 %s" % paths.overview)
    names = {t["name"] + ".md" for t in topics}
    if os.path.isdir(paths.topics_dir):
        stale = sorted(f[:-3] for f in os.listdir(paths.topics_dir) if f.endswith(".md") and f not in names
                       and lib.read_block(lib.read_text(os.path.join(paths.topics_dir, f))) is not None)
        if stale:
            log("这些主题卡片已不在 topics.json 里，没有删除，需要的话手动处理：" + "、".join(stale))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="校验 .atlas/topics.json，写入主题卡片、书的领域和主题、总览。")
    ap.add_argument("--root", required=True, help="Obsidian 库里的 微信读书 根目录")
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    args = ap.parse_args(argv)
    try:
        return run(lib.Paths(args.root), check_only=args.check)
    except ValueError as e:
        print("topics.json 不是合法的 JSON：%s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
