#!/usr/bin/env python3
"""Write or update one note per book: <root>/书/<fileName>.md, from .atlas/books.json.

Only the frontmatter fields listed in references/vault-format.md and the text
between the weread-atlas markers are touched. 领域 / 主题 belong to topics.py:
this script keeps whatever it finds there and keeps the topic line in the block.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import atlas_lib as lib  # noqa: E402

# managed by notes.py, in the order new notes get them
FIELDS = ["书名", "作者", "bookId", "分类", "进度", "读完", "最近阅读", "时长", "划线数", "想法数", "封面", "链接"]


def book_fields(book):
    values = {
        "书名": book.get("title") or "",
        "作者": book.get("author") or None,
        "bookId": str(book["bookId"]),
        "分类": book.get("category") or None,
        "进度": int(book.get("progress") or 0),
        "读完": book.get("finished"),
        "最近阅读": book.get("readAt"),
        "时长": float(round(book.get("hours") or 0, 1)),
        "划线数": int(book.get("marks") or 0),
        "想法数": int(book.get("thoughts") or 0),
        "封面": book.get("cover") or None,
        "链接": book.get("link") or None,
    }
    sets = {k: values[k] for k in FIELDS if values[k] is not None}
    removes = [k for k in FIELDS if values[k] is None]
    return sets, removes


def topics_from_frontmatter(fm):
    value = fm.get("主题")
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    return [lib.unwikilink(v) for v in value if v]


def write_book_note(paths, book, topics=None, domains=None, guard=None):
    """Write one book note. Returns 'created', 'updated' or 'unchanged'.

    topics / domains None: keep what the note already has (notes.py).
    A list (possibly empty): set or clear 主题 / 领域 (topics.py).
    """
    path = paths.book_note(book["fileName"])
    existing = lib.read_text(path)
    sets, removes = book_fields(book)
    if topics is None:
        topics = topics_from_frontmatter(lib.read_frontmatter(existing))
    else:
        if domains:
            sets["领域"] = list(domains)
        else:
            removes.append("领域")
        if topics:
            sets["主题"] = [lib.wikilink(t) for t in topics]
        else:
            removes.append("主题")
    block = lib.render_book_block(book, topics)
    text = lib.merge_note(existing, block, sets, removes)
    write = guard.write if guard else (lambda p, _old, t: lib.write_text_if_changed(p, t))
    changed = write(path, existing, text)
    if existing is None:
        return "created"
    return "updated" if changed else "unchanged"


def run(paths, log=print):
    books = lib.load_books(paths)
    counts = {"created": 0, "updated": 0, "unchanged": 0}
    guard = lib.BlockGuard(paths)
    for b in books:
        counts[write_book_note(paths, b, guard=guard)] += 1
    guard.save(log)
    log("书的笔记 %d 篇：新建 %d，更新 %d，未变化 %d（目录 %s）"
        % (len(books), counts["created"], counts["updated"], counts["unchanged"], paths.books_dir))
    known = {b["fileName"] + ".md" for b in books}
    if os.path.isdir(paths.books_dir):
        stray = sorted(f for f in os.listdir(paths.books_dir)
                       if f.endswith(".md") and f not in known and lib.read_block(lib.read_text(os.path.join(paths.books_dir, f))) is not None)
        if stray:
            log("这些笔记带生成区块，但书已不在 books.json 里，没有改动：" + "、".join(stray[:10])
                + ("……" if len(stray) > 10 else ""))
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(description="根据 .atlas/books.json 写入或更新 书/<书名>.md，不覆盖用户内容。")
    ap.add_argument("--root", required=True, help="Obsidian 库里的 微信读书 根目录")
    args = ap.parse_args(argv)
    run(lib.Paths(args.root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
