#!/usr/bin/env python3
"""Fetch WeRead notes and reading stats into <root>/.atlas/.

Writes:
  .atlas/cache/<bookId>.json        raw responses per book
  .atlas/cache/notebooks.json       the notebook list
  .atlas/cache/readdata/*.json      monthly / annual / overall reading stats
  .atlas/books.json                 normalised books (see references/vault-format.md)
  .atlas/stats.json                 reading statistics

Incremental: a book is refetched only when its notebook `sort` (last note
time) changed or it has no cache yet; --full refetches everything. Past months
of reading stats never change, so only the current and previous month (and the
current year) are refetched.

Only books that have notes are covered: /user/notebooks does not list the rest
of the shelf.
"""

import argparse
import datetime
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import atlas_lib as lib  # noqa: E402
from weread_client import UpgradeRequired, WereadError, make_client  # noqa: E402

REVIEW_PAGE = 100
MAX_REVIEW_PAGES = 100


PROGRESS_EVERY = 25  # books per progress line and per save of .atlas/fetch.json

def _date(ts):
    if not ts:
        return None
    try:
        return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except (ValueError, OSError, OverflowError):
        return None


def _hours(seconds, digits=1):
    return round((seconds or 0) / 3600.0, digits)


def _count(text):
    """'344本' -> 344, '1.5万条' -> 15000."""
    if text is None:
        return 0
    if isinstance(text, (int, float)):
        return int(text)
    m = re.search(r"([\d.]+)\s*(万|千)?", str(text))
    if not m:
        return 0
    n = float(m.group(1))
    if m.group(2) == "万":
        n *= 10000
    elif m.group(2) == "千":
        n *= 1000
    return int(round(n))


def _norm(text):
    return re.sub(r"\s+", "", text or "")


def _range_start(r):
    try:
        return int(str(r).split("-")[0])
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------- fetching

def fetch_notebooks(client):
    books, last, seen = [], None, set()
    while True:
        params = {"count": 100}
        if last is not None:
            params["lastSort"] = last
        r = client.call("/user/notebooks", **params)
        page = r.get("books") or []
        new = [b for b in page if b.get("bookId") not in seen]
        for b in new:
            seen.add(b.get("bookId"))
        books.extend(new)
        if not r.get("hasMore") or not page or not new:
            return books, r.get("totalBookCount")
        last = page[-1].get("sort")


def fetch_reviews(client, book_id):
    reviews, synckey = [], 0
    for _ in range(MAX_REVIEW_PAGES):
        params = {"bookid": book_id, "count": REVIEW_PAGE}
        if synckey:
            params["synckey"] = synckey
        r = client.call("/review/list/mine", **params)
        reviews.extend(r.get("reviews") or [])
        nxt = r.get("synckey")
        if not r.get("hasMore") or not nxt or nxt == synckey or not r.get("reviews"):
            break
        synckey = nxt
    return reviews


def fetch_book(client, nb):
    bid = nb["bookId"]
    return {
        "notebook": nb,
        "info": client.call("/book/info", bookId=bid),
        "progress": client.call("/book/getprogress", bookId=bid),
        "bookmarks": client.call("/book/bookmarklist", bookId=bid),
        "reviews": fetch_reviews(client, bid),
    }


def fetch_shelf_state(client, log):
    """bookId -> (readUpdateTime, finishReading) from /shelf/sync; {} if it fails."""
    try:
        r = client.call("/shelf/sync")
    except UpgradeRequired:
        raise
    except WereadError as e:
        log("书架同步失败，本次不刷新阅读进度：%s" % e)
        return {}
    return {str(b.get("bookId")): (b.get("readUpdateTime") or 0, 1 if b.get("finishReading") else 0)
            for b in r.get("books") or [] if b.get("bookId")}


def progress_stale(cached, shelf_entry):
    """True when the shelf says the book was read or finished after the cached progress.

    The shelf values seen at the last refresh are kept in the cache, so a book whose
    shelf time and progress time never agree is not refetched on every run.
    """
    read_time, finish = shelf_entry
    book = (cached.get("progress") or {}).get("book") or {}
    seen_time = max(book.get("updateTime") or 0, cached.get("shelfReadUpdateTime") or 0)
    seen_finish = cached.get("shelfFinish")
    if seen_finish is None:
        seen_finish = 1 if int(book.get("progress") or 0) >= 100 else 0
    return read_time > seen_time or finish != seen_finish


