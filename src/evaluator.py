"""
分维度独立评审引擎 - TestCase Generator 最核心最复杂的模块

核心改进（相比原始 kb_auto_evaluate.py）：
1. 分维度独立评审：正确性、忠实度、幻觉、检索召回、检索精确率 各自独立 prompt
2. 多轮评审取均值：支持 N 次评审，消除 LLM-as-Judge 单次偏差
3. 幻觉定位：不仅判定是否幻觉，还能定位幻觉片段并给出证据
4. Few-shot 校准：为每个维度提供评分锚点参考
5. 检索质量可量化：用 Embedding 语义比对计算 context_recall/precision

架构：
  ┌──────────────────────────────────────────────────────┐
  │  evaluate_single()                                     │
  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
  │  │ judge_correct │  │judge_faithful│  │judge_hallucin │ │
  │  │  ×N轮取均值   │  │  ×N轮取均值   │  │  ×N轮+定位    │ │
  │  └──────────────┘  └──────────────┘  └──────────────┘ │
  │  ┌──────────────┐  ┌──────────────┐                   │
  │  │calc_recall   │  │calc_precision│                   │
  │  │Embedding比对 │  │Embedding比对 │                   │
  │  └──────────────┘  └──────────────┘                   │
  └──────────────────────────────────────────────────────┘
"""

from typing import List, Dict, Any, Optional
from .utils import (
    llm_request, get_embedding, cos_sim,
    safe_json_loads, compute_stats,
)


# ---- Few-shot 校准样例（评分锚点） ----

CORRECT_FEWSHOT = """
评分锚点参考：
- 1.0分：答案与标准答案完全一致，无任何遗漏
- 0.8分：答案核心内容正确，但遗漏次要细节或表述略有不同
- 0.5分：答案部分正确，但缺少关键信息或存在小偏差
- 0.2分：答案仅有一小部分正确，大部分偏离标准答案
- 0.0分：答案完全错误或与标准答案无关
"""

FAITHFUL_FEWSHOT = """
评分锚点参考：
- 1.0分：回答100%来自检索上下文，无任何外部信息
- 0.8分：回答主要来自上下文，有少量合理推理（非编造）
- 0.5分：回答约一半来自上下文，另一半是通用知识
- 0.2分：回答大部分来自外部知识，与上下文关联很少
- 0.0分：回答完全来自外部知识，与检索上下文无关
"""

HALLUCINATION_FEWSHOT = """
评分锚点参考：
- 0.0分（无幻觉）：回答全部基于检索上下文，无任何编造
- 0.3分（轻微幻觉）：有1处小偏差，可能是合理推理而非故意编造
- 0.5分（中度幻觉）：有1~2处明显编造信息，但核心内容仍正确
- 0.8分（重度幻觉）：多处编造，核心内容偏离上下文
- 1.0分（完全幻觉）：回答完全编造，与上下文完全无关

幻觉类型定义：
- contradiction: 与原文矛盾（原文说A，回答说B）
- fabrication: 无中生有（原文中完全没有的内容）
- omission: 遗漏关键信息（导致回答不准确）
- misattribution: 张冠李戴（把A的特征说成B的）
"""


# ---- 分维度独立评审函数 ----

def judge_correctness(
    question: str,
    kb_answer: str,
    ground_truth: str,
    source_text: str,
    llm_url: str = "",
    temperature: float = 0.1,
) -> Dict:
    """
    维度1：答案正确性评审
    仅评判 kb_answer 与 ground_truth 的匹配程度
    """
    prompt = f"""
你是答案正确性评审专家。仅评判知识库回答与标准答案的匹配程度，不考虑其他因素。

评审规则：仅比较【知识库回答】与【标准答案】的内容匹配度。

问题：{question}
标准答案：{ground_truth}
出题原文依据：{source_text}
知识库回答：{kb_answer}

{CORRECT_FEWSHOT}

输出严格JSON：
{{"score": 0~1, "comment": "简短扣分原因"}}
"""
    raw = llm_request(prompt, api_url=llm_url, temperature=temperature)
    result = safe_json_loads(raw, default={"score": 0, "comment": "评审解析失败"})
    return {
        "score": float(result.get("score", 0)),
        "comment": result.get("comment", ""),
    }


