import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import atlas_lib as lib  # noqa: E402

BEGIN = lib.BEGIN
END = lib.END


class FrontmatterRoundTrip(unittest.TestCase):
    def roundtrip(self, value):
        text = lib.dump_frontmatter({"k": value})
        fm, body = lib.parse_frontmatter(text)
        self.assertEqual(body, "")
        return fm.get("k")

    def test_plain_values(self):
        self.assertEqual(self.roundtrip("金钱心理学"), "金钱心理学")
        self.assertEqual(self.roundtrip(85), 85)
        self.assertEqual(self.roundtrip(2.5), 2.5)
        self.assertEqual(self.roundtrip("2023-06-24"), "2023-06-24")

    def test_special_characters_round_trip(self):
        for s in [
            "书名：副标题",
            "a: b",
            "C# 入门",
            "[[主题A]]",
            "a, b",
            "他说\"你好\"",
            " leading",
            "trailing ",
            "back\\slash",
            "*星号开头",
            "- 横线开头",
            "'单引号'",
            "true",
            "null",
            "",
        ]:
            self.assertEqual(self.roundtrip(s), s, s)

    def test_numeric_string_stays_string(self):
        text = lib.dump_frontmatter({"bookId": "3300064234"})
        self.assertIn('bookId: "3300064234"', text)
        fm, _ = lib.parse_frontmatter(text)
        self.assertEqual(fm.get("bookId"), "3300064234")

    def test_list_round_trip(self):
        value = ["[[主题A]]", "投资, 周期", "plain", "引号\"里"]
        self.assertEqual(self.roundtrip(value), value)
        self.assertEqual(self.roundtrip([]), [])
        text = lib.dump_frontmatter({"主题": ["[[主题A]]", "[[主题B]]"]})
        self.assertIn('主题: ["[[主题A]]", "[[主题B]]"]', text)

    def test_block_style_list_is_read(self):
        text = "---\ntags:\n  - a\n  - \"b: c\"\nx: 1\n---\nbody\n"
        fm, body = lib.parse_frontmatter(text)
        self.assertEqual(fm.get("tags"), ["a", "b: c"])
        self.assertEqual(fm.get("x"), 1)
        self.assertEqual(body, "body\n")

    def test_no_frontmatter(self):
        fm, body = lib.parse_frontmatter("hello\n---\n")
        self.assertIsNone(fm)
        self.assertEqual(body, "hello\n---\n")


class MergeNote(unittest.TestCase):
    def make(self):
        return (
            "---\n"
            "mine: 用户字段\n"
            "书名: 旧书名\n"
            "tags:\n"
            "  - 读书\n"
            "进度: 10\n"
            "rating: 5\n"
            "---\n"
            "用户在区块前写的话\n\n"
            + BEGIN + "\n旧内容\n" + END + "\n\n"
            "用户在区块后写的话：[[链接]]\n"
        )

    def test_user_text_and_keys_survive(self):
        out = lib.merge_note(self.make(), "新内容", {"书名": "新书名", "进度": 100, "作者": "某人"})
        self.assertIn("用户在区块前写的话\n\n" + BEGIN + "\n新内容\n" + END, out)
        self.assertTrue(out.endswith(END + "\n\n用户在区块后写的话：[[链接]]\n"))
        self.assertNotIn("旧内容", out)
        fm, _ = lib.parse_frontmatter(out)
        self.assertEqual(fm.keys(), ["mine", "书名", "tags", "进度", "rating", "作者"])
        self.assertEqual(fm.get("mine"), "用户字段")
        self.assertEqual(fm.get("tags"), ["读书"])
        self.assertEqual(fm.get("书名"), "新书名")
        self.assertEqual(fm.get("进度"), 100)
        self.assertIn("tags:\n  - 读书\n", out)

    def test_remove_field(self):
        out = lib.merge_note(self.make(), "x", {}, remove_fields=["进度", "不存在"])
        fm, _ = lib.parse_frontmatter(out)
        self.assertEqual(fm.keys(), ["mine", "书名", "tags", "rating"])

    def test_idempotent(self):
        updates = {"书名": "新书名：副标题", "bookId": "123", "主题": ["[[A]]"]}
        once = lib.merge_note(self.make(), "内容\n\n- 一条", updates)
        twice = lib.merge_note(once, "内容\n\n- 一条", updates)
        self.assertEqual(once.encode("utf-8"), twice.encode("utf-8"))

    def test_unchanged_value_keeps_raw_line(self):
        text = "---\n书名: '单引号写法'\n---\n" + BEGIN + "\nx\n" + END + "\n"
        out = lib.merge_note(text, "x", {"书名": "单引号写法"})
        self.assertEqual(out, text)

    def test_missing_markers_with_frontmatter(self):
        text = "---\nmine: 1\n---\n\n用户原有正文\n"
        out = lib.merge_note(text, "生成", {"书名": "书"})
        self.assertEqual(out, "---\nmine: 1\n书名: 书\n---\n" + BEGIN + "\n生成\n" + END + "\n\n用户原有正文\n")
        self.assertEqual(lib.merge_note(out, "生成", {"书名": "书"}), out)

    def test_missing_markers_without_frontmatter(self):
        out = lib.merge_note("只有正文\n", "生成", {})
        self.assertEqual(out, BEGIN + "\n生成\n" + END + "\n\n只有正文\n")

    def test_new_file(self):
        out = lib.merge_note(None, "生成", {"书名": "书", "bookId": "1"})
        self.assertEqual(out, '---\n书名: 书\nbookId: "1"\n---\n' + BEGIN + "\n生成\n" + END + "\n")
        self.assertEqual(lib.merge_note("", "生成", {}), BEGIN + "\n生成\n" + END + "\n")

    def test_crlf_input(self):
        text = self.make().replace("\n", "\r\n")
        out = lib.merge_note(text, "新内容\n第二行", {"进度": 50})
        self.assertNotIn("\n", out.replace("\r\n", ""))
        self.assertIn("用户在区块后写的话：[[链接]]\r\n", out)
        self.assertIn(BEGIN + "\r\n新内容\r\n第二行\r\n" + END, out)
        fm, _ = lib.parse_frontmatter(out)
        self.assertEqual(fm.get("进度"), 50)
        self.assertEqual(fm.get("mine"), "用户字段")
        again = lib.merge_note(out, "新内容\n第二行", {"进度": 50})
        self.assertEqual(out.encode("utf-8"), again.encode("utf-8"))

    def test_read_block(self):
        self.assertEqual(lib.read_block(self.make()), "旧内容")
        self.assertIsNone(lib.read_block("no markers"))


