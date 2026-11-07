import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import share_check  # noqa: E402


class ShareCheckRulesTest(unittest.TestCase):
    def test_age_and_body_numbers_are_flagged(self):
        for text in ["今年刚好21，还来得及", "我 25-26岁 才想明白", "这个月胖了 8.7KG", "计划瘦身 50 斤"]:
            self.assertIn("年龄与身体数字", share_check.flags(text, share_check.THOUGHT_CHECKS), text)

    def test_numbers_and_job_plans_without_keywords_are_flagged(self):
        cases = {"超重了五十斤": "年龄与身体数字", "BMI 刚好在30边缘": "年龄与身体数字",
                 "那年年入80，不算多": "收入与持仓", "想 gap 半年再找": "工作单位与同事",
                 "准备裸辞": "工作单位与同事"}
        for text, label in cases.items():
            self.assertIn(label, share_check.flags(text, share_check.THOUGHT_CHECKS), text)

    def test_topic_text_flags_only_own_life_with_numbers_or_politics(self):
        for text in ["我执是痛苦的根源：书里说放下我执", "30 岁以上的人更该存钱", "自我驯化：体制改变人"]:
            self.assertEqual(share_check.flags(text, share_check.TOPIC_CHECKS), [], text)
        for text in ["我月薪 3 万也存不下钱", "我月薪三万也攒不下钱", "我今年二十八岁"]:
            self.assertIn("第一人称的个人情况", share_check.flags(text, share_check.TOPIC_CHECKS), text)

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
