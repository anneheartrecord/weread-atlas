import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fixtures as fx  # noqa: E402
import atlas_lib as lib  # noqa: E402
import fetch  # noqa: E402
import weread_client  # noqa: E402


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.paths = lib.Paths(self.dir)
        self.out = []

    def tearDown(self):
        shutil.rmtree(self.dir)

    def run_fetch(self, client, full=False):
        return fetch.run(self.paths, client, full=full, today=fx.TODAY, log=self.out.append)

    def books(self):
        return {b["bookId"]: b for b in lib.read_json(self.paths.books_json)}

    def test_first_run_writes_default_config_and_keeps_user_edits(self):
        self.run_fetch(fx.FakeClient(fx.default_world()))
        cfg = lib.read_json(self.paths.config)
        self.assertEqual(cfg["rootName"], "微信读书")
        self.assertEqual(cfg["exclude"], [])
        cfg["title"] = "我的书脉"
        lib.save_config(self.dir, cfg)
        self.run_fetch(fx.FakeClient(fx.default_world()))
        self.assertEqual(lib.read_json(self.paths.config)["title"], "我的书脉")

    def test_books_json_shape(self):
        summary = self.run_fetch(fx.FakeClient(fx.default_world()))
        books = self.books()
        self.assertEqual(set(books), {"1001", "1002", "1004"})  # 1003 has nothing exportable
        self.assertEqual(summary["empty"], 1)
        b = books["1001"]
        self.assertEqual(b["title"], "复利花园：慢慢变好的方法（修订版）")
        self.assertEqual(b["category"], "经济理财")
        self.assertEqual(b["rating"], 85.2)
        self.assertEqual(b["progress"], 100)
        self.assertEqual(b["finished"], "2026-10-01")
        self.assertEqual(b["readAt"], "2026-10-02")
        self.assertEqual(b["link"], "https://example.com/read/1001")
        self.assertEqual(b["hours"], round((1800 + 3600 + 1440) / 3600.0, 1))
        self.assertEqual(b["noteSort"], 300)
        self.assertEqual([c["title"] for c in b["chapters"]], ["第一章 种子", "第二章 时间", lib.UNKNOWN_CHAPTER])
        first = b["chapters"][0]["highlights"]
        self.assertEqual([h["pos"] for h in first], [100, 300])
        self.assertEqual(first[0]["text"], "前面的一句：种子需要 等待。")
        self.assertEqual(first[0]["thought"], "想法甲：要有耐心\n想法丙：同一条划线的第二个想法")
        self.assertIsNone(first[1]["thought"])
        self.assertEqual(b["chapters"][1]["highlights"][0]["thought"], "想法乙：靠位置匹配")
        self.assertEqual(b["orphanThoughts"], [
            {"text": "想法丁：没有划线的想法", "quote": "一句没有划线的原文"},
            {"text": "整本书的书评", "quote": None},
        ])
        self.assertEqual(b["marks"], 4)
        self.assertEqual(b["thoughts"], 5)
        # same cleaned title: the book noted earlier (smaller noteSort) keeps the plain name
        self.assertEqual(books["1004"]["fileName"], "复利花园")
        self.assertEqual(b["fileName"], "复利花园（林一）")

    def test_stats_json(self):
        self.run_fetch(fx.FakeClient(fx.default_world()))
        s = lib.read_json(self.paths.stats_json)
        self.assertEqual(s["since"], "2026-08-20")
        self.assertEqual(s["totalHours"], 31)
        self.assertEqual(s["readBooks"], 12)
        self.assertEqual(s["finishedBooks"], 4)
        self.assertEqual(s["notes"], 15000)
        self.assertEqual(s["generatedAt"], "2026-11-06")
        self.assertEqual([m["month"] for m in s["months"]], ["2026-08", "2026-09", "2026-10", "2026-11"])
        self.assertEqual(s["months"][1]["hours"], 2.0)
        self.assertEqual(len(s["hourly"]), 24)
        self.assertEqual(s["hourly"][6], {"hour": 6, "hours": 1.0})   # preferTime[0] is 6 am
        self.assertEqual(s["hourly"][5], {"hour": 5, "hours": 24.0})  # preferTime[23] is 5 am
        self.assertEqual(s["categories"], [{"name": "经济理财", "hours": 2.0, "count": 3}])
        self.assertEqual(s["years"], [{"year": 2026, "hours": 3.7, "days": 19, "finished": 3}])

    def test_paging(self):
        c = fx.FakeClient(fx.default_world(), page_size=2)
        self.run_fetch(c)
        nb_calls = [p for a, p in c.log if a == "/user/notebooks"]
        self.assertEqual(nb_calls, [{"count": 100}, {"count": 100, "lastSort": 200}])
        rv_calls = [p for a, p in c.log if a == "/review/list/mine" and p["bookid"] == "1001"]
        self.assertEqual([p.get("synckey", 0) for p in rv_calls], [0, 2, 4])

    def test_incremental(self):
        w = fx.default_world()
        self.run_fetch(fx.FakeClient(w))
        c = fx.FakeClient(w)
        summary = self.run_fetch(c)
        self.assertEqual(c.count("/book/info"), 0)
        self.assertEqual(summary["skipped"], 4)
        # only the current and previous month are refetched
        months = [p for a, p in c.log if a == "/readdata/detail" and p["mode"] == "monthly"]
        self.assertEqual(len(months), 2)
        # a changed sort refetches that book only
        w["notebooks"][1]["sort"] = 400
        c = fx.FakeClient(w)
        self.run_fetch(c)
        self.assertEqual([p["bookId"] for a, p in c.log if a == "/book/info"], ["1002"])
        c = fx.FakeClient(w)
        self.run_fetch(c, full=True)
        self.assertEqual(c.count("/book/info"), 4)

    def test_shelf_refreshes_progress_only(self):
        w = fx.default_world()
        w["shelf"] = [
            {"bookId": "1001", "readUpdateTime": fx.ts(2026, 10, 2), "finishReading": 1},
            {"bookId": "1002", "readUpdateTime": fx.ts(2026, 9, 9), "finishReading": 0},
            {"bookId": "1004", "readUpdateTime": fx.ts(2026, 9, 1), "finishReading": 0},
        ]
        self.run_fetch(fx.FakeClient(w))
        c = fx.FakeClient(w)
        summary = self.run_fetch(c)
        self.assertEqual(c.count("/shelf/sync"), 1)
        self.assertEqual(c.count("/book/getprogress"), 0)
        self.assertEqual(summary["progressRefreshed"], 0)
        # read 1002 again (no new notes) and finish 1004 on another device
        w["shelf"][1]["readUpdateTime"] = fx.ts(2026, 11, 5)
        w["progress"]["1002"] = {"book": {"progress": 80, "updateTime": fx.ts(2026, 11, 5)}}
        w["shelf"][2]["finishReading"] = 1
        w["progress"]["1004"] = {"book": {"progress": 100, "finishTime": fx.ts(2026, 11, 4), "updateTime": fx.ts(2026, 9, 1)}}
        c = fx.FakeClient(w)
        summary = self.run_fetch(c)
        self.assertEqual(sorted(p["bookId"] for a, p in c.log if a == "/book/getprogress"), ["1002", "1004"])
        self.assertEqual(c.count("/book/bookmarklist") + c.count("/review/list/mine") + c.count("/book/info"), 0)
        self.assertEqual(summary["progressRefreshed"], 2)
        books = self.books()
        self.assertEqual((books["1002"]["progress"], books["1002"]["readAt"]), (80, "2026-11-05"))
        self.assertEqual(books["1004"]["finished"], "2026-11-04")
        # the shelf values are remembered, so the next run refetches nothing
        c = fx.FakeClient(w)
        self.assertEqual(self.run_fetch(c)["progressRefreshed"], 0)
        self.assertEqual(c.count("/book/getprogress"), 0)
        # --full skips the shelf call
        c = fx.FakeClient(w)
        self.run_fetch(c, full=True)
        self.assertEqual(c.count("/shelf/sync"), 0)

    def test_filename_stable_across_runs(self):
        w = fx.default_world()
        self.run_fetch(fx.FakeClient(w))
        before = {k: v["fileName"] for k, v in self.books().items()}
        w["notebooks"].append(fx.notebook("1005", "复利花园", "钱五", 1))
        w["info"]["1005"] = fx.info("1005", "复利花园", "钱五")
        w["progress"]["1005"] = {"book": {"progress": 1}}
        w["bookmarks"]["1005"] = {"chapters": [], "updated": [fx.mark("1005", 1, "1-2", "第五本书")]}
        w["reviews"]["1005"] = []
        self.run_fetch(fx.FakeClient(w))
        after = self.books()
        for k, v in before.items():
            self.assertEqual(after[k]["fileName"], v)
        self.assertEqual(after["1005"]["fileName"], "复利花园（钱五）")

    def test_api_error_skips_book(self):
        w = fx.default_world()

        class Failing(fx.FakeClient):
            def call(self, api, **p):
                if api == "/book/info" and p.get("bookId") == "1002":
                    raise weread_client.ApiError(api, -1, "书籍不存在")
                return fx.FakeClient.call(self, api, **p)

        summary = self.run_fetch(Failing(w))
        self.assertEqual(len(summary["failed"]), 1)
        self.assertNotIn("1002", self.books())

    def test_upgrade_info_stops_with_exit_3(self):
        c = fx.FakeClient(fx.default_world(), upgrade_on=("/book/info", "1004"))
        with self.assertRaises(weread_client.UpgradeRequired):
            self.run_fetch(c)
        c = fx.FakeClient(fx.default_world(), upgrade_on=("/book/info", "1004"))
        with mock.patch.object(fetch, "make_client", return_value=c), mock.patch("sys.stderr", io.StringIO()), \
                mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(fetch.main(["--root", self.dir]), 3)


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"HOME": self.home, "WEREAD_API_KEY": "wrk-test"})
        self.env.start()
        os.environ.pop("WEREAD_SKILL_DIR", None)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.home)

    def write_skill(self, folder, text):
        d = os.path.join(self.home, folder)
        os.makedirs(d)
        with open(os.path.join(d, "SKILL.md"), "w") as f:
            f.write(text)
        return d

    def test_version_from_metadata(self):
        self.write_skill(".claude/skills/weread-skills", '---\nname: weread-skills\nmetadata:\n  version: "1.2.3"\n---\n')
        self.assertEqual(weread_client.discover_skill_version()[0], "1.2.3")

    def test_version_top_level_and_env_dir(self):
        d = self.write_skill("custom", "---\nname: weread-skills\nversion: 2.0.1\n---\n")
        os.environ["WEREAD_SKILL_DIR"] = d
        self.assertEqual(weread_client.discover_skill_version()[0], "2.0.1")

    def test_version_from_renamed_folder(self):
        self.write_skill(".codex/skills/my-weread", '---\nname: weread-skills\nmetadata:\n  version: "1.0.9"\n---\n')
        self.write_skill(".codex/skills/other-weread", '---\nname: something-else\nversion: 9.9.9\n---\n')
        self.assertEqual(weread_client.discover_skill_version()[0], "1.0.9")

    def test_missing_skill(self):
        self.assertEqual(weread_client.discover_skill_version(), (None, None))
        with self.assertRaises(weread_client.WereadError) as cm:
            weread_client.Client()
        self.assertIn("weread-skills.zip", str(cm.exception))

    def test_call_body_retry_and_upgrade(self):
        c = weread_client.Client(skill_version="1.0.6", pause=0)
        sent = []
        replies = [urllib.error.HTTPError("u", 499, "busy", {}, io.BytesIO(b"")), {"ok": 1}]

        def post(body):
            sent.append(body)
            r = replies.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        with mock.patch.object(c, "_post", side_effect=post), mock.patch.object(weread_client, "BACKOFF", 0):
            self.assertEqual(c.call("/user/notebooks", count=100, lastSort=5), {"ok": 1})
        self.assertEqual(sent[0], {"api_name": "/user/notebooks", "count": 100, "lastSort": 5, "skill_version": "1.0.6"})
        self.assertEqual(c.http499, 1)
        with mock.patch.object(c, "_post", return_value={"upgrade_info": {"message": "请升级"}}):
            with self.assertRaises(weread_client.UpgradeRequired) as cm:
                c.call("/book/info", bookId="1")
        self.assertIn("请升级", str(cm.exception))
        with mock.patch.object(c, "_post", return_value={"errcode": -2012, "errmsg": "登录超时"}):
            with self.assertRaises(weread_client.ApiError):
                c.call("/book/info", bookId="1")

    def test_gives_up_after_retries(self):
        c = weread_client.Client(skill_version="1.0.6", pause=0, retries=3)
        err = urllib.error.HTTPError("u", 502, "bad", {}, io.BytesIO(b""))
        with mock.patch.object(c, "_post", side_effect=err) as post, mock.patch.object(weread_client, "BACKOFF", 0):
            with self.assertRaises(weread_client.WereadError):
                c.call("/book/info", bookId="1")
        self.assertEqual(post.call_count, 3)


if __name__ == "__main__":
    unittest.main()
