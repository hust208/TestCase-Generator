"""
智能出题引擎 - 基于知识库文本切片自动生成高质量测试题

改进点：
1. 分题型出题 prompt，每种题型独立生成，避免题型配比偏差
2. 增加 few-shot 参考样例，提升出题质量
3. 支持"不存在题"专项生成（测试知识库对超范围问题的拒绝能力）
4. 输出解析容错增强
"""

from typing import List, Dict, Optional
from .utils import llm_request, safe_json_loads


# ---- Few-shot 参考样例（每种题型） ----

FACT_EXAMPLE = """
样例1:
原文："智云科技成立于1992年，是中国领先的智慧出行解决方案提供商。"
题目："智云科技成立于哪一年？"
标准答案："1992年"
→ 输出: {"question": "智云科技成立于哪一年？", "ground_truth": "1992年", "source_text": "智云科技成立于1992年，是中国领先的智慧出行解决方案提供商。", "question_type": "事实题"}
"""

SUMMARY_EXAMPLE = """
样例1:
原文："系统支持微信支付、支付宝、无感支付、ETC支付、现金等多种支付方式。车牌识别率高达99.9%。在全国设有100多个分支机构。"
题目："智云科技系统的主要特点有哪些？"
标准答案："支持多种支付方式（微信、支付宝、无感支付、ETC支付、现金），车牌识别率达99.9%，在全国设有100多个分支机构"
→ 输出: {"question": "智云科技系统的主要特点有哪些？", "ground_truth": "支持多种支付方式（微信、支付宝、无感支付、ETC支付、现金），车牌识别率达99.9%，在全国设有100多个分支机构", "source_text": "系统支持微信支付...", "question_type": "归纳题"}
"""

DISTINCTION_EXAMPLE = """
样例1:
原文："chunk模式是自动文本分割训练，适合长文档；qa模式是问答对提取训练，适合FAQ类内容。"
题目："chunk模式和qa模式在训练方式上有什么区别？"
标准答案："chunk模式是自动文本分割训练，适合长文档；qa模式是问答对提取训练，适合FAQ类内容"
→ 输出: {"question": "chunk模式和qa模式在训练方式上有什么区别？", "ground_truth": "chunk模式是自动文本分割训练，适合长文档；qa模式是问答对提取训练，适合FAQ类内容", "source_text": "...", "question_type": "辨析题"}
"""

NONEXISTENT_EXAMPLE = """
样例1:
原文："智云科技主要提供智能停车管理系统、门禁系统、通道管理系统等。"
题目："智云科技是否提供云计算服务器托管服务？"（原文中未提及此服务）
标准答案："原文中未提及智云科技提供云计算服务器托管服务"
→ 输出: {"question": "智云科技是否提供云计算服务器托管服务？", "ground_truth": "原文中未提及", "source_text": "智云科技主要提供智能停车管理系统...", "question_type": "不存在题"}
"""


def generate_questions_for_type(
    chunk_text: str,
    question_type: str,
    num_q: int = 1,
    example: str = "",
    llm_url: str = "",
    temperature: float = 0.1,
) -> List[Dict]:
    """为特定题型生成题目（分题型独立 prompt）"""

    type_desc = {
        "事实题": "从原文中提取一个具体事实（如数字、名称、时间等）作为答案",
        "归纳题": "将原文中多个相关信息归纳总结为一个完整答案",
        "辨析题": "对比原文中两个或多个概念/方案的区别",
        "不存在题": "故意提出一个原文中未涉及的问题，测试知识库的拒绝能力",
    }

    prompt = f"""
你是知识库命题专家，严格只基于下面原文出题，禁止使用外部知识。

原文内容：
{chunk_text}

本次出题类型：{question_type}
出题要求：{type_desc.get(question_type, "")}

通用规则：
1. ground_truth必须完全来自原文，不能编造、不能引申
2. 问题必须有唯一确定答案，禁止开放式主观提问
3. 问题长度在8~120字之间，答案长度不少于5字
4. 生成{num_q}道题目

参考样例：
{example}

输出仅JSON数组，格式：
[
{{"question": "xxx", "ground_truth": "xxx", "source_text": "对应原文片段", "question_type": "{question_type}"}}
]
"""
    raw = llm_request(prompt, api_url=llm_url, temperature=temperature)
    result = safe_json_loads(raw, default=[])

    if isinstance(result, dict):
        # 如果返回单个对象而非数组，包装为数组
        result = [result]

    # 标准化字段
    for item in result:
        item.setdefault("question_type", question_type)
        if "source_text" not in item:
            item["source_text"] = chunk_text[:200]

    return result


def generate_test_questions(
    chunk_text: str,
    num_q: int = 2,
    type_weights: Dict[str, float] = None,
    llm_url: str = "",
    temperature: float = 0.1,
) -> List[Dict]:
    """
    主入口：基于文本切片批量生成测试题
    按题型配比分别生成，避免单次 LLM 出题的题型偏差

    Args:
        chunk_text: 知识库文本切片
        num_q: 总题目数
        type_weights: 题型配比权重，默认 {事实题:0.4, 归纳题:0.3, 辨析题:0.2, 不存在题:0.1}
        llm_url: LLM API 地址
        temperature: 生成温度

    Returns:
        测试题目列表
    """
    if type_weights is None:
        type_weights = {"事实题": 0.4, "归纳题": 0.3, "辨析题": 0.2, "不存在题": 0.1}

    examples = {
        "事实题": FACT_EXAMPLE,
        "归纳题": SUMMARY_EXAMPLE,
        "辨析题": DISTINCTION_EXAMPLE,
        "不存在题": NONEXISTENT_EXAMPLE,
    }

    all_questions = []

    for q_type, weight in type_weights.items():
        # 按权重计算该题型数量
        count = max(1, round(num_q * weight))
        questions = generate_questions_for_type(
            chunk_text=chunk_text,
            question_type=q_type,
            num_q=count,
            example=examples.get(q_type, ""),
            llm_url=llm_url,
            temperature=temperature,
        )
        all_questions.extend(questions)

    print(f"[出题] 生成 {len(all_questions)} 题目 "
          f"(事实{sum(1 for q in all_questions if q.get('question_type')=='事实题')}, "
          f"归纳{sum(1 for q in all_questions if q.get('question_type')=='归纳题')}, "
          f"辨析{sum(1 for q in all_questions if q.get('question_type')=='辨析题')}, "
          f"不存在{sum(1 for q in all_questions if q.get('question_type')=='不存在题')})")

    return all_questions


def generate_from_chunks(
    chunks: List[str],
    num_q_per_chunk: int = 2,
    type_weights: Dict[str, float] = None,
    llm_url: str = "",
    temperature: float = 0.1,
) -> List[Dict]:
    """批量：遍历多个 chunk 生成题目"""
    all_q = []
    for idx, chunk in enumerate(chunks):
        print(f"\n[出题] 处理 chunk {idx+1}/{len(chunks)}...")
        questions = generate_test_questions(
            chunk_text=chunk,
            num_q=num_q_per_chunk,
            type_weights=type_weights,
            llm_url=llm_url,
            temperature=temperature,
        )
        all_q.extend(questions)
    return all_q
