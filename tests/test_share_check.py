import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import share_check  # noqa: E402


class ShareCheckRulesTest(unittest.TestCase):
    def test_age_and_body_numbers_are_flagged(self):
        for text in ["今年刚好21，还来得及", "我 25-26岁 才想明白", "这个月胖了 8.7KG", "计划瘦身 50 斤"]:
            self.assertIn("年龄与身体数字", share_check.flags(text, share_check.THOUGHT_CHECKS), text)

    def test_trades_are_flagged(self):
        self.assertIn("收入与持仓", share_check.flags("那时候买入了医药", share_check.THOUGHT_CHECKS))

    def test_book_reflections_pass(self):
        self.assertEqual(share_check.flags("复利需要时间，耐心比聪明重要", share_check.THOUGHT_CHECKS), [])

    def test_own_uploads_are_listed(self):
        books = [
            {"bookId": "CB_1", "fileName": "草稿", "title": "The-Worker-Investor.zh-CN.2026-10-14", "author": "python-docx"},
            {"bookId": "CB_2", "fileName": "原则", "title": "原则", "author": "瑞·达利欧"},
            {"bookId": "123", "fileName": "活着", "title": "活着", "author": ""},
            {"bookId": "CB_3", "fileName": "已藏", "title": "x_20231017", "author": ""},
        ]
        found = share_check.own_uploads(books, {"已藏"})
        self.assertEqual([u["fileName"] for u in found], ["草稿"])


if __name__ == "__main__":
    unittest.main()