def judge_faithfulness(
    kb_answer: str,
    contexts: List[Any],
    llm_url: str = "",
    temperature: float = 0.1,
) -> Dict:
    """
    维度2：忠实度评审
    仅评判 kb_answer 是否忠实于检索上下文（不编造外部信息）
    """
    ctx_str = "\n".join([str(c) for c in contexts]) if contexts else "(无检索上下文)"

    prompt = f"""
你是忠实度评审专家。仅评判知识库回答是否忠实于检索上下文，不使用任何外部知识。

评审规则：逐句检查【知识库回答】中的每个陈述，判定是否能在【检索上下文】中找到依据。

检索上下文：
{ctx_str}

知识库回答：
{kb_answer}

{FAITHFUL_FEWSHOT}

输出严格JSON：
{{"score": 0~1, "comment": "简短扣分原因，列出不忠实的具体陈述"}}
"""
    raw = llm_request(prompt, api_url=llm_url, temperature=temperature)
    result = safe_json_loads(raw, default={"score": 0, "comment": "评审解析失败"})
    return {
        "score": float(result.get("score", 0)),
        "comment": result.get("comment", ""),
    }


def judge_hallucination(
    kb_answer: str,
    contexts: List[Any],
    question: str,
    ground_truth: str,
    llm_url: str = "",
    temperature: float = 0.1,
) -> Dict:
    """
    维度3：幻觉检测 + 定位
    不仅判定是否幻觉，还定位幻觉片段并给出证据
    """
    ctx_str = "\n".join([str(c) for c in contexts]) if contexts else "(无检索上下文)"

    prompt = f"""
你是幻觉检测专家。逐句检查知识库回答中是否存在幻觉（编造、矛盾、遗漏）。

评审规则：将知识库回答拆分为独立陈述，逐条对照检索上下文验证。

问题：{question}
标准答案：{ground_truth}
检索上下文：
{ctx_str}

知识库回答：
{kb_answer}

{HALLUCINATION_FEWSHOT}

输出严格JSON：
{{"score": 0~1, "has_hallucination": true/false, "hallucination_details": [
  {{\"claim\": \"被质疑的具体陈述\", \"evidence\": \"为什么判定为幻觉（与上下文的对比）\", \"type\": \"contradiction/fabrication/omission/misattribution\"}}
], "comment": "简短总结"}}
"""
    raw = llm_request(prompt, api_url=llm_url, temperature=temperature)
    result = safe_json_loads(raw, default={
        "score": 1.0,
        "has_hallucination": True,
        "hallucination_details": [],
        "comment": "评审解析失败，默认判定为幻觉",
    })

    # 确保 hallucination_details 是列表
    details = result.get("hallucination_details", [])
    if isinstance(details, dict):
        details = [details]
    if not isinstance(details, list):
        details = []

    return {
        "score": float(result.get("score", 1.0)),
        "has_hallucination": bool(result.get("has_hallucination", True)),
        "hallucination_details": details,
        "comment": result.get("comment", ""),
    }


# ---- 检索质量量化计算（基于 Embedding） ----

def calc_context_recall(
    ground_truth: str,
    source_text: str,
    contexts: List[Any],
    embedding_api_url: str = "",
) -> float:
    """
    维度4：检索召回率
    衡量：标准答案/原文的关键信息是否被检索上下文覆盖
    """
    if not embedding_api_url or not contexts:
        return 0.0

    gt_vec = get_embedding(ground_truth, api_url=embedding_api_url)
    if not gt_vec:
        return 0.0

    # 计算标准答案与每条检索上下文的相似度，取最高值
    max_sim = 0.0
    for ctx in contexts:
        ctx_text = str(ctx)[:200]  # 截取避免过长
        ctx_vec = get_embedding(ctx_text, api_url=embedding_api_url)
        if ctx_vec:
            sim = cos_sim(gt_vec, ctx_vec)
            max_sim = max(max_sim, sim)

    return max_sim


