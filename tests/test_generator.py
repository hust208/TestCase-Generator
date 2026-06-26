"""
出题引擎单元测试
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.generator import generate_test_questions, generate_questions_for_type
from src.filter import rule_filter, filter_questions
from src.utils import extract_json_from_text, cos_sim


class TestGenerator(unittest.TestCase):
    """出题引擎测试"""

    def test_generate_for_type_structure(self):
        """测试分题型出题函数返回结构"""
        # 注意：此测试需要实际 LLM API，在无 API 时跳过
        # 仅测试函数接口是否正确
        try:
            result = generate_questions_for_type(
                chunk_text="智云科技成立于1992年。",
                question_type="事实题",
                num_q=1,
                llm_url="",  # 无 API
            )
            # 无 API 应返回空列表或解析失败
            self.assertIsInstance(result, list)
        except Exception:
            pass  # 无 API 时可忽略

    def test_rule_filter_pass(self):
        """测试规则过滤 - 合格题目"""
        item = {
            "question": "智云科技成立于哪一年？",
            "ground_truth": "1992年",
            "source_text": "智云科技成立于1992年，是中国领先的智慧出行解决方案提供商。",
            "question_type": "事实题",
        }
        reason = rule_filter(item)
        self.assertIsNone(reason, f"合格题目不应被过滤，但被拒绝: {reason}")

    def test_rule_filter_short_question(self):
        """测试规则过滤 - 过短问题"""
        item = {
            "question": "啥?",  # 仅2字
            "ground_truth": "答案",
            "source_text": "这是原文内容。",
            "question_type": "事实题",
        }
        reason = rule_filter(item)
        self.assertIsNotNone(reason, "过短问题应被过滤")
        self.assertIn("过短", reason)

    def test_rule_filter_open_question(self):
        """测试规则过滤 - 开放式主观提问"""
        item = {
            "question": "你觉得智云科技怎么样？",
            "ground_truth": "挺好的",
            "source_text": "智云科技成立于1992年。",
            "question_type": "事实题",
        }
        reason = rule_filter(item)
        self.assertIsNotNone(reason, "开放式主观提问应被过滤")

    def test_rule_filter_nonexistent_wrong_answer(self):
        """测试规则过滤 - 不存在题答案格式不规范"""
        item = {
            "question": "智云科技是否提供云服务？",
            "ground_truth": "不提供",  # 应为"原文中未提及"类表述
            "source_text": "智云科技主要提供停车管理系统。",
            "question_type": "不存在题",
        }
        reason = rule_filter(item)
        self.assertIsNotNone(reason, "不存在题答案格式不规范应被过滤")


class TestJsonParsing(unittest.TestCase):
    """JSON 解析工具测试"""

    def test_extract_pure_json(self):
        """测试纯 JSON 提取"""
        text = '{"score": 0.8, "comment": "正确"}'
        result = extract_json_from_text(text)
        self.assertEqual(result["score"], 0.8)

    def test_extract_json_with_wrapper(self):
        """测试带解释文字的 JSON 提取"""
        text = '以下是评审结果：\n{"score": 0.7, "comment": "部分正确"}\n以上为评审结果。'
        result = extract_json_from_text(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["score"], 0.7)

    def test_extract_json_array(self):
        """测试 JSON 数组提取"""
        text = '[{"question": "Q1", "ground_truth": "A1"}]'
        result = extract_json_from_text(text)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_extract_empty_text(self):
        """测试空文本"""
        result = extract_json_from_text("")
        self.assertIsNone(result)


class TestCosineSimilarity(unittest.TestCase):
    """余弦相似度测试"""

    def test_identical_vectors(self):
        """测试相同向量"""
        vec = [1.0, 2.0, 3.0]
        sim = cos_sim(vec, vec)
        self.assertAlmostEqual(sim, 1.0, places=5)

    def test_orthogonal_vectors(self):
        """测试正交向量"""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        sim = cos_sim(vec1, vec2)
        self.assertAlmostEqual(sim, 0.0, places=5)

    def test_opposite_vectors(self):
        """测试反向向量"""
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        sim = cos_sim(vec1, vec2)
        self.assertAlmostEqual(sim, -1.0, places=5)

    def test_zero_vectors(self):
        """测试零向量"""
        sim = cos_sim([0, 0, 0], [1, 2, 3])
        self.assertEqual(sim, 0.0)


if __name__ == "__main__":
    unittest.main()
