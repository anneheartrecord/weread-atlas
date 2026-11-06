"""notes.py, digest.py, topics.py and share_check.py on synthetic data."""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fixtures as fx  # noqa: E402
import atlas_lib as lib  # noqa: E402
import digest  # noqa: E402
import fetch  # noqa: E402
import notes  # noqa: E402
import share_check  # noqa: E402
import topics  # noqa: E402


def quiet(*_):
    pass


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.paths = lib.Paths(self.dir)
        fetch.run(self.paths, fx.FakeClient(fx.default_world()), today=fx.TODAY, log=quiet)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def read(self, path):
        return lib.read_text(path)

    def note(self, name):
        return self.read(self.paths.book_note(name))

    def write_topics(self, data):
        lib.write_json(self.paths.topics_json, data)

    def good_topics(self):
        return {
            "domains": ["成长与复利", "小说"],
            "topics": [{
                "name": "耐心的复利",
                "domain": "成长与复利",
                "oneLiner": "慢慢变好靠的是耐心和时间",
                "books": ["复利花园（林一）", "复利花园"],
                "viewpoints": [
                    {"claim": "时间是肥料", "text": "等待种子发芽需要耐心。", "books": ["复利花园（林一）"]},
                    {"claim": "每天一点点", "text": "进步靠积累。", "books": ["复利花园", "不存在的书"]},
                ],
            }],
            "assign": {"星海旅人": "小说"},
        }


class NotesTest(Base):
    def test_note_content(self):
        notes.run(self.paths, log=quiet)
        text = self.note("复利花园（林一）")
        fm = lib.read_frontmatter(text)
        self.assertEqual(list(fm.keys()), notes.FIELDS)
        self.assertEqual(fm["书名"], "复利花园：慢慢变好的方法（修订版）")
        self.assertEqual(fm["bookId"], "1001")
        self.assertIn('bookId: "1001"', text)
        self.assertEqual(fm["读完"], "2026-10-01")
        self.assertEqual(fm["时长"], 1.9)
        self.assertEqual(fm["划线数"], 4)
        block = lib.read_block(text)
        self.assertTrue(block.startswith("## 第一章 种子\n\n- 前面的一句：种子需要 等待。\n  - 💭 想法甲：要有耐心\n  - 💭 想法丙"))
        self.assertIn("## 第二章 时间\n\n- 时间是最好的肥料，耐心是最好的园丁。\n  - 💭 想法乙：靠位置匹配", block)
        self.assertTrue(block.endswith("## 没有对应划线的想法\n\n- 💭 想法丁：没有划线的想法\n  > 一句没有划线的原文\n- 💭 整本书的书评"))
        self.assertNotIn("读完", lib.read_frontmatter(self.note("星海旅人")))

    def test_user_content_and_topics_survive(self):
        notes.run(self.paths, log=quiet)
        path = self.paths.book_note("星海旅人")
        text = self.read(path)
        text = text.replace("---\n", "---\n我的评分: 5\n", 1)
        text = text.replace("进度: 35", "进度: 35\n领域: [小说]\n主题: [\"[[星辰]]\"]")
        text += "\n我自己写的读后感。\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        notes.run(self.paths, log=quiet)
        out = self.read(path)
        self.assertTrue(out.endswith("我自己写的读后感。\n"))
        fm = lib.read_frontmatter(out)
        self.assertEqual(list(fm)[0], "我的评分")
        self.assertEqual(fm["领域"], ["小说"])
        self.assertTrue(lib.read_block(out).startswith("> 主题：[[星辰]]\n\n## 启航"))
        counts = notes.run(self.paths, log=quiet)
        self.assertEqual(counts["unchanged"], 3)