def _month_iter(start, end):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def fetch_readdata(client, paths, today, log):
    """Returns (overall, {YYYY-MM: monthly}, {YYYY: annual}, months_fetched)."""
    os.makedirs(paths.readdata_cache, exist_ok=True)
    overall = client.call("/readdata/detail", mode="overall", baseTime=0)
    lib.write_json(os.path.join(paths.readdata_cache, "overall.json"), overall)
    regist = overall.get("registTime")
    if regist:
        start = datetime.datetime.fromtimestamp(int(regist)).date()
    else:
        start = (today.replace(day=1) - datetime.timedelta(days=730)).replace(day=1)
        log("接口没有返回注册时间，阅读统计只取最近两年。")
    prev = (today.replace(day=1) - datetime.timedelta(days=1))
    fresh = {(today.year, today.month), (prev.year, prev.month)}

    months, fetched = {}, 0
    for y, m in _month_iter(start, today):
        key = "%04d-%02d" % (y, m)
        path = os.path.join(paths.readdata_cache, "monthly-%s.json" % key)
        data = lib.read_json(path)
        if data is None or (y, m) in fresh:
            base = int(time.mktime(datetime.datetime(y, m, 15, 12).timetuple()))
            data = client.call("/readdata/detail", mode="monthly", baseTime=base)
            lib.write_json(path, data)
            fetched += 1
        months[key] = data

    years = {}
    for y in range(start.year, today.year + 1):
        path = os.path.join(paths.readdata_cache, "annually-%04d.json" % y)
        data = lib.read_json(path)
        if data is None or y >= prev.year:
            base = int(time.mktime(datetime.datetime(y, 6, 15, 12).timetuple()))
            data = client.call("/readdata/detail", mode="annually", baseTime=base)
            lib.write_json(path, data)
        years[y] = data
    return overall, months, years, fetched


# ---------------------------------------------------------------- normalising

def normalise_book(raw, hours_sec):
    nb = raw.get("notebook") or {}
    nbook = nb.get("book") or {}
    info = raw.get("info") or {}
    prog = (raw.get("progress") or {}).get("book") or {}
    bm = raw.get("bookmarks") or {}

    category = info.get("category") or ""
    if not category:
        cats = nbook.get("categories") or []
        category = (cats[0].get("title") if cats else "") or ""
    category = category.split("-")[0].strip()

    chapter_meta = {}
    for c in bm.get("chapters") or []:
        chapter_meta[c.get("chapterUid")] = (c.get("chapterIdx", 0), c.get("title") or "")

    # highlights grouped by chapter
    groups = {}
    for u in bm.get("updated") or []:
        text = lib.one_line(u.get("markText"))
        if not text:
            continue
        uid = u.get("chapterUid")
        if uid not in chapter_meta:
            uid = None
        h = {"text": text, "thought": None, "pos": _range_start(u.get("range")),
             "_t": u.get("createTime") or 0, "_uid": u.get("chapterUid"), "_range": u.get("range")}
        groups.setdefault(uid, []).append(h)

    by_text, by_range = {}, {}
    for hls in groups.values():
        hls.sort(key=lambda h: (h["pos"], h["_t"]))
        for h in hls:
            by_text.setdefault(_norm(h["text"]), h)
            by_range.setdefault((h["_uid"], h["_range"]), h)

    orphans, thought_count = [], 0
    reviews = [e.get("review", e) for e in raw.get("reviews") or []]
    reviews.sort(key=lambda r: r.get("createTime") or 0)
    for r in reviews:
        text = lib.one_line(r.get("content"))
        if not text:
            continue
        thought_count += 1
        abstract = lib.one_line(r.get("abstract"))
        target = None
        if abstract:
            target = by_text.get(_norm(abstract)) or by_range.get((r.get("chapterUid"), r.get("range")))
        if target is not None:
            target["thought"] = text if not target["thought"] else target["thought"] + "\n" + text
        else:
            orphans.append({"text": text, "quote": abstract or None})

    ordered = sorted((uid for uid in groups if uid is not None), key=lambda uid: chapter_meta[uid][0])
    if None in groups:
        ordered.append(None)
    chapters = []
    for uid in ordered:
        title = lib.one_line(chapter_meta[uid][1]) if uid is not None else lib.UNKNOWN_CHAPTER
        chapters.append({
            "title": title or lib.UNKNOWN_CHAPTER,
            "highlights": [{"text": h["text"], "thought": h["thought"], "pos": h["pos"]} for h in groups[uid]],
        })

    progress = prog.get("progress")
    if progress is None:
        progress = nb.get("readingProgress") or 0
    finished = _date(prog.get("finishTime")) if int(progress or 0) >= 100 else None
    rating = info.get("newRating")

    return {
        "bookId": str(nb.get("bookId") or info.get("bookId")),
        "title": lib.display_title(info.get("title") or nbook.get("title") or ""),
        "fileName": None,
        "author": info.get("author") or nbook.get("author") or "",
        "category": category,
        "cover": info.get("cover") or nbook.get("cover") or "",
        "link": info.get("readerLink") or nbook.get("readerLink") or info.get("deepLink") or nbook.get("deepLink") or None,
        "rating": round(rating / 10.0, 1) if rating else None,
        "progress": int(progress or 0),
        "finished": finished,
        "readAt": _date(prog.get("updateTime")),
        "hours": _hours(hours_sec),
        "noteSort": nb.get("sort") or 0,
        "chapters": chapters,
        "orphanThoughts": orphans,
        "marks": sum(len(c["highlights"]) for c in chapters),
        "thoughts": thought_count,
    }


