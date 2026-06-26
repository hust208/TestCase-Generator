"""
评审引擎单元测试

注意：评审引擎的核心函数依赖 LLM API，在无 API 时只能测试非 API 部分
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.evaluator import (
    evaluate_single,
    calc_context_recall,
    calc_context_precision,
    multi_round_judge,
    judge_correctness,
    judge_hallucination,
)
from src.utils import compute_stats


class TestComputeStats(unittest.TestCase):
    """统计计算测试"""

    def test_stats_normal(self):
        """正常分数统计"""
        stats = compute_stats([0.8, 0.9, 0.7])
        self.assertAlmostEqual(stats["avg"], 0.8, places=2)
        self.assertGreater(stats["std"], 0)
        self.assertEqual(stats["min"], 0.7)
        self.assertEqual(stats["max"], 0.9)

    def test_stats_empty(self):
        """空列表统计"""
        stats = compute_stats([])
        self.assertEqual(stats["avg"], 0.0)

    def test_stats_single(self):
        """单个分数统计"""
        stats = compute_stats([0.5])
        self.assertEqual(stats["avg"], 0.5)
        self.assertEqual(stats["std"], 0.0)


class TestMultiRoundJudge(unittest.TestCase):
    """多轮评审测试"""

    def test_multi_round_without_api(self):
        """无 API 时多轮评审（应返回默认值）"""
        result = multi_round_judge(
            judge_correctness,
            rounds=2,
            question="测试问题",
            kb_answer="测试答案",
            ground_truth="标准答案",
            source_text="原文",
            llm_url="",  # 无 API
        )
        # 无 API 时各轮返回 0 分
        self.assertIsInstance(result["rounds_scores"], list)
        self.assertEqual(len(result["rounds_scores"]), 2)


class TestEvaluateSingle(unittest.TestCase):
    """单条评测测试"""

    def test_evaluate_without_api(self):
        """无 API 时完整评测流程"""
        config = {
            "llm_api": {"url": ""},
            "embedding_api": {"url": ""},
            "evaluation": {"judge_rounds": 1, "min_answer_score": 0.8},
        }
        result = evaluate_single(
            question="智云科技成立于哪一年？",
            kb_answer="1992年",
            contexts=["智云科技成立于1992年。"],
            ground_truth="1992年",
            source_text="智云科技成立于1992年。",
            config=config,
        )
        self.assertIn("correctness", result)
        self.assertIn("faithfulness", result)
        self.assertIn("hallucination", result)
        self.assertIn("overall_score", result)
        self.assertIn("passed", result)
        self.assertIn("context_recall", result)
        self.assertIn("context_precision", result)


class TestContextMetrics(unittest.TestCase):
    """检索质量指标测试"""

    def test_recall_without_embedding(self):
        """无 Embedding API 时召回率为0"""
        recall = calc_context_recall(
            ground_truth="1992年",
            source_text="智云科技成立于1992年",
            contexts=["智云科技成立于1992年。"],
            embedding_api_url="",
        )
        self.assertEqual(recall, 0.0)

    def test_precision_without_embedding(self):
        """无 Embedding API 时精确率为0"""
        precision = calc_context_precision(
            contexts=["智云科技成立于1992年。"],
            source_text="智云科技成立于1992年",
            question="智云科技成立于哪一年？",
            embedding_api_url="",
        )
        self.assertEqual(precision, 0.0)


class TestHallucinationDetection(unittest.TestCase):
    """幻觉检测测试"""

    def test_hallucination_structure(self):
        """幻觉检测结果结构验证"""
        result = judge_hallucination(
            kb_answer="智云科技成立于1998年",
            contexts=["智云科技成立于1992年"],
            question="智云科技成立年份",
            ground_truth="1992年",
            llm_url="",  # 无 API
        )
        self.assertIn("score", result)
        self.assertIn("has_hallucination", result)
        self.assertIn("hallucination_details", result)
        self.assertIn("comment", result)
        self.assertIsInstance(result["hallucination_details"], list)


if __name__ == "__main__":
    unittest.main()
