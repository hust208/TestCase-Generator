"""
过滤引擎单元测试
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.filter import rule_filter, filter_questions


class TestRuleFilter(unittest.TestCase):
    """规则过滤测试"""

    def test_pass_valid_fact_question(self):
        """合格的事实题"""
        item = {
            "question": "智云科技成立于哪一年？",
            "ground_truth": "1992年",
            "source_text": "智云科技成立于1992年，是中国领先的智慧出行解决方案提供商。",
            "question_type": "事实题",
        }
        self.assertIsNone(rule_filter(item))

    def test_pass_valid_summary_question(self):
        """合格的归纳题"""
        item = {
            "question": "智云科技停车系统的主要特点有哪些？",
            "ground_truth": "支持多种支付方式，车牌识别率99.9%",
            "source_text": "系统支持微信支付、支付宝、无感支付等多种支付方式。车牌识别率高达99.9%。",
            "question_type": "归纳题",
        }
        self.assertIsNone(rule_filter(item))

    def test_pass_valid_nonexistent_question(self):
        """合格的不存在题"""
        item = {
            "question": "智云科技是否提供云计算服务器托管服务？",
            "ground_truth": "原文中未提及智云科技提供云计算服务器托管服务",
            "source_text": "智云科技主要提供智能停车管理系统、门禁系统。",
            "question_type": "不存在题",
        }
        self.assertIsNone(rule_filter(item))

    def test_reject_empty_fields(self):
        """空值字段"""
        item = {"question": "", "ground_truth": "答案", "source_text": "原文", "question_type": "事实题"}
        self.assertIsNotNone(rule_filter(item))

    def test_reject_short_question(self):
        """过短问题"""
        item = {"question": "啥", "ground_truth": "答案内容", "source_text": "原文内容很丰富", "question_type": "事实题"}
        self.assertIsNotNone(rule_filter(item))

    def test_reject_long_question(self):
        """过长问题"""
        long_q = "这是一个非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的问题超过120字?"
        item = {"question": long_q, "ground_truth": "答案", "source_text": "原文", "question_type": "事实题"}
        self.assertIsNotNone(rule_filter(item))

    def test_reject_short_answer(self):
        """过短答案"""
        item = {"question": "智云科技成立年份是什么？", "ground_truth": "1", "source_text": "原文内容", "question_type": "事实题"}
        self.assertIsNotNone(rule_filter(item))

    def test_reject_open_ended_question(self):
        """开放式主观提问"""
        item = {"question": "你觉得智云科技怎么样？", "ground_truth": "挺好的公司", "source_text": "智云科技成立于1992年", "question_type": "事实题"}
        self.assertIsNotNone(rule_filter(item))


class TestFilterPipeline(unittest.TestCase):
    """完整过滤流水线测试"""

    def test_filter_mixed_questions(self):
        """混合题目过滤"""
        questions = [
            {"question": "智云科技成立于哪一年？", "ground_truth": "1992年", "source_text": "智云科技成立于1992年。", "question_type": "事实题"},
            {"question": "啥", "ground_truth": "答案", "source_text": "原文", "question_type": "事实题"},  # 应被过滤
        ]
        result = filter_questions(questions, config={}, embedding_api_url="")
        # 过短题目应被过滤掉
        self.assertLessEqual(len(result), 1)
        if result:
            self.assertEqual(result[0]["question"], "智云科技成立于哪一年？")


if __name__ == "__main__":
    unittest.main()