def per_book_seconds(months):
    total = {}
    for data in months.values():
        for e in data.get("readLongest") or []:
            bid = (e.get("book") or {}).get("bookId")
            if bid:
                total[str(bid)] = total.get(str(bid), 0) + (e.get("readTime") or 0)
    return total


def build_stats(overall, months, years, today):
    stat = {s.get("stat"): s.get("counts") for s in overall.get("readStat") or []}
    pt = overall.get("preferTime") or []
    hourly = [{"hour": h, "hours": 0.0} for h in range(24)]
    for i, sec in enumerate(pt[:24]):
        hourly[(6 + i) % 24]["hours"] = _hours(sec)
    cats = [{"name": c.get("categoryTitle"), "hours": _hours(c.get("readingTime")), "count": c.get("readingCount") or 0}
            for c in overall.get("preferCategory") or [] if (c.get("readingTime") or 0) > 0][:8]
    year_rows = []
    for y in sorted(years):
        d = years[y] or {}
        ys = {s.get("stat"): s.get("counts") for s in d.get("readStat") or []}
        year_rows.append({"year": y, "hours": _hours(d.get("totalReadTime")), "days": d.get("readDays") or 0,
                          "finished": _count(ys.get("读完"))})
    return {
        "generatedAt": today.strftime("%Y-%m-%d"),
        "since": _date(overall.get("registTime")),
        "totalHours": int((overall.get("totalReadTime") or 0) / 3600.0 + 0.5),
        "readDays": overall.get("readDays") or 0,
        "readBooks": _count(stat.get("读过")),
        "finishedBooks": _count(stat.get("读完")),
        "notes": _count(stat.get("笔记")),
        "years": year_rows,
        "months": [{"month": k, "hours": _hours(v.get("totalReadTime"))} for k, v in sorted(months.items())],
        "hourly": hourly,
        "categories": cats,
    }


# ---------------------------------------------------------------- main flow

