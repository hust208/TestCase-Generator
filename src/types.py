"""
类型定义 - TestCase Generator 核心数据结构
"""

from typing import List, Dict, Optional, Any
from enum import Enum


class QuestionType(str, Enum):
    """题目类型"""
    FACT = "事实题"
    SUMMARY = "归纳题"
    DISTINCTION = "辨析题"
    NONEXISTENT = "不存在题"


class HallucinationType(str, Enum):
    """幻觉类型"""
    CONTRADICTION = "contradiction"    # 与原文矛盾
    FABRICATION = "fabrication"        # 无中生有（编造）
    OMISSION = "omission"              # 遗漏关键信息
    MISATTRIBUTION = "misattribution"  # 张冠李戴（归属错误)


class TestModule(str, Enum):
    """API测试模块"""
    DATASET = "dataset"
    COLLECTION = "collection"
    DATA = "data"
    TRAINING = "training"
    SEARCH = "search"
    CHAT = "chat"
    E2E = "e2e"
    PERFORMANCE = "performance"


class Priority(str, Enum):
    """优先级"""
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


# ---- 知识库评测相关 ----

class TestQuestion(Dict):
    """测试题目"""
    question: str
    ground_truth: str
    source_text: str
    question_type: str


class JudgeResult(Dict):
    """单维度评审结果"""
    dimension: str              # 评审维度名称
    score: float                # 0~1 分值
    rounds: List[float]         # 各轮评分（用于稳定性分析）
    avg_score: float            # 平均分
    std_dev: float              # 标准差（衡量一致性）
    comment: str                # 评审说明


class HallucinationDetail(Dict):
    """幻觉定位详情"""
    claim: str                  # 被质疑的具体陈述
    evidence: str               # 证据说明（为什么判定为幻觉）
    type: str                   # hallucination type


class EvalRecord(Dict):
    """单条评测记录"""
    question: str
    ground_truth: str
    kb_answer: str
    contexts: List[Any]
    judge_results: Dict[str, JudgeResult]  # 各维度评审结果
    hallucination_details: List[HallucinationDetail]
    overall_score: float
    passed: bool


class EvalSummary(Dict):
    """评测汇总"""
    total_sample: int
    pass_sample: int
    fail_sample: int
    overall_accuracy: float
    hallucination_rate: float
    avg_scores: Dict[str, float]
    detail_records: List[EvalRecord]


# ---- API 测试相关 ----

class ApiTestStep(Dict):
    """API测试步骤"""
    id: str
    name: str
    method: str                     # GET/POST/PUT/DELETE/WAIT/ASSERT
    endpoint: str
    body: Optional[Dict]
    queryParams: Optional[Dict]
    expectedStatus: Optional[int]
    assertions: List[Dict]
    extractVars: Optional[Dict]


class ApiTestCase(Dict):
    """API测试用例"""
    id: str
    name: str
    description: str
    module: str
    priority: str
    tags: List[str]
    precondition: Optional[str]
    enabled: bool
    steps: List[ApiTestStep]
    cleanup: Optional[List[ApiTestStep]]


class ApiTestResult(Dict):
    """API测试结果"""
    case_id: str
    case_name: str
    passed: bool
    step_results: List[Dict]
    error_message: Optional[str]
    duration_ms: float
