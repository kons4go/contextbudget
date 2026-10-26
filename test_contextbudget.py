"""contextbudget —— 自检测试。

按片段统计上下文的 token 占用，标出超预算的部分与可裁剪的低价值片段。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import contextbudget  # noqa: E402


class TestContextBudget(unittest.TestCase):
    def setUp(self):
        self.text = ("# 系统提示\n你是助手。\n\n"
                     "# 历史记录\n" + ("用户问了一句话。\n" * 200) + "\n"
                     "# 参考资料\n" + ("参考资料的一行内容。\n" * 300))

    def test_segments_are_attributed(self):
        r = contextbudget.analyze(self.text, 100000)
        self.assertGreater(len(r["segments"]), 2)
        titles = [s["title"] for s in r["segments"]]
        self.assertIn("历史记录", titles)
        self.assertIn("参考资料", titles)

    def test_over_budget_is_flagged(self):
        r = contextbudget.analyze(self.text, 100)
        self.assertTrue(r["over_budget"])
        self.assertGreater(r["overage"], 0)

    def test_under_budget(self):
        r = contextbudget.analyze(self.text, 10_000_000)
        self.assertFalse(r["over_budget"])

    def test_rank_by_size(self):
        r = contextbudget.analyze(self.text, 100000)
        ranked = r["ranked_by_size"]
        self.assertGreaterEqual(ranked[0]["tokens"], ranked[-1]["tokens"])

    def test_empty_text(self):
        r = contextbudget.analyze("", 100)
        self.assertEqual(r["total_tokens"], 0)
        self.assertFalse(r["over_budget"])