def calc_context_precision(
    contexts: List[Any],
    source_text: str,
    question: str,
    embedding_api_url: str = "",
) -> float:
    """
    维度5：检索精确率
    衡量：检索上下文中与问题/原文相关的内容占比
    """
    if not embedding_api_url or not contexts:
        return 0.0

    q_vec = get_embedding(question, api_url=embedding_api_url)
    if not q_vec:
        return 0.0

    # 计算每条上下文与问题的相似度
    relevant_count = 0
    threshold = 0.5  # 相关性阈值

    for ctx in contexts:
        ctx_text = str(ctx)[:200]
        ctx_vec = get_embedding(ctx_text, api_url=embedding_api_url)
        if ctx_vec:
            sim = cos_sim(q_vec, ctx_vec)
            if sim >= threshold:
                relevant_count += 1

    precision = relevant_count / len(contexts) if contexts else 0.0
    return precision


# ---- 多轮评审 + 汇总 ----

def multi_round_judge(
    judge_func,
    rounds: int = 3,
    **kwargs,
) -> Dict:
    """
    多轮评审取均值，提升稳定性
    返回：{avg_score, std_dev, rounds_scores, comment}
    """
    scores = []
    comments = []

    for i in range(rounds):
        result = judge_func(**kwargs)
        scores.append(result.get("score", 0))
        comments.append(result.get("comment", ""))
        if i < rounds - 1:
            # 小幅变化 temperature 以增加多样性
            kwargs["temperature"] = kwargs.get("temperature", 0.1) + 0.05 * (i + 1)

    stats = compute_stats(scores)

    # 选取最详细的 comment（通常是非最高分的那个）
    best_comment = max(comments, key=len) if comments else ""

    return {
        "avg_score": stats["avg"],
        "std_dev": stats["std"],
        "rounds_scores": scores,
        "comment": best_comment,
    }


# ---- 主入口：完整评测一条记录 ----

def evaluate_single(
    question: str,
    kb_answer: str,
    contexts: List[Any],
    ground_truth: str,
    source_text: str,
    config: Dict = None,
) -> Dict:
    """
    主入口：对单条问答记录执行完整分维度评审

    Returns:
        {
            "correctness": {avg_score, std_dev, rounds_scores, comment},
            "faithfulness": {avg_score, std_dev, rounds_scores, comment},
            "hallucination": {avg_score, has_hallucination, hallucination_details, ...},
            "context_recall": float,
            "context_precision": float,
            "overall_score": float,   # 加权综合分
            "passed": bool,
        }
    """
    if config is None:
        config = {}

    llm_url = config.get("llm_api", {}).get("url", "")
    embedding_url = config.get("embedding_api", {}).get("url", "")
    judge_rounds = config.get("evaluation", {}).get("judge_rounds", 3)
    min_score = config.get("evaluation", {}).get("min_answer_score", 0.8)
    default_temp = config.get("llm_api", {}).get("temperature", 0.1)

    # 维度1：正确性（多轮评审）
    correct_result = multi_round_judge(
        judge_correctness,
        question=question,
        kb_answer=kb_answer,
        ground_truth=ground_truth,
        source_text=source_text,
        llm_url=llm_url,
        temperature=default_temp,
        rounds=judge_rounds,
    )

    # 维度2：忠实度（多轮评审）
    faithful_result = multi_round_judge(
        judge_faithfulness,
        kb_answer=kb_answer,
        contexts=contexts,
        llm_url=llm_url,
        temperature=default_temp,
        rounds=judge_rounds,
    )

    # 维度3：幻觉检测（多轮评审 + 定位）
    hallucination_result = multi_round_judge(
        judge_hallucination,
        kb_answer=kb_answer,
        contexts=contexts,
        question=question,
        ground_truth=ground_truth,
        llm_url=llm_url,
        temperature=default_temp,
        rounds=judge_rounds,
    )

    # 取最后一轮的幻觉定位详情（最完整的）
    last_hallu_detail = judge_hallucination(
        kb_answer=kb_answer,
        contexts=contexts,
        question=question,
        ground_truth=ground_truth,
        llm_url=llm_url,
        temperature=default_temp,
    )
    hallucination_details = last_hallu_detail.get("hallucination_details", [])
    has_hallucination = last_hallu_detail.get("has_hallucination", True)

    # 维度4：检索召回率（Embedding 计算）
    context_recall = calc_context_recall(
        ground_truth=ground_truth,
        source_text=source_text,
        contexts=contexts,
        embedding_api_url=embedding_url,
    )

    # 维度5：检索精确率（Embedding 计算）
    context_precision = calc_context_precision(
        contexts=contexts,
        source_text=source_text,
        question=question,
        embedding_api_url=embedding_url,
    )

    # 加权综合分：正确性40% + 忠实度25% + (1-幻觉分)20% + 召回10% + 精确5%
    overall_score = (
        correct_result["avg_score"] * 0.40
        + faithful_result["avg_score"] * 0.25
        + (1.0 - hallucination_result["avg_score"]) * 0.20
        + context_recall * 0.10
        + context_precision * 0.05
    )

    passed = overall_score >= min_score and not has_hallucination

    return {
        "question": question,
        "ground_truth": ground_truth,
        "kb_answer": kb_answer,
        "contexts": contexts,
        "correctness": correct_result,
        "faithfulness": faithful_result,
        "hallucination": hallucination_result,
        "has_hallucination": has_hallucination,
        "hallucination_details": hallucination_details,
        "context_recall": context_recall,
        "context_precision": context_precision,
        "overall_score": round(overall_score, 4),
        "passed": passed,
    }