class BlockGuardTest(Base):
    def edit_inside(self, path, old, new):
        text = self.read(path)
        self.assertIn(old, text)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace(old, new, 1))

    def backups(self):
        d = os.path.join(self.paths.atlas, "overwritten")
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    def test_first_write_and_unregistered_files_are_not_flagged(self):
        out = []
        notes.run(self.paths, log=out.append)
        self.assertEqual(self.backups(), [])
        self.assertFalse(any("手动改过" in line for line in out))
        os.remove(os.path.join(self.paths.atlas, "blocks.json"))  # a vault from before the registry existed
        path = self.paths.book_note("星海旅人")
        self.edit_inside(path, "## ", "## 我改的标题 ")
        notes.run(self.paths, log=quiet)
        self.assertEqual(self.backups(), [])

    def test_hand_edit_inside_block_is_backed_up_and_reported(self):
        notes.run(self.paths, log=quiet)
        path = self.paths.book_note("星海旅人")
        self.edit_inside(path, "## ", "## 我改的标题 ")
        out = []
        notes.run(self.paths, log=out.append)
        self.assertEqual(len(self.backups()), 1)
        saved = self.read(os.path.join(self.paths.atlas, "overwritten", self.backups()[0]))
        self.assertIn("我改的标题", saved)
        self.assertNotIn("我改的标题", self.read(path))
        self.assertTrue(any("1 处生成区块被手动改过" in line and "overwritten" in line for line in out))
        notes.run(self.paths, log=quiet)  # the rewrite is now registered: no second backup
        self.assertEqual(len(self.backups()), 1)

    def test_data_change_alone_is_not_flagged(self):
        notes.run(self.paths, log=quiet)
        books = lib.read_json(self.paths.books_json)
        books[0]["chapters"][0]["highlights"].append({"text": "新划的一句", "thought": None, "pos": 5000})
        lib.write_json(self.paths.books_json, books)
        out = []
        notes.run(self.paths, log=out.append)
        self.assertIn("新划的一句", self.note(books[0]["fileName"]))
        self.assertEqual(self.backups(), [])

    def test_topic_card_edit_is_backed_up(self):
        self.write_topics(self.good_topics())
        topics.run(self.paths, log=quiet)
        path = self.paths.topic_card("耐心的复利")
        self.edit_inside(path, "慢慢变好靠的是耐心和时间", "我自己改的结论")
        out = []
        topics.run(self.paths, log=out.append)
        self.assertEqual(len(self.backups()), 1)
        self.assertTrue(any("手动改过" in line for line in out))


class DigestTest(Base):
    def test_top(self):
        files = digest.run(self.paths, top=2, log=quiet)
        self.assertEqual(len(files), 1)
        text = self.read(files[0][0])
        self.assertIn("## 1. 复利花园：慢慢变好的方法（修订版）", text)
        self.assertIn("- 文件名：复利花园（林一）", text)
        self.assertIn("- 💭 想法丁：没有划线的想法\n  > 一句没有划线的原文", text)
        self.assertNotIn("星海旅人", text.split("## 2.")[0])
        self.assertEqual(files[0][1], 2)

    def test_many_files_and_stale_removed(self):
        books = lib.read_json(self.paths.books_json)
        many = []
        for i in range(32):
            b = json.loads(json.dumps(books[0]))
            b["bookId"] = str(5000 + i)
            b["fileName"] = "书%d" % i
            many.append(b)
        lib.write_json(self.paths.books_json, many)
        os.makedirs(self.paths.digest_dir)
        with open(os.path.join(self.paths.digest_dir, "digest-09.md"), "w") as f:
            f.write("old")
        files = digest.run(self.paths, top=50, log=quiet)
        self.assertEqual([n for _, n in files], [15, 15, 2])
        self.assertFalse(os.path.exists(os.path.join(self.paths.digest_dir, "digest-09.md")))

    def test_pick_highlights_spread(self):
        hls = [{"text": "第%02d句。这是一条足够长的划线文字，用来测试挑选。" % i, "pos": i, "thought": None} for i in range(40)]
        book = {"chapters": [{"title": "甲", "highlights": hls[:20]}, {"title": "乙", "highlights": hls[20:]}]}
        picked = digest.pick_highlights(book)
        self.assertEqual(len(picked), 12)
        self.assertEqual([t for t, _ in picked], sorted(t for t, _ in picked))
        self.assertTrue(picked[0][0].startswith("第0") and picked[-1][0] >= "第36")

    def test_new(self):
        self.write_topics(self.good_topics())
        old = time.time() - 100
        os.utime(self.paths.topics_json, (old, old))
        files = digest.run(self.paths, new=True, log=quiet)
        self.assertEqual(files, [])
        books = lib.read_json(self.paths.books_json)
        books[0]["noteSort"] = time.time()
        lib.write_json(self.paths.books_json, books)
        files = digest.run(self.paths, new=True, log=quiet)
        self.assertEqual(files[0][1], 1)


    def test_new_does_not_confuse_books_with_the_same_title(self):
        books = lib.read_json(self.paths.books_json)
        for b in books:
            if b["fileName"] == "复利花园（林一）":
                b["title"] = "复利花园"  # two books titled the same, told apart by file name
        lib.write_json(self.paths.books_json, books)
        data = self.good_topics()
        data["topics"][0]["books"] = ["复利花园"]
        for v in data["topics"][0]["viewpoints"]:
            v["books"] = ["复利花园"]
        self.write_topics(data)
        old = time.time() - 100
        os.utime(self.paths.topics_json, (old, old))
        self.assertEqual([b["fileName"] for b in digest.select_new(books, self.paths)], ["复利花园（林一）"])


