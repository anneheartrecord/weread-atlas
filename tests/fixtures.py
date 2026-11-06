"""Synthetic WeRead responses for tests. All books, people and text are invented."""

import datetime
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from weread_client import UpgradeRequired  # noqa: E402

TODAY = datetime.date(2026, 11, 6)
REGIST = int(time.mktime(datetime.datetime(2026, 8, 20, 10).timetuple()))


def ts(y, m, d):
    return int(time.mktime(datetime.datetime(y, m, d, 12).timetuple()))


def notebook(book_id, title, author, sort, cat="经济理财-理财"):
    return {"bookId": book_id, "sort": sort, "noteCount": 3, "reviewCount": 2, "bookmarkCount": 0,
            "readingProgress": 40, "markedStatus": 0,
            "book": {"bookId": book_id, "title": title, "author": author, "cover": "https://example.com/%s.jpg" % book_id,
                     "categories": [{"title": cat}]}}


def info(book_id, title, author, cat="经济理财-理财"):
    return {"bookId": book_id, "title": title, "author": author, "cover": "https://example.com/%s.jpg" % book_id,
            "category": cat, "newRating": 852, "readerLink": "https://example.com/read/%s" % book_id,
            "deepLink": "https://example.com/book/%s" % book_id}


def mark(book_id, uid, rng, text, t=1):
    return {"bookId": book_id, "chapterUid": uid, "range": rng, "markText": text, "createTime": t, "type": 1}


def review(content, abstract=None, uid=None, rng=None, t=1):
    r = {"reviewId": "r%s" % t, "content": content, "createTime": t}
    if abstract is not None:
        r["abstract"] = abstract
    if uid is not None:
        r["chapterUid"] = uid
    if rng is not None:
        r["range"] = rng
    return {"reviewId": r["reviewId"], "review": r}


def default_world():
    """Three books: one rich, one sharing a cleaned title, one with only bookmarks."""
    b1 = "1001"
    b2 = "1002"
    b3 = "1003"
    b4 = "1004"
    w = {
        "notebooks": [
            notebook(b1, "复利花园：慢慢变好的方法（修订版）", "林一", 300),
            notebook(b2, "星海旅人", "周二", 200, cat="文学-科幻"),
            notebook(b4, "复利花园", "赵四", 150),
            notebook(b3, "空白之书", "孙三", 100),
        ],
        "info": {
            b1: info(b1, "复利花园：慢慢变好的方法（修订版）", "林一"),
            b2: info(b2, "星海旅人", "周二", cat="文学-科幻"),
            b3: info(b3, "空白之书", "孙三"),
            b4: info(b4, "复利花园", "赵四"),
        },
        "progress": {
            b1: {"book": {"progress": 100, "finishTime": ts(2026, 10, 1), "updateTime": ts(2026, 10, 2)}},
            b2: {"book": {"progress": 35, "updateTime": ts(2026, 9, 9)}},
            b3: {"book": {"progress": 5}},
            b4: {"book": {"progress": 60, "updateTime": ts(2026, 9, 1)}},
        },
        "bookmarks": {
            b1: {"chapters": [{"chapterUid": 20, "chapterIdx": 2, "title": "第二章 时间"},
                              {"chapterUid": 10, "chapterIdx": 1, "title": "第一章 种子"}],
                 "updated": [
                     mark(b1, 20, "500-520", "时间是最好的肥料，耐心是最好的园丁。"),
                     mark(b1, 10, "300-310", "后面的一句：每天进步一点点。"),
                     mark(b1, 10, "100-120", "前面的一句：种子需要\n等待。"),
                     mark(b1, 99, "5-9", "章节对不上的划线"),
                 ]},
            b2: {"chapters": [{"chapterUid": 1, "chapterIdx": 1, "title": "启航"}],
                 "updated": [mark(b2, 1, "10-30", "星星不会回答，但它们一直都在。")]},
            b3: {"chapters": [], "updated": []},
            b4: {"chapters": [{"chapterUid": 1, "chapterIdx": 1, "title": "序"}],
                 "updated": [mark(b4, 1, "1-5", "另一本同名书的一句话，讲复利。")]},
        },
        "reviews": {
            b1: [
                review("想法甲：要有耐心", abstract="前面的一句：种子需要 等待。", uid=10, rng="100-120", t=1),
                review("想法乙：靠位置匹配", abstract="原文改过了", uid=20, rng="500-520", t=2),
                review("想法丙：同一条划线的第二个想法", abstract="前面的一句：种子需要等待。", t=3),
                review("想法丁：没有划线的想法", abstract="一句没有划线的原文", t=4),
                review("整本书的书评", t=5),
                review("", abstract="空内容不算", t=6),
            ],
            b2: [review("宇宙很大", abstract="星星不会回答，但它们一直都在。", uid=1, rng="10-30")],
            b3: [],
            b4: [],
        },
        "overall": {
            "registTime": REGIST, "totalReadTime": 36000 * 3 + 1800, "readDays": 40,
            "readStat": [{"stat": "读过", "counts": "12本"}, {"stat": "读完", "counts": "4本"},
                         {"stat": "阅读", "counts": "40天"}, {"stat": "笔记", "counts": "1.5万条"}],
            "preferTime": [3600 * (i + 1) for i in range(24)],
            "preferCategory": [{"categoryTitle": "经济理财", "readingTime": 7200, "readingCount": 3},
                               {"categoryTitle": "占位", "readingTime": 0, "readingCount": 0}],
        },
        "monthly": {
            "2026-08": {"totalReadTime": 3600, "readDays": 3, "readLongest": [{"book": {"bookId": b1}, "readTime": 1800}]},
            "2026-09": {"totalReadTime": 7200, "readDays": 10,
                        "readLongest": [{"book": {"bookId": b1}, "readTime": 3600}, {"book": {"bookId": b2}, "readTime": 900},
                                        {"albumInfo": {"albumId": "x"}, "readTime": 600}]},
            "2026-10": {"totalReadTime": 1800, "readDays": 5, "readLongest": [{"book": {"bookId": b1}, "readTime": 1440}]},
            "2026-11": {"totalReadTime": 600, "readDays": 1, "readLongest": []},
        },
        "annual": {2026: {"totalReadTime": 13200, "readDays": 19, "readStat": [{"stat": "读完", "counts": "3本"}]}},
    }
    return w