def run(paths, client, full=False, today=None, log=print):
    started = time.time()
    today = today or datetime.date.today()
    os.makedirs(paths.cache, exist_ok=True)
    # The config file marks this folder as a 书脉 root (locate.py looks for it), so a
    # first run writes the defaults; an existing config is left exactly as the user keeps it.
    if not os.path.exists(paths.config):
        lib.save_config(paths.root, lib.load_config(paths.root))

    previous_run = lib.read_json(paths.fetch_report)
    if previous_run and not previous_run.get("finished"):
        log("上一次拉取没有跑完（停在第 %s/%s 本），这次从缓存接着拉。"
            % (previous_run.get("processed"), previous_run.get("total")))

    notebooks, total = fetch_notebooks(client)
    lib.write_json(paths.notebooks_cache, notebooks)
    log("有笔记的书 %d 本（/user/notebooks 只列出有笔记的书，书架上其余的书不在其中）" % len(notebooks))

    shelf = {} if full else fetch_shelf_state(client, log)
    fetched = skipped = refreshed = 0
    failed = []
    raws = []

    def report(processed, finished=False, **extra):
        # Saved on every progress line, so a run that is killed still leaves its
        # progress and failures on disk.
        r = {"startedAt": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started)),
             "finished": finished, "processed": processed, "total": len(notebooks),
             "fetched": fetched, "skipped": skipped, "progressRefreshed": refreshed, "failed": failed,
             "calls": getattr(client, "calls", None), "retried": getattr(client, "retried", None),
             "http499": getattr(client, "http499", None)}
        r.update(extra)
        lib.write_json(paths.fetch_report, r)

    report(0)
    for n, nb in enumerate(notebooks, 1):
        bid = str(nb.get("bookId"))
        cache_path = paths.book_cache(bid)
        cached = lib.read_json(cache_path)
        if cached and not full and (cached.get("notebook") or {}).get("sort") == nb.get("sort"):
            skipped += 1
            if bid in shelf and progress_stale(cached, shelf[bid]):
                try:
                    cached["progress"] = client.call("/book/getprogress", bookId=bid)
                    cached["shelfReadUpdateTime"], cached["shelfFinish"] = shelf[bid]
                    lib.write_json(cache_path, cached, indent=None)
                    refreshed += 1
                except UpgradeRequired:
                    raise
                except WereadError as e:
                    failed.append("%s（%s）进度：%s" % ((nb.get("book") or {}).get("title", ""), bid, e))
            raws.append(cached)
        else:
            try:
                raw = fetch_book(client, nb)
                if bid in shelf:
                    raw["shelfReadUpdateTime"], raw["shelfFinish"] = shelf[bid]
                lib.write_json(cache_path, raw, indent=None)
                raws.append(raw)
                fetched += 1
            except UpgradeRequired:
                raise
            except WereadError as e:
                failed.append("%s（%s）：%s" % ((nb.get("book") or {}).get("title", ""), bid, e))
                if cached:
                    raws.append(cached)
        if n % PROGRESS_EVERY == 0 or n == len(notebooks):
            log("  书目 %d/%d：新拉取 %d，未变化跳过 %d（其中刷新进度 %d），失败 %d"
                % (n, len(notebooks), fetched, skipped, refreshed, len(failed)))
            report(n)

    overall, months, years, months_fetched = fetch_readdata(client, paths, today, log)
    secs = per_book_seconds(months)

    previous = {str(b["bookId"]): b["fileName"] for b in lib.read_json(paths.books_json, []) if b.get("fileName")}
    books, empty = [], 0
    for raw in raws:
        b = normalise_book(raw, secs.get(str((raw.get("notebook") or {}).get("bookId")), 0))
        if b["marks"] == 0 and b["thoughts"] == 0:
            empty += 1
            continue
        books.append(b)
    names = lib.assign_filenames(books, previous)
    for b in books:
        b["fileName"] = names[b["bookId"]]
    books.sort(key=lambda b: -(b["noteSort"] or 0))
    lib.write_json(paths.books_json, books)
    stats = build_stats(overall, months, years, today)
    # The API rounds its own note total ("1.5万条"); count what was actually exported.
    stats["notes"] = sum(b["marks"] + b["thoughts"] for b in books)
    lib.write_json(paths.stats_json, stats)

    summary = {
        "books": len(books), "fetched": fetched, "skipped": skipped, "progressRefreshed": refreshed, "failed": failed, "empty": empty,
        "highlights": sum(b["marks"] for b in books), "thoughts": sum(b["thoughts"] for b in books),
        "orphans": sum(len(b["orphanThoughts"]) for b in books),
        "months": len(months), "monthsFetched": months_fetched,
        "calls": getattr(client, "calls", None), "http499": getattr(client, "http499", None),
        "retried": getattr(client, "retried", None), "seconds": round(time.time() - started, 1),
    }
    log("写入 %d 本书：划线 %d 条，想法 %d 条（其中 %d 条对不上划线）"
        % (summary["books"], summary["highlights"], summary["thoughts"], summary["orphans"]))
    if empty:
        log("跳过 %d 本只有书签、没有可导出内容的书" % empty)
    log("阅读统计 %d 个月（本次请求 %d 个月），累计 %s 小时，%s 天"
        % (len(months), months_fetched, stats["totalHours"], stats["readDays"]))
    log("接口调用 %s 次，重试 %s 次（其中 HTTP 499 %s 次），用时 %.0f 秒"
        % (summary["calls"], summary["retried"], summary["http499"], summary["seconds"]))
    for f in failed:
        log("失败：" + f)
    if failed:
        log("失败的 %d 本书没有写进笔记，重跑同一条命令会补拉。" % len(failed))
    report(len(notebooks), finished=True, books=summary["books"], highlights=summary["highlights"],
           thoughts=summary["thoughts"], seconds=summary["seconds"])
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="拉取微信读书笔记和阅读统计，写入 <root>/.atlas/。")
    ap.add_argument("--root", required=True, help="Obsidian 库里的 微信读书 根目录")
    ap.add_argument("--full", action="store_true", help="忽略缓存，所有书重新拉取")
    ap.add_argument("--skill-version", help="手动指定 skill_version，默认从官方 weread skill 读取")
    args = ap.parse_args(argv)
    # A full fetch runs for minutes, often in the background with output sent to a
    # file; flush each progress line so the log shows where it is.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    paths = lib.Paths(args.root)
    client = make_client(args)
    try:
        summary = run(paths, client, full=args.full)
    except UpgradeRequired as e:
        print("微信读书接口要求升级官方 weread skill，已停止：%s" % e, file=sys.stderr)
        return 3
    except WereadError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 1 if summary["books"] == 0 and summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
