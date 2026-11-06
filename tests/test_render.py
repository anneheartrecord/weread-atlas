"""Tests for scripts/vault_read.py and scripts/render.py.

Run: python3 -m unittest tests/test_render.py -v
The fixture vault under tests/fixtures/vault/ is invented; no real reading data.
"""

import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import render  # noqa: E402
import vault_read  # noqa: E402

FIXTURE = HERE / "fixtures" / "vault" / "微信读书"
EXCLUDE = "私房菜馆"


def page_data(html):
    """The inlined JSON, parsed exactly as the browser would."""
    m = re.search(r'<script type="application/json" id="bk-data">(.*?)</script>', html, re.S)
    assert m, "data script missing"
    return json.loads(m.group(1)), m.group(1)


class RenderCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "微信读书"
        shutil.copytree(FIXTURE, self.root)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def render(self, *extra):
        out = self.tmp / "out.html"
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = render.main(["--root", str(self.root), "--out", str(out), *extra])
        self.assertEqual(code, 0)
        return out.read_text(encoding="utf-8"), buf.getvalue()


class TestThemes(RenderCase):
    def test_all_three_themes_render(self):
        for theme, attr in (("舆图", "yutu"), ("羊皮纸", "kami"), ("星空", "stars")):
            with self.subTest(theme=theme):
                html, summary = self.render("--theme", theme)
                self.assertIn(f'data-theme="{attr}"', html)
                self.assertIn(f"风格 {theme}", summary)
                self.assertNotIn("@@ATLAS_", html)
                self.assertIn("lxgw-wenkai-screen-webfont@1.7.0", html)
                data, _ = page_data(html)
                self.assertEqual(len(data["books"]), 12)

    def test_theme_defaults_to_config(self):
        cfg = self.root / ".atlas" / "config.json"
        c = json.loads(cfg.read_text(encoding="utf-8"))
        c["theme"] = "星空"
        cfg.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
        html, _ = self.render()
        self.assertIn('data-theme="stars"', html)

    def test_default_output_path(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(render.main(["--root", str(self.root)]), 0)
        self.assertTrue((self.root / "书房" / "index.html").exists())

    def test_only_allowed_external_requests(self):
        html, _ = self.render()
        urls = set(re.findall(r'(?:src|href)="(https?://[^"]+)"', html))
        self.assertEqual(urls, {"https://cdn.jsdelivr.net", "https://cdn.jsdelivr.net/npm/lxgw-wenkai-screen-webfont@1.7.0/lxgwwenkaigbscreen.css"})
        self.assertNotIn("<script src", html)


class TestData(RenderCase):
    def test_counts(self):
        html, summary = self.render()
        data, _ = page_data(html)
        self.assertEqual(len(data["books"]), 12)
        self.assertEqual(len(data["topics"]), 5)
        names = [d["name"] for d in data["domains"]]
        self.assertEqual(names[:3], ["投资与周期", "精力与习惯", "写作与表达"])
        self.assertEqual(names[-1], vault_read.UNSORTED)
        self.assertEqual(data["title"], "书房")
        self.assertEqual(len(data["stats"]["hourly"]), 24)
        self.assertIn("书 12 本｜主题 5 个｜领域 3 个", summary)

    def test_per_book_limits_and_card_text(self):
        data, _ = page_data(self.render()[0])
        for b in data["books"]:
            self.assertLessEqual(len(b["highlights"]), render.MAX_HIGHLIGHTS)
            self.assertLessEqual(len(b["thoughts"]), render.MAX_THOUGHTS)
            if b["thoughts"]:
                self.assertEqual(b["card"], b["thoughts"][0]["text"])
            elif b["highlights"]:
                self.assertEqual(b["card"], b["highlights"][0])
        slow = next(b for b in data["books"] if b["title"].startswith("慢钱"))
        self.assertEqual(len(slow["highlights"]), 10)  # 16 in the note

    def test_highlights_spread_across_book(self):
        items = list(range(40))
        picked = render.pick_spread(items, [1.0] * 40, 10)
        self.assertEqual(len(picked), 10)
        self.assertLess(picked[0], 4)
        self.assertGreaterEqual(picked[-1], 36)

    def test_cross_links(self):
        data, _ = page_data(self.render()[0])
        titles = [b["title"] for b in data["books"]]
        risk = next(t for t in data["topics"] if t["name"] == "风险与生存")
        self.assertEqual(len(risk["books"]), 4)
        self.assertTrue(all(0 <= i < len(titles) for i in risk["books"]))
        for t_idx, t in enumerate(data["topics"]):
            for bi in t["books"]:
                self.assertIn(t_idx, data["books"][bi]["topics"])
        compound = next(t for t in data["topics"] if t["name"] == "复利与耐心")
        off_shelf = [s for v in compound["viewpoints"] for s in v["books"] if s["idx"] is None]
        self.assertEqual([s["title"] for s in off_shelf], ["十年一刻"])
        unsorted = next(b for b in data["books"] if b["title"] == "旧城散记")
        self.assertEqual(unsorted["domains"], [vault_read.UNSORTED])

    def test_obsidian_block_lists_are_read(self):
        data, _ = page_data(self.render()[0])
        body = next(b for b in data["books"] if b["title"] == "醒来的身体")
        self.assertEqual(body["domains"], ["精力与习惯"])
        self.assertEqual(sorted(data["topics"][i]["name"] for i in body["topics"]), ["习惯的设计", "睡眠与精力"])

    def test_orphan_thought_keeps_its_quote(self):
        data, _ = page_data(self.render()[0])
        line = next(b for b in data["books"] if b["title"].startswith("一条线"))
        quotes = {t["text"]: t["quote"] for t in line["thoughts"]}
        self.assertEqual(quotes.get("删形容词这件事，比我想的难很多。"),
                         "初学者最常见的错误，是想在一篇文章里把知道的都写进去。")

    def test_several_thoughts_on_one_highlight(self):
        vault = vault_read.read_vault(self.root)
        slow = next(b for b in vault["books"] if b["file"] == "慢钱")
        multi = [h for c in slow["chapters"] for h in c["highlights"] if len(h["thoughts"]) > 1]
        self.assertEqual(len(multi), 1)
        self.assertEqual(len(multi[0]["thoughts"]), 2)
        data, _ = page_data(self.render()[0])
        page_slow = next(b for b in data["books"] if b["title"].startswith("慢钱"))
        quoted = [t for t in page_slow["thoughts"] if t["quote"] == multi[0]["text"]]
        self.assertEqual(len(quoted), 2)


class TestVaultIsTheSource(RenderCase):
    def test_exclude_fragments_removed(self):
        raw = "".join(p.read_text(encoding="utf-8") for p in self.root.rglob("*.md"))
        self.assertGreaterEqual(raw.count(EXCLUDE), 4)  # thought, highlight, orphan quote, topic card
        html, _ = self.render()
        self.assertNotIn(EXCLUDE, html)
        data, _ = page_data(html)
        body = next(b for b in data["books"] if b["title"] == "醒来的身体")
        # the thought survives, only the excluded quote under it is dropped
        runner = next(t for t in body["thoughts"] if t["text"] == "跑鞋放门口这个办法真的有效。")
        self.assertEqual(runner["quote"], "")

    def test_user_edit_in_one_liner_shows_up(self):
        card = self.root / "主题" / "清晰写作.md"
        text = card.read_text(encoding="utf-8")
        edited = "改过的结论：先想清楚，再动笔"
        card.write_text(text.replace("写不清楚是想不清楚，修改的本质是重新思考", edited), encoding="utf-8")
        data, _ = page_data(self.render()[0])
        topic = next(t for t in data["topics"] if t["name"] == "清晰写作")
        self.assertEqual(topic["oneLiner"], edited)

    def test_user_text_outside_block_is_not_rendered(self):
        html, _ = self.render()
        self.assertNotIn("我自己的批注", html)

    def test_malformed_note_skipped_with_warning(self):
        html, summary = self.render()
        self.assertIn("坏掉的笔记.md", summary)
        self.assertIn("已跳过", summary)
        data, _ = page_data(html)
        self.assertNotIn("坏掉的笔记", [b["title"] for b in data["books"]])

    def test_odd_notes_never_crash(self):
        (self.root / "书" / "空白.md").write_text("", encoding="utf-8")
        (self.root / "书" / "乱码.md").write_bytes(b"\xff\xfe\x00bad")
        (self.root / "书" / "没有标记.md").write_text("---\n书名: 没有标记\n时长: 很久\n---\n- 一条划线\n  - 💭 一条想法\n", encoding="utf-8")
        (self.root / "主题" / "残缺.md").write_text("---\n主题: 残缺\n---\n随便写的\n", encoding="utf-8")
        html, summary = self.render()
        data, _ = page_data(html)
        titles = [b["title"] for b in data["books"]]
        self.assertIn("没有标记", titles)
        self.assertNotIn("空白", titles)
        self.assertIn("乱码.md", summary)
        self.assertIn("时长 不是数字", summary)
        nomark = data["books"][titles.index("没有标记")]
        self.assertEqual(nomark["highlights"], ["一条划线"])

    def test_missing_stats_still_renders(self):
        (self.root / ".atlas" / "stats.json").unlink()
        html, summary = self.render()
        data, _ = page_data(html)
        self.assertIsNone(data["stats"])
        self.assertIn("stats.json 不存在", summary)


class TestEscaping(RenderCase):
    def test_script_tag_in_highlight_cannot_break_out(self):
        html, _ = self.render()
        data, raw = page_data(html)
        self.assertNotIn("</", raw)
        self.assertNotIn("<!--", raw)
        fog = next(b for b in data["books"] if b["title"] == "雾中航行")
        self.assertTrue(any("</script><script>alert('书脉')</script>" in h for h in fog["highlights"]))
        # exactly one closing tag for the data script and one for the code
        self.assertEqual(html.count("</script>"), 2)

    def test_title_is_html_escaped(self):
        cfg = self.root / ".atlas" / "config.json"
        c = json.loads(cfg.read_text(encoding="utf-8"))
        c["title"] = "<b>书房</b>"
        cfg.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
        html, _ = self.render()
        self.assertIn("<title>&lt;b&gt;书房&lt;/b&gt;</title>", html)

    def test_placeholder_text_in_data_is_left_alone(self):
        note = self.root / "书" / "旧城散记.md"
        note.write_text(note.read_text(encoding="utf-8").replace("<!-- weread-atlas:end -->", "- @@ATLAS_CSS@@ 和 /*@@ATLAS_JS@@*/\n<!-- weread-atlas:end -->"), encoding="utf-8")
        html, _ = self.render()
        data, _ = page_data(html)
        old = next(b for b in data["books"] if b["title"] == "旧城散记")
        self.assertTrue(any("@@ATLAS_CSS@@" in h for h in old["highlights"]))


class TestFrontmatterReading(unittest.TestCase):
    def test_sources(self):
        body, src = vault_read.split_source("一句话 —— [[书A]] · 《书B》 · [[书C|别名]]")
        self.assertEqual(body, "一句话")
        self.assertEqual([(s["title"], s["linked"]) for s in src], [("书A", True), ("书B", False), ("书C", True)])

    def test_topic_block(self):
        block = (
            "## 一句话结论\n\n结论\n\n## 核心观点\n\n1. **甲**：说明。 —— [[书A]]\n2. 乙：没有加粗 —— 《书B》\n\n"
            "## 我的想法\n\n- 想法 —— [[书A]]\n  > 原句\n\n## 代表划线\n\n- 划线 —— [[书B]]\n"
        )
        t = vault_read.parse_topic_block(block)
        self.assertEqual(t["oneLiner"], "结论")
        self.assertEqual([(v["claim"], v["text"]) for v in t["viewpoints"]], [("甲", "说明。"), ("乙", "没有加粗")])
        self.assertEqual(t["thoughts"], [{"text": "想法", "quote": "原句", "book": "书A"}])
        self.assertEqual(t["highlights"], [{"text": "划线", "book": "书B"}])


if __name__ == "__main__":
    unittest.main()
