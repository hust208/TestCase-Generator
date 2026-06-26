"""
双层过滤引擎 - 规则过滤 + Embedding 语义去重

规则过滤层：
  1. 长度过滤（问题 8~120字，答案 ≥ 5字）
  2. 答案溯源性验证（ground_truth 必须在 source_text 中）
  3. 问题质量检查（是否有唯一确定答案）
  4. 不存在题特殊处理

语义去重层：
  5. Embedding 余弦相似度去重（阈值可配）
  6. 语义一致性校验（问题与原文是否语义相关）
"""

from typing import List, Dict, Optional
from .utils import get_embedding, cos_sim


def rule_filter(item: Dict, config: Dict = None) -> Optional[str]:
    """
    规则层过滤，返回拒绝原因（None表示通过）
    """
    if config is None:
        config = {}

    min_q_len = config.get("min_question_length", 8)
    max_q_len = config.get("max_question_length", 120)
    min_a_len = config.get("min_answer_length", 5)

    q = item.get("question", "")
    gt = item.get("ground_truth", "")
    src = item.get("source_text", "")
    q_type = item.get("question_type", "事实题")

    # 1. 空值检查
    if not q or not gt or not src:
        return "空值字段"

    # 2. 长度过滤
    if len(q) < min_q_len:
        return f"问题过短({len(q)}<{min_q_len})"
    if len(q) > max_q_len:
        return f"问题过长({len(q)}>{max_q_len})"
    if len(gt) < min_a_len:
        return f"答案过短({len(gt)}<{min_a_len})"

    # 3. 答案溯源性验证
    if q_type != "不存在题":
        if gt not in src and src not in gt:
            # 允许 gt 是 src 的子串或 src 是 gt 的子串（归纳题可能扩展）
            # 更宽松的检查：gt 的关键词片段是否在 src 中
            # 中文分词：按2~4字滑动窗口提取关键短语
            gt_clean = gt.replace("，", "").replace("、", "").replace("。", "").replace("？", "").replace("！", "")
            src_clean = src.replace("，", "").replace("、", "").replace("。", "").replace("？", "").replace("！", "")
            # 提取2~4字关键片段
            key_phrases = set()
            for w_len in [2, 3, 4]:
                for i in range(len(gt_clean) - w_len + 1):
                    key_phrases.add(gt_clean[i:i+w_len])
            # 过滤掉太通用的片段
            generic = {"是的", "的有", "可以", "能够", "包括", "提供", "支持", "主要", "特点", "哪些"}
            key_phrases = {p for p in key_phrases if p not in generic and len(p.strip()) >= 2}
            if key_phrases:
                overlap = sum(1 for kw in key_phrases if kw in src_clean)
                overlap_rate = overlap / len(key_phrases)
                if overlap_rate < 0.3:
                    return f"答案溯源性不足(关键词重叠率{overlap_rate:.0%})"

    # 4. 不存在题特殊处理
    if q_type == "不存在题":
        # 不存在题的 ground_truth 应标注"原文中未提及"类表述
        if "未提及" not in gt and "不存在" not in gt and "没有" not in gt and "原文中未" not in gt:
            return f"不存在题答案表述不规范: '{gt}'"

    # 5. 问题质量检查
    # 禁止开放式主观提问
    open_markers = ["你觉得", "你认为", "你怎么看", "大家觉得", "随便说"]
    for marker in open_markers:
        if marker in q:
            return f"开放式主观提问(含'{marker}')"

    # 禁止过于模糊的问题
    vague_markers = ["什么意思", "怎么样", "好不好"]
    if len(q) < 20 and any(m in q for m in vague_markers):
        return f"问题过于模糊"

    return None  # 通过


def semantic_dedup(
    questions: List[Dict],
    sim_threshold: float = 0.9,
    embedding_api_url: str = "",
) -> List[Dict]:
    """
    语义去重层：基于 Embedding 余弦相似度
    O(n²) 相似度比对，但 n 通常较小（每chunk几题）
    """
    if not embedding_api_url:
        print("[WARN] 无 Embedding API，跳过语义去重")
        return questions

    kept = []
    question_vecs = []

    for item in questions:
        q = item.get("question", "")
        q_vec = get_embedding(q, api_url=embedding_api_url)

        if not q_vec:
            # Embedding 失败时保留题目（不因接口问题丢弃）
            kept.append(item)
            continue

        is_dup = False
        for v in question_vecs:
            sim = cos_sim(q_vec, v)
            if sim > sim_threshold:
                is_dup = True
                print(f"[去重] 丢弃重复题: '{q[:30]}...' (相似度={sim:.3f})")
                break

        if not is_dup:
            question_vecs.append(q_vec)
            kept.append(item)

    return kept


def semantic_relevance_check(
    questions: List[Dict],
    embedding_api_url: str = "",
    min_relevance: float = 0.3,
) -> List[Dict]:
    """
    语义相关性检查：问题与原文的语义相似度
    过滤掉与原文无关的问题（防止 LLM 跑题）
    """
    if not embedding_api_url:
        return questions

    kept = []
    for item in questions:
        q = item.get("question", "")
        src = item.get("source_text", "")
        q_vec = get_embedding(q, api_url=embedding_api_url)
        src_vec = get_embedding(src[:200], api_url=embedding_api_url)  # 截取避免过长

        if q_vec and src_vec:
            sim = cos_sim(q_vec, src_vec)
            if sim < min_relevance:
                print(f"[相关性] 丢弃跑题: '{q[:30]}...' (与原文相似度={sim:.3f})")
                continue

        kept.append(item)

    return kept


def filter_questions(
    raw_questions: List[Dict],
    config: Dict = None,
    embedding_api_url: str = "",
) -> List[Dict]:
    """
    主入口：双层过滤

    流程：
    1. 规则过滤（快速、确定性）
    2. 语义去重（需要 Embedding API）
    3. 语义相关性检查（需要 Embedding API）
    """
    if config is None:
        config = {}

    filter_config = config.get("filter", {})
    sim_threshold = config.get("evaluation", {}).get("sim_dup_threshold", 0.9)

    # 第一层：规则过滤
    passed_rule = []
    rejected_rule = []
    for item in raw_questions:
        reason = rule_filter(item, filter_config)
        if reason:
            rejected_rule.append((item, reason))
            print(f"[规则过滤] 丢弃: '{item.get('question', '')[:30]}...' 原因: {reason}")
        else:
            passed_rule.append(item)

    print(f"\n[过滤] 规则层: {len(raw_questions)} → {len(passed_rule)} (丢弃{len(rejected_rule)})")

    # 第二层：语义去重
    deduped = semantic_dedup(passed_rule, sim_threshold, embedding_api_url)
    print(f"[过滤] 去重层: {len(passed_rule)} → {len(deduped)} (去重{len(passed_rule)-len(deduped)})")

    # 第三层：语义相关性检查
    relevant = semantic_relevance_check(deduped, embedding_api_url)
    print(f"[过滤] 相关性层: {len(deduped)} → {len(relevant)} (跑题{len(deduped)-len(relevant)})")

    return relevant