class TopicsTest(Base):
    def test_validation_lists_all_errors_and_writes_nothing(self):
        bad = self.good_topics()
        bad["topics"][0]["domain"] = "不存在"
        bad["topics"][0]["oneLiner"] = "长" * 41
        bad["topics"][0]["books"].append("复利花")
        bad["topics"][0]["viewpoints"] = bad["topics"][0]["viewpoints"][:1]
        bad["topics"].append(dict(self.good_topics()["topics"][0]))
        bad["topics"].append(dict(self.good_topics()["topics"][0], name="坏/名字"))
        bad["assign"]["没有这本"] = "小说"
        self.write_topics(bad)
        out = []
        self.assertEqual(topics.run(self.paths, log=out.append), 1)
        joined = "\n".join(out)
        for needle in ["不在 domains 里", "超过 40 个字", "书名找不到：复利花", "是不是", "有 1 条观点",
                       "主题重名：耐心的复利", "文件名不能用的字符", "assign 里的书名找不到"]:
            self.assertIn(needle, joined)
        self.assertFalse(os.path.exists(self.paths.topics_dir))
        self.assertFalse(os.path.exists(self.paths.books_dir))
        self.assertFalse(os.path.exists(self.paths.overview))

    def test_writes_cards_notes_overview(self):
        notes.run(self.paths, log=quiet)
        self.write_topics(self.good_topics())
        out = []
        self.assertEqual(topics.run(self.paths, log=out.append), 0)
        self.assertTrue(any("不在书架上" in line for line in out))
        card = self.read(self.paths.topic_card("耐心的复利"))
        fm = lib.read_frontmatter(card)
        self.assertEqual(fm["主题"], "耐心的复利")
        self.assertEqual(fm["领域"], "成长与复利")
        self.assertEqual(fm["书目"], ["[[复利花园（林一）]]", "[[复利花园]]"])
        self.assertEqual(fm["时长"], 1.9)
        block = lib.read_block(card)
        self.assertIn("## 一句话结论\n\n慢慢变好靠的是耐心和时间", block)
        self.assertIn("1. **时间是肥料**：等待种子发芽需要耐心。 —— [[复利花园（林一）]]", block)
        self.assertIn("2. **每天一点点**：进步靠积累。 —— [[复利花园]] · 《不存在的书》", block)
        mine = block.split("## 我的想法")[1].split("## 代表划线")[0]
        self.assertEqual(mine.count("\n- "), 1)  # one thought per book
        self.assertIn("想法甲：要有耐心 —— [[复利花园（林一）]]\n  > 前面的一句", mine)
        reps = block.split("## 代表划线")[1]
        self.assertLessEqual(reps.count("[[复利花园（林一）]]"), 2)
        self.assertIn("时间是最好的肥料", reps)

        note = self.note("复利花园（林一）")
        nfm = lib.read_frontmatter(note)
        self.assertEqual(nfm["领域"], ["成长与复利"])
        self.assertEqual(nfm["主题"], ["[[耐心的复利]]"])
        self.assertTrue(lib.read_block(note).startswith("> 主题：[[耐心的复利]]\n\n## 第一章"))
        self.assertEqual(lib.read_frontmatter(self.note("星海旅人"))["领域"], ["小说"])
        self.assertNotIn("主题", lib.read_frontmatter(self.note("星海旅人")))

        overview = self.read(self.paths.overview)
        self.assertTrue(overview.startswith(lib.BEGIN))
        self.assertIn("## 成长与复利\n\n2 本书", overview)
        self.assertIn("- [[耐心的复利]] · 2 本", overview)
        self.assertIn("## 小说\n\n1 本书", overview)
        self.assertIn("累计阅读 31 小时", overview)

        # notes.py afterwards keeps the topic line; a second topics run changes nothing
        notes.run(self.paths, log=quiet)
        self.assertEqual(self.note("复利花园（林一）"), note)
        before = {p: self.read(p) for p in [self.paths.topic_card("耐心的复利"), self.paths.overview]}
        topics.run(self.paths, log=quiet)
        for p, t in before.items():
            self.assertEqual(self.read(p), t)

    def two_topics(self):
        data = self.good_topics()
        second = {
            "name": "星际想象",
            "domain": "小说",
            "oneLiner": "远方的故事其实在写此地",
            "books": ["星海旅人"],
            "viewpoints": [
                {"claim": "远方即此地", "text": "科幻写的是现在。", "books": ["星海旅人"]},
                {"claim": "想象要耐心", "text": "慢慢展开。", "books": ["星海旅人"]},
            ],
            "related": [{"topic": "耐心的复利", "why": "后写的理由不会覆盖先写的"}],
        }
        data["topics"][0]["related"] = [{"topic": "星际想象", "why": "长时间尺度才看得见变化"}]
        data["topics"].append(second)
        del data["assign"]["星海旅人"]
        return data

    def test_related_validation(self):
        data = self.two_topics()
        data["topics"][0]["related"] = [
            {"topic": "星际想像", "why": "理由"},
            {"topic": "耐心的复利", "why": "自己"},
            {"topic": "星际想象", "why": ""},
            {"topic": "星际想象", "why": "长" * 27},
            "不是对象",
        ]
        data["topics"][1]["related"] = "不是列表"
        self.write_topics(data)
        out = []
        self.assertEqual(topics.run(self.paths, log=out.append), 1)
        joined = "\n".join(out)
        for needle in ["related 主题找不到：星际想像，是不是「星际想象」", "related 指向了自己", "缺少 why",
                       "超过 26 个字", "related 不是对象", "related 必须是列表"]:
            self.assertIn(needle, joined)
        self.assertFalse(os.path.exists(self.paths.topics_dir))

    def test_topic_named_like_a_book_is_rejected(self):
        data = self.good_topics()
        data["topics"][0]["name"] = "星海旅人"  # also a book's file name: [[星海旅人]] would be ambiguous
        self.write_topics(data)
        out = []
        self.assertEqual(topics.run(self.paths, log=out.append), 1)
        self.assertIn("和书的文件名重名", "\n".join(out))

    def test_small_plan_without_related_still_writes(self):
        self.write_topics(self.good_topics())
        out = []
        self.assertEqual(topics.run(self.paths, log=out.append), 0)

    def four_topics(self):
        data = self.good_topics()
        base = data["topics"][0]
        for i, name in enumerate(["种子与等待", "园丁的耐心", "星际想象"]):
            t = dict(base, name=name, related=[])
            if name == "星际想象":
                t.update(domain="小说", books=["星海旅人", "复利花园"])
            data["topics"].append(t)
        del data["assign"]["星海旅人"]
        return data

    def test_isolated_topics_fail_and_candidates_are_listed(self):
        data = self.four_topics()
        data["topics"][0]["related"] = [{"topic": "种子与等待", "why": "等待本身就是复利的一部分"}]
        self.write_topics(data)
        out = []
        self.assertEqual(topics.run(self.paths, log=out.append), 1)
        joined = "\n".join(out)
        self.assertIn("「园丁的耐心」没有和任何主题建立关系", joined)
        self.assertIn("「星际想象」没有和任何主题建立关系", joined)
        self.assertNotIn("「种子与等待」没有和任何主题建立关系", joined)
        self.assertIn("共读的书", joined)
        self.assertIn("星际想象 · ", joined)  # a cross-domain candidate sharing 复利花园
        self.assertFalse(os.path.exists(self.paths.topics_dir))

    def test_check_prints_candidates_even_when_valid(self):
        data = self.four_topics()
        names = [t["name"] for t in data["topics"]]
        for t, other in zip(data["topics"], names[1:] + names[:1]):
            t["related"] = [{"topic": other, "why": "都在讲耐心的回报"}]
        self.write_topics(data)
        out = []
        self.assertEqual(topics.run(self.paths, check_only=True, log=out.append), 0)
        self.assertTrue(any("校验通过" in line for line in out))

    def test_coverage_and_next_step_reported(self):
        self.write_topics(self.good_topics())
        out = []
        self.assertEqual(topics.run(self.paths, log=out.append), 0)
        joined = "\n".join(out)
        books = lib.read_json(self.paths.books_json)
        self.assertIn("有笔记的书 %d 本，已归入主题 2 本，还有 %d 本不在任何主题里" % (len(books), len(books) - 2), joined)
        self.assertIn("更新书脉", joined)

    def test_related_written_to_both_cards_and_read_back(self):
        self.write_topics(self.two_topics())
        out = []
        self.assertEqual(topics.run(self.paths, log=out.append), 0)
        self.assertTrue(any("用先写的理由" in line for line in out))
        self.assertTrue(any("主题之间的关系 1 条" in line for line in out))
        a = lib.read_block(self.read(self.paths.topic_card("耐心的复利")))
        b = lib.read_block(self.read(self.paths.topic_card("星际想象")))
        self.assertTrue(a.endswith("## 相关主题\n\n- [[星际想象]]：长时间尺度才看得见变化"))
        self.assertTrue(b.endswith("## 相关主题\n\n- [[耐心的复利]]：长时间尺度才看得见变化"))
        import vault_read  # noqa: E402
        vault = vault_read.read_vault(self.paths.root)
        rel = {t["name"]: t["related"] for t in vault["topics"]}
        self.assertEqual(rel["耐心的复利"], [{"topic": "星际想象", "why": "长时间尺度才看得见变化"}])
        self.assertEqual(rel["星际想象"], [{"topic": "耐心的复利", "why": "长时间尺度才看得见变化"}])
        import render  # noqa: E402
        data = render.build_page_data(vault)
        self.assertEqual(len(data["relations"]), 1)
        self.assertTrue(data["relations"][0]["cross"])
        self.assertEqual(data["relations"][0]["kind"], "concept")

    def test_topic_removed_clears_note(self):
        self.write_topics(self.good_topics())
        topics.run(self.paths, log=quiet)
        data = self.good_topics()
        data["topics"][0]["books"] = ["复利花园"]
        data["topics"][0]["viewpoints"][0]["books"] = []
        self.write_topics(data)
        topics.run(self.paths, log=quiet)
        fm = lib.read_frontmatter(self.note("复利花园（林一）"))
        self.assertNotIn("主题", fm)
        self.assertNotIn("领域", fm)
        self.assertFalse(lib.read_block(self.note("复利花园（林一）")).startswith(">"))

    def test_exclude_respected_when_picking(self):
        cfg = lib.load_config(self.dir)
        cfg["exclude"] = ["想法甲", "想法丙"]
        lib.save_config(self.dir, cfg)
        self.write_topics(self.good_topics())
        topics.run(self.paths, log=quiet)
        block = lib.read_block(self.read(self.paths.topic_card("耐心的复利")))
        self.assertNotIn("想法甲", block)