class FakeClient(object):
    def __init__(self, world, page_size=2, upgrade_on=None):
        self.w = world
        self.page_size = page_size
        self.upgrade_on = upgrade_on
        self.log = []
        self.calls = 0
        self.http499 = 0
        self.retried = 0

    def call(self, api, **p):
        self.calls += 1
        self.log.append((api, dict(p)))
        if self.upgrade_on and self.upgrade_on == (api, p.get("bookId")):
            raise UpgradeRequired("请升级到 9.9.9")
        if api == "/user/notebooks":
            books = sorted(self.w["notebooks"], key=lambda b: -b["sort"])
            if "lastSort" in p:
                books = [b for b in books if b["sort"] < p["lastSort"]]
            page = books[:self.page_size]
            return {"books": page, "hasMore": 1 if len(books) > self.page_size else 0,
                    "totalBookCount": len(self.w["notebooks"])}
        if api == "/shelf/sync":
            return {"books": self.w.get("shelf", [])}
        if api == "/book/info":
            return self.w["info"][p["bookId"]]
        if api == "/book/getprogress":
            return self.w["progress"][p["bookId"]]
        if api == "/book/bookmarklist":
            return self.w["bookmarks"][p["bookId"]]
        if api == "/review/list/mine":
            items = self.w["reviews"][p["bookid"]]
            start = p.get("synckey", 0)
            page = items[start:start + self.page_size]
            more = start + self.page_size < len(items)
            return {"reviews": page, "hasMore": 1 if more else 0, "synckey": start + self.page_size,
                    "totalCount": len(items)}
        if api == "/readdata/detail":
            mode = p["mode"]
            if mode == "overall":
                return self.w["overall"]
            d = datetime.datetime.fromtimestamp(p["baseTime"])
            if mode == "monthly":
                return self.w["monthly"].get("%04d-%02d" % (d.year, d.month), {"totalReadTime": 0})
            if mode == "annually":
                return self.w["annual"].get(d.year, {"totalReadTime": 0})
        raise AssertionError("unexpected call %s %r" % (api, p))

    def count(self, api):
        return sum(1 for a, _ in self.log if a == api)
