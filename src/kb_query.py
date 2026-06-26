"""
知识库问答接口 - 调用私有知识库 API
"""

import requests
from typing import Dict, Any


def query_knowledge_base(
    question: str,
    config: Dict = None,
) -> Dict[str, Any]:
    """
    调用知识库问答接口

    Args:
        question: 用户问题
        config: 配置字典（含 kb_api 配置）

    Returns:
        {"answer": str, "contexts": list}
    """
    if config is None:
        config = {}

    kb_config = config.get("kb_api", {})
    url = kb_config.get("url", "")
    top_k = kb_config.get("top_k", 3)
    timeout = kb_config.get("timeout", 45)
    headers = kb_config.get("headers", {"Content-Type": "application/json"})

    if not url:
        print("[ERROR] 未配置知识库 API 地址")
        return {"answer": "", "contexts": []}

    payload = {"query": question, "top_k": top_k}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # 兼容多种返回格式
        answer = ""
        contexts = []

        if isinstance(data, dict):
            answer = data.get("answer", data.get("response", data.get("result", "")))
            contexts = data.get("contexts", data.get("context", data.get("sources", [])))
            if isinstance(contexts, str):
                contexts = [contexts]
        elif isinstance(data, str):
            answer = data

        return {"answer": answer, "contexts": contexts}

    except requests.exceptions.Timeout:
        print(f"[WARN] 知识库查询超时 (>{timeout}s): {question[:30]}")
        return {"answer": "", "contexts": []}
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] 知识库连接失败: {url}")
        return {"answer": "", "contexts": []}
    except Exception as e:
        print(f"[ERROR] 知识库接口异常: {e}")
        return {"answer": "", "contexts": []}