class Filenames(unittest.TestCase):
    def test_clean_title(self):
        self.assertEqual(lib.clean_title("小狗钱钱（全新升级版）"), "小狗钱钱")
        self.assertEqual(lib.clean_title("编程入门：从零到一"), "编程入门")
        self.assertEqual(lib.clean_title("Book Title: A Subtitle (2nd Edition)"), "Book Title")
        self.assertEqual(lib.clean_title("问号?星号*冒号#井号[括号]"), "问号星号冒号井号")
        self.assertEqual(lib.clean_title("a/b\\c<d>e|f^g\"h"), "abcde")
        self.assertEqual(lib.clean_title("A/B测试"), "AB测试")
        self.assertEqual(lib.clean_title("12:30 的约会"), "1230 的约会")
        self.assertEqual(lib.clean_title("（只有括号）"), "只有括号")
        self.assertEqual(lib.clean_title("..."), "未命名")
        self.assertEqual(lib.clean_title("投资法 副题 (甲乙(Jia Yi),丙丁(Bing Ding))"), "投资法 副题")
        self.assertEqual(lib.clean_title("书名（外层（内层）说明）"), "书名")

    def test_author_suffix_drops_nationality(self):
        books = [
            {"bookId": "1", "title": "同名", "author": "某甲", "noteSort": 1},
            {"bookId": "2", "title": "同名", "author": "[美]乔治·某乙", "noteSort": 2},
            {"bookId": "3", "title": "同名", "author": "（英）某丙", "noteSort": 3},
        ]
        names = lib.assign_filenames(books, {})
        self.assertEqual(names["2"], "同名（乔治·某乙）")
        self.assertEqual(names["3"], "同名（某丙）")

    def test_assign_filenames_collision_and_stability(self):
        books = [
            {"bookId": "2", "title": "同名书（新版）", "author": "乙", "noteSort": 200},
            {"bookId": "1", "title": "同名书", "author": "甲", "noteSort": 100},
            {"bookId": "3", "title": "同名书", "author": "乙", "noteSort": 300},
        ]
        names = lib.assign_filenames(books, {})
        self.assertEqual(names, {"1": "同名书", "2": "同名书（乙）", "3": "同名书（乙，3）"})
        # an existing assignment never changes, even when an older book shows up later
        names2 = lib.assign_filenames(books + [{"bookId": "0", "title": "同名书", "author": "丙", "noteSort": 1}], names)
        self.assertEqual({k: names2[k] for k in names}, names)
        self.assertEqual(names2["0"], "同名书（丙）")

    def test_case_insensitive_collision(self):
        books = [
            {"bookId": "1", "title": "Python", "author": "A", "noteSort": 1},
            {"bookId": "2", "title": "python", "author": "B", "noteSort": 2},
        ]
        self.assertEqual(lib.assign_filenames(books, {})["2"], "python（B）")


class ConfigAndPaths(unittest.TestCase):
    def test_config_defaults_and_save(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = lib.load_config(d)
            self.assertEqual(cfg["topN"], 50)
            self.assertEqual(cfg["theme"], "舆图")
            cfg["exclude"].append("片段")
            lib.save_config(d, cfg)
            self.assertEqual(lib.load_config(d)["exclude"], ["片段"])
            p = lib.Paths(d)
            self.assertTrue(p.config.endswith(os.path.join(".atlas", "config.json")))
            self.assertTrue(p.book_note("书").endswith(os.path.join("书", "书.md")))


class BookBlock(unittest.TestCase):
    def test_render_book_block(self):
        book = {
            "chapters": [
                {"title": "第一章", "highlights": [
                    {"text": "第一句", "thought": "想法一", "pos": 1},
                    {"text": "第二句", "thought": None, "pos": 5},
                ]},
                {"title": "第二章", "highlights": [{"text": "第三句", "thought": "甲\n乙", "pos": 1}]},
            ],
            "orphanThoughts": [{"text": "孤立想法", "quote": "原文"}],
        }
        out = lib.render_book_block(book, ["主题A", "主题B"])
        self.assertEqual(
            out,
            "> 主题：[[主题A]] · [[主题B]]\n\n"
            "## 第一章\n\n- 第一句\n  - 💭 想法一\n- 第二句\n\n"
            "## 第二章\n\n- 第三句\n  - 💭 甲\n  - 💭 乙\n\n"
            "## 没有对应划线的想法\n\n- 💭 孤立想法\n  > 原文",
        )
        out2 = lib.render_book_block({"chapters": [], "orphanThoughts": []}, [])
        self.assertEqual(out2, "")


if __name__ == "__main__":
    unittest.main()