class ShareCheckTest(Base):
    def setUp(self):
        Base.setUp(self)
        books = lib.read_json(self.paths.books_json)
        b = books[0]
        b["orphanThoughts"] = [
            {"text": "今年工资涨了，存款终于到了 5 万", "quote": None},
            {"text": "和女朋友一起读的", "quote": None},
            {"text": "一个关于宇宙的普通感想", "quote": None},
            {"text": "联系我 13800001234", "quote": None},
            {"text": "我 28 岁那年第一次读", "quote": None},
        ]
        b["chapters"][0]["highlights"].append({"text": "书里说投资 100 万元需要耐心", "thought": None, "pos": 999})
        b["chapters"][0]["highlights"].append({"text": "作者邮箱 someone@example.com", "thought": None, "pos": 1000})
        lib.write_json(self.paths.books_json, books)

    def test_list_and_exclude(self):
        out = []
        share_check.run(self.paths, log=out.append)
        listed = [line for line in out if line.startswith("[")]
        joined = "\n".join(listed)
        self.assertIn("金额", joined)
        self.assertIn("收入与持仓", joined)
        self.assertIn("家人与伴侣", joined)
        self.assertIn("联系方式或证件号", joined)
        self.assertIn("带数字的个人经历", joined)
        self.assertNotIn("普通感想", joined)
        self.assertNotIn("100 万元", joined)  # highlights are only checked for contact/ID patterns
        self.assertIn("someone@example.com", joined)
        self.assertTrue(listed[0].startswith("[1] 《"))
        n = next(i for i, line in enumerate(listed, 1) if "女朋友" in line)
        share_check.run(self.paths, exclude_numbers=[n], log=quiet)
        self.assertEqual(lib.load_config(self.dir)["exclude"], ["和女朋友一起读的"])
        out = []
        share_check.run(self.paths, log=out.append)
        self.assertNotIn("女朋友", "\n".join(out))
        self.assertEqual(share_check.run(self.paths, exclude_numbers=[99], log=quiet), 1)

    def test_political_words_flag_thoughts_and_highlights(self):
        books = lib.read_json(self.paths.books_json)
        books[0]["orphanThoughts"].append({"text": "这一段让我想到审查制度", "quote": None})
        books[0]["chapters"][0]["highlights"].append({"text": "书里讲到文革时期的经历", "thought": None, "pos": 1001})
        books[0]["chapters"][0]["highlights"].append({"text": "地方政府的财政收入", "thought": None, "pos": 1002})
        lib.write_json(self.paths.books_json, books)
        out = []
        share_check.run(self.paths, log=out.append)
        joined = "\n".join(out)
        self.assertIn("政治敏感", joined)
        self.assertIn("审查制度", joined)
        self.assertIn("文革时期", joined)
        self.assertNotIn("地方政府的财政", joined)  # common words only count in the owner's own thoughts

    def test_topic_card_text_is_screened(self):
        data = self.good_topics()
        data["topics"][0]["oneLiner"] = "我月薪三万也攒不下钱"
        data["topics"][0]["viewpoints"][0]["text"] = "独裁者靠印钞维持统治。"
        data["topics"][0]["viewpoints"][1]["text"] = "工资和存款要分开管，自我约束比收入更重要。"
        lib.write_json(self.paths.topics_json, data)
        out = []
        share_check.run(self.paths, log=out.append)
        joined = "\n".join(out)
        self.assertIn("主题卡片里的文字", joined)
        self.assertIn("耐心的复利", joined)
        self.assertIn("月薪三万", joined)
        self.assertIn("独裁者", joined)
        self.assertNotIn("工资和存款", joined)  # books talk about money; only the owner's own life is flagged
        self.assertIn("topics.json", joined)


if __name__ == "__main__":
    unittest.main()