def evaluate_batch(
    test_set: List[Dict],
    kb_query_func,  # 知识库查询函数
    config: Dict = None,
) -> Dict:
    """
    批量评测完整测试集

    Args:
        test_set: 测试题目列表
        kb_query_func: 知识库查询函数 (question) → {answer, contexts}
        config: 配置字典

    Returns:
        评测汇总结果
    """
    total = len(test_set)
    records = []
    bad_samples = []
    pass_cnt = 0
    hallu_cnt = 0

    for idx, item in enumerate(test_set):
        print(f"\n{'='*50}")
        print(f"[评测] {idx+1}/{total} | 问题: {item['question'][:40]}...")

        # 查询知识库
        kb_ret = kb_query_func(item["question"])

        # 分维度评审
        record = evaluate_single(
            question=item["question"],
            kb_answer=kb_ret.get("answer", ""),
            contexts=kb_ret.get("contexts", []),
            ground_truth=item["ground_truth"],
            source_text=item["source_text"],
            config=config,
        )

        records.append(record)

        if record["passed"]:
            pass_cnt += 1
            print(f"  ✅ 通过 (综合分={record['overall_score']:.2f})")
        else:
            bad_samples.append(record)
            reason = "幻觉" if record["has_hallucination"] else f"低分({record['overall_score']:.2f})"
            print(f"  ❌ 不合格 ({reason})")

        if record["has_hallucination"]:
            hallu_cnt += 1
            for detail in record["hallucination_details"]:
                print(f"  🔍 幻觉: {detail.get('claim', '?')} [{detail.get('type', '?')}]")

    accuracy = pass_cnt / total if total > 0 else 0
    hallucination_rate = hallu_cnt / total if total > 0 else 0

    # 维度平均分汇总
    avg_scores = {
        "answer_correct": sum(r["correctness"]["avg_score"] for r in records) / total if total else 0,
        "faithfulness": sum(r["faithfulness"]["avg_score"] for r in records) / total if total else 0,
        "context_recall": sum(r["context_recall"] for r in records) / total if total else 0,
        "context_precision": sum(r["context_precision"] for r in records) / total if total else 0,
    }

    summary = {
        "total_sample": total,
        "pass_sample": pass_cnt,
        "fail_sample": total - pass_cnt,
        "overall_accuracy": round(accuracy, 4),
        "hallucination_rate": round(hallucination_rate, 4),
        "avg_scores": avg_scores,
        "detail_records": records,
    }

    return summary, bad_samples
