"""
公共工具函数 - LLM调用、Embedding、余弦相似度、JSON解析等
"""

import requests
import json
import numpy as np
import re
from typing import List, Dict, Any, Optional


def llm_request(
    prompt: str,
    api_url: str,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    timeout: int = 60,
    headers: Dict = None,
) -> str:
    """
    调用私有大模型通用函数
    支持多种 API 格式：/v1/completions, /v1/chat/completions
    """
    if headers is None:
        headers = {"Content-Type": "application/json"}

    # 自动适配 chat/completions 格式
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # 兼容多种返回格式
        if "choices" in data:
            choice = data["choices"][0]
            if "message" in choice:
                return choice["message"].get("content", "").strip()
            elif "text" in choice:
                return choice["text"].strip()
        if "response" in data:
            return data["response"].strip()
        if "result" in data:
            return data["result"].strip()

        return resp.text.strip()
    except requests.exceptions.Timeout:
        print(f"[WARN] LLM调用超时 (>{timeout}s)")
        return ""
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] LLM连接失败: {api_url}")
        return ""
    except Exception as e:
        print(f"[ERROR] LLM调用异常: {e}")
        return ""


def get_embedding(
    text: str,
    api_url: str,
    headers: Dict = None,
    timeout: int = 30,
) -> List[float]:
    """获取文本向量，用于去重和语义一致性校验"""
    if headers is None:
        headers = {"Content-Type": "application/json"}

    payload = {"input": text}

    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # 兼容多种返回格式
        if "data" in data and len(data["data"]) > 0:
            return data["data"][0].get("embedding", [])
        if "embedding" in data:
            return data["embedding"]
        if "result" in data:
            return data["result"]

        return []
    except Exception as e:
        print(f"[WARN] Embedding调用异常: {e}")
        return []


def cos_sim(vec1: List[float], vec2: List[float]) -> float:
    """余弦相似度计算"""
    v1, v2 = np.array(vec1), np.array(vec2)
    if len(v1) == 0 or len(v2) == 0:
        return 0.0
    dot = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))


def extract_json_from_text(text: str) -> Optional[Any]:
    """
    从 LLM 输出文本中提取 JSON，支持多种格式：
    - 纯 JSON 字符串
    - JSON 外包裹解释文字
    - 多行 JSON
    - JSON 数组
    """
    if not text:
        return None

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 对象
    try:
        # 找到第一个 { 和最后一个 } 的匹配
        start = text.find("{")
        if start != -1:
            # 从后往前找，确保括号匹配
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                if depth == 0:
                    return json.loads(text[start:i + 1])
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 数组
    try:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except json.JSONDecodeError:
        pass

    # 尝试修复常见的 JSON 格式问题
    try:
        # 移除 JSON 中的注释
        cleaned = re.sub(r"//.*?\n", "", text)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
        # 移除尾部逗号
        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    return None


def safe_json_loads(text: str, default: Any = None) -> Any:
    """安全的 JSON 解析，失败时返回默认值"""
    result = extract_json_from_text(text)
    if result is not None:
        return result
    return default


def compute_stats(scores: List[float]) -> Dict[str, float]:
    """计算统计指标：均值、标准差、最小值、最大值"""
    if not scores:
        return {"avg": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
    arr = np.array(scores)
    return {
        "avg": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }
