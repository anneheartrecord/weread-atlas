#!/usr/bin/env python3
"""Write compact reading digests for the agent: <root>/.atlas/digest/digest-NN.md.

Each file covers about 15 books: title, author, category, hours, counts, up to
12 highlights picked by quality and spread across the book, and up to 10
thoughts with the highlight they were written on. The agent reads these to
propose domains and topics (topics.json); it should not need the full notes.

  --top N   the N books with the most highlights + thoughts (then hours); default config topN
  --new     books no topic in topics.json mentions yet, or with notes newer than topics.json
"""

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import atlas_lib as lib  # noqa: E402

PER_FILE = 15
MAX_HIGHLIGHTS = 12
MAX_THOUGHTS = 10
CLIP = 200
SENTENCE_END = "。！？”…!?.」』"


def _clip(text, n=CLIP):
    return text if len(text) <= n else text[:n] + "…"


def highlight_score(h):
    t = h["text"]
    s = 0
    if t[-1:] in SENTENCE_END:
        s += 2
    if 30 <= len(t) <= 120:
        s += 1
    if len(re.findall(r"\d", t)) >= 3:
        s -= 2
    if h.get("thought"):
        s += 2
    return s


def pick_highlights(book, k=MAX_HIGHLIGHTS):
    """Best-scoring highlight from each of k equal slices of the book, in book order."""
    cands = []
    for ci, ch in enumerate(book.get("chapters", [])):
        for h in ch.get("highlights", []):
            t = h.get("text") or ""
            if "[插图]" in t or len(t) < 10:
                continue
            cands.append((ci, h.get("pos") or 0, highlight_score(h), t, ch.get("title") or ""))
    if not cands:
        return []
    k = min(k, len(cands))
    size = len(cands) / float(k)
    out = []
    for i in range(k):
        bucket = cands[int(i * size):int((i + 1) * size)] or cands[-1:]
        best = max(bucket, key=lambda x: x[2])
        out.append((best[3], best[4]))
    return out


def all_thoughts(book):
    """(thought, quote) pairs in book order."""
    out = []
    for ch in book.get("chapters", []):
        for h in ch.get("highlights", []):
            for t in lib.thought_lines(h.get("thought")):
                out.append((t, h.get("text") or ""))
    for o in book.get("orphanThoughts", []):
        if o.get("text"):
            out.append((o["text"], o.get("quote") or ""))
    return out


def pick_thoughts(book, k=MAX_THOUGHTS):
    items = all_thoughts(book)
    if len(items) <= k:
        return items
    keep = sorted(range(len(items)), key=lambda i: (-min(len(items[i][0]), 120), i))[:k]
    return [items[i] for i in sorted(keep)]


def rank_key(b):
    return (-((b.get("marks") or 0) + (b.get("thoughts") or 0)), -(b.get("hours") or 0), b.get("fileName", ""))


def topic_references(topics):
    refs = set()
    for t in topics.get("topics") or []:
        refs.update(t.get("books") or [])
        for v in t.get("viewpoints") or []:
            refs.update(v.get("books") or [])
    refs.update((topics.get("assign") or {}).keys())
    return refs


def referenced_files(books, refs):
    """File names the references point at, resolved the way topics.py resolves them:
    an exact file name first, otherwise the first book with that full title. Two books
    sharing a title stay distinct, because each reference lands on exactly one file."""
    by_file = {b["fileName"] for b in books}
    by_title = {}
    for b in books:
        by_title.setdefault(b.get("title"), b["fileName"])
    out = set()
    for r in refs:
        r = lib.unwikilink(r) if isinstance(r, str) else r
        if r in by_file:
            out.add(r)
        elif r in by_title:
            out.add(by_title[r])
    return out


def select_new(books, paths):
    topics = lib.read_json(paths.topics_json)
    if topics is None:
        return list(books)
    mtime = os.path.getmtime(paths.topics_json)
    placed = referenced_files(books, topic_references(topics))
    return [b for b in books if b["fileName"] not in placed or (b.get("noteSort") or 0) > mtime]


def render_book(n, b):
    lines = ["## %d. %s" % (n, b.get("title") or b["fileName"]), ""]
    lines.append("- 文件名：%s" % b["fileName"])
    lines.append("- 作者：%s ｜ 分类：%s ｜ 时长：%s 小时（下限） ｜ 进度：%s%%"
                 % (b.get("author") or "未知", b.get("category") or "未知", b.get("hours") or 0, b.get("progress") or 0))
    lines.append("- 划线 %d 条 ｜ 想法 %d 条" % (b.get("marks") or 0, b.get("thoughts") or 0))
    hls = pick_highlights(b)
    if hls:
        lines += ["", "### 划线", ""]
        lines += ["- %s（%s）" % (_clip(t), _clip(ch, 40)) for t, ch in hls]
    ths = pick_thoughts(b)
    if ths:
        lines += ["", "### 想法", ""]
        for t, q in ths:
            lines.append("- 💭 " + _clip(t))
            if q:
                lines.append("  > " + _clip(q, 120))
    return "\n".join(lines)


def run(paths, top=None, new=False, log=print):
    books = lib.load_books(paths)
    cfg = lib.load_config(paths.root)
    if new:
        chosen = sorted(select_new(books, paths), key=rank_key)
        mode = "新书和有新笔记的书"
    else:
        n = top if top is not None else int(cfg.get("topN") or 50)
        ranked = sorted(books, key=rank_key)
        # 0 or less means every book with notes.
        chosen = ranked[:n] if n > 0 else ranked
        mode = "划线和想法最多的前 %d 本" % n if n > 0 else "全部有笔记的书"

    os.makedirs(paths.digest_dir, exist_ok=True)
    for old in glob.glob(os.path.join(paths.digest_dir, "digest-*.md")):
        os.remove(old)
    files = []
    chunks = [chosen[i:i + PER_FILE] for i in range(0, len(chosen), PER_FILE)]
    for i, chunk in enumerate(chunks, 1):
        start = (i - 1) * PER_FILE
        head = ("# 书目摘要 %d/%d：%s，第 %d–%d 本\n\n"
                "给 agent 读的摘要。写 topics.json 时，书名一律用「文件名」那一行。"
                "时长是下限：只统计进过每月阅读前 10 的月份。\n"
                % (i, len(chunks), mode, start + 1, start + len(chunk)))
        body = "\n\n".join(render_book(start + j + 1, b) for j, b in enumerate(chunk))
        path = os.path.join(paths.digest_dir, "digest-%02d.md" % i)
        with open(path, "w", encoding="utf-8") as f:
            f.write(head + "\n" + body + "\n")
        files.append((path, len(chunk)))
    log("摘要（%s）共 %d 本，%d 个文件：" % (mode, len(chosen), len(files)))
    for path, count in files:
        log("  %s  %d 本" % (path, count))
    if not files:
        log("  没有需要摘要的书。")
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成给 agent 读的书目摘要 .atlas/digest/digest-NN.md。")
    ap.add_argument("--root", required=True, help="Obsidian 库里的 微信读书 根目录")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--top", type=int, help="按划线加想法数排名取前 N 本，0 表示全部，默认用配置里的 topN")
    g.add_argument("--new", action="store_true", help="只摘要主题方案里还没提到的书，以及笔记比 topics.json 新的书")
    args = ap.parse_args(argv)
    try:
        run(lib.Paths(args.root), top=args.top, new=args.new)
    except (ValueError, json.JSONDecodeError) as e:
        print("读取失败：%s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
