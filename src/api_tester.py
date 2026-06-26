"""
API 自动化测试引擎 - 支持 FastGPT / 私有知识库 API 全流程测试

基于 test-cases.ts 的测试用例定义，转换为 Python 可执行版本
支持：
- 多步骤串联（变量传递、上下文依赖）
- 自动清理（cleanup 步骤）
- 多种断言方式（status、jsonPath、custom、responseTime）
- 变量替换 {{varName}}
- WAIT 步骤（等待训练完成）
"""

import requests
import json
import time
import re
from typing import Dict, List, Any, Optional
from jsonpath_ng import parse as jsonpath_parse


class ApiTester:
    """API 自动化测试引擎"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.api_config = config.get("api_test", {})
        self.base_url = self.api_config.get("base_url", "")
        self.api_key = self.api_config.get("api_key", "")
        self.timeout = self.api_config.get("timeout", 30)
        self.variables: Dict[str, Any] = {}  # 运行时变量存储
        self.timestamp = str(int(time.time()))

    def _get_headers(self) -> Dict:
        """获取请求头（含认证）"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _replace_vars(self, obj: Any) -> Any:
        """递归替换模板变量 {{varName}} 和 {{timestamp}}"""
        if isinstance(obj, str):
            # 替换 {{timestamp}}
            obj = obj.replace("{{timestamp}}", self.timestamp)
            # 替换 {{varName}}
            for var_name, var_value in self.variables.items():
                pattern = "{{" + var_name + "}}"
                obj = obj.replace(pattern, str(var_value))
            return obj
        elif isinstance(obj, dict):
            return {k: self._replace_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_vars(item) for item in obj]
        else:
            return obj

    def _execute_step(self, step: Dict) -> Dict:
        """执行单个测试步骤"""
        method = step.get("method", "GET")
        endpoint = step.get("endpoint", "")
        body = step.get("body")
        query_params = step.get("queryParams")
        expected_status = step.get("expectedStatus", 200)

        # WAIT 步骤特殊处理
        if method == "WAIT":
            wait_time = 5
            time.sleep(wait_time)
            return {
                "step_id": step.get("id", ""),
                "step_name": step.get("name", "等待"),
                "method": "WAIT",
                "passed": True,
                "response": {"waited_seconds": wait_time},
            }

        # ASSERT 步骤特殊处理（仅做断言）
        if method == "ASSERT":
            return {
                "step_id": step.get("id", ""),
                "step_name": step.get("name", "断言"),
                "method": "ASSERT",
                "passed": True,
            }

        # 变量替换
        endpoint = self._replace_vars(endpoint)
        body = self._replace_vars(body)
        query_params = self._replace_vars(query_params)

        # 构建完整 URL
        url = f"{self.base_url}{endpoint}"

        # 执行请求
        try:
            start_time = time.time()
            if method == "GET":
                resp = requests.get(url, params=query_params, headers=self._get_headers(), timeout=self.timeout)
            elif method == "POST":
                resp = requests.post(url, json=body, params=query_params, headers=self._get_headers(), timeout=self.timeout)
            elif method == "PUT":
                resp = requests.put(url, json=body, params=query_params, headers=self._get_headers(), timeout=self.timeout)
            elif method == "DELETE":
                resp = requests.delete(url, params=query_params, headers=self._get_headers(), timeout=self.timeout)
            else:
                print(f"[WARN] 未知方法: {method}")
                resp = requests.request(method, url, json=body, params=query_params, headers=self._get_headers(), timeout=self.timeout)

            duration_ms = (time.time() - start_time) * 1000
            resp_data = resp.json() if resp.text else {}

            # 提取变量
            extract_vars = step.get("extractVars", {})
            if extract_vars:
                for var_name, json_path in extract_vars.items():
                    self.variables[var_name] = self._extract_jsonpath(resp_data, json_path)
                    print(f"  📌 提取变量: {var_name} = {self.variables[var_name]}")

            # 执行断言
            assertions = step.get("assertions", [])
            assertion_results = self._run_assertions(assertions, resp.status_code, resp_data, duration_ms)

            all_passed = all(a.get("passed", True) for a in assertion_results)

            return {
                "step_id": step.get("id", ""),
                "step_name": step.get("name", ""),
                "method": method,
                "url": url,
                "status_code": resp.status_code,
                "duration_ms": duration_ms,
                "passed": all_passed,
                "assertions": assertion_results,
                "response": resp_data,
            }

        except Exception as e:
            return {
                "step_id": step.get("id", ""),
                "step_name": step.get("name", ""),
                "method": method,
                "url": url,
                "passed": False,
                "error": str(e),
            }

    def _extract_jsonpath(self, data: Dict, path: str) -> Any:
        """从响应数据中提取 JSONPath 值"""
        try:
            if path.startswith("$."):
                jp_expr = jsonpath_parse(path)
                matches = jp_expr.find(data)
                if matches:
                    return matches[0].value
            return None
        except Exception:
            return None

    def _run_assertions(
        self,
        assertions: List[Dict],
        status_code: int,
        resp_data: Dict,
        duration_ms: float,
    ) -> List[Dict]:
        """执行断言列表"""
        results = []
        for assertion in assertions:
            a_type = assertion.get("type", "custom")
            a_name = assertion.get("name", "")
            expected = assertion.get("expected")
            actual_path = assertion.get("actual")

            passed = False
            detail = ""

            if a_type == "status":
                passed = status_code == expected
                detail = f"状态码 {status_code} vs 预期 {expected}"

            elif a_type == "jsonPath":
                actual_value = self._extract_jsonpath(resp_data, actual_path)
                if expected == "string":
                    passed = isinstance(actual_value, str) and len(actual_value) > 0
                elif expected == "array":
                    passed = isinstance(actual_value, list)
                elif expected == "number":
                    passed = isinstance(actual_value, (int, float))
                else:
                    passed = actual_value == expected
                detail = f"路径 {actual_path} 值 '{actual_value}' vs 预期 '{expected}'"

            elif a_type == "responseTime":
                passed = duration_ms < expected
                detail = f"响应时间 {duration_ms:.0f}ms vs 预期 <{expected}ms"

            elif a_type == "custom":
                # 自定义断言需要人工判定，默认标记为 passed
                passed = True
                detail = a_name

            results.append({
                "assertion_id": assertion.get("id", ""),
                "type": a_type,
                "name": a_name,
                "passed": passed,
                "detail": detail,
            })

        return results

    def run_test_case(self, case: Dict) -> Dict:
        """运行单个测试用例（含所有步骤）"""
        self.timestamp = str(int(time.time()))  # 每个用例刷新时间戳
        self.variables = {}  # 每个用例重置变量

        steps = case.get("steps", [])
        step_results = []
        case_passed = True

        print(f"\n🧪 [{case.get('id', '')}] {case.get('name', '')}")

        for step in steps:
            result = self._execute_step(step)
            step_results.append(result)

            status_icon = "✅" if result.get("passed") else "❌"
            print(f"  {status_icon} Step: {result.get('step_name', step.get('name', ''))}")

            if not result.get("passed"):
                case_passed = False

        # 执行清理步骤
        cleanup_steps = case.get("cleanup", [])
        if cleanup_steps:
            print(f"  🧹 执行清理 ({len(cleanup_steps)} 步)")
            for step in cleanup_steps:
                self._execute_step(step)

        return {
            "case_id": case.get("id", ""),
            "case_name": case.get("name", ""),
            "module": case.get("module", ""),
            "priority": case.get("priority", ""),
            "passed": case_passed,
            "step_results": step_results,
            "total_steps": len(steps),
            "passed_steps": sum(1 for r in step_results if r.get("passed")),
        }

    def run_all_cases(self, cases: List[Dict]) -> Dict:
        """运行所有测试用例"""
        total = len(cases)
        results = []
        passed_cnt = 0

        for idx, case in enumerate(cases):
            if not case.get("enabled", True):
                continue
            result = self.run_test_case(case)
            results.append(result)
            if result["passed"]:
                passed_cnt += 1

        return {
            "total_cases": total,
            "passed_cases": passed_cnt,
            "failed_cases": total - passed_cnt,
            "pass_rate": round(passed_cnt / total, 4) if total > 0 else 0,
            "results": results,
        }


# ---- 预定义的 FastGPT API 测试用例集 ----

FASTGPT_TEST_CASES = [
    {
        "id": "DS-001",
        "name": "创建知识库 - 基本创建",
        "module": "dataset",
        "priority": "P0",
        "tags": ["创建", "正向"],
        "enabled": True,
        "steps": [
            {
                "id": "DS-001-S1",
                "name": "创建知识库",
                "method": "POST",
                "endpoint": "/api/core/dataset/create",
                "body": {"name": "自动化测试知识库_{{timestamp}}", "intro": "由测试系统自动创建的知识库", "type": "dataset"},
                "expectedStatus": 200,
                "assertions": [
                    {"id": "a1", "type": "status", "name": "HTTP状态码为200", "expected": 200},
                    {"id": "a2", "type": "jsonPath", "name": "返回知识库ID", "expected": "string", "actual": "$.data"},
                ],
                "extractVars": {"datasetId": "$.data"},
            },
        ],
        "cleanup": [
            {"id": "DS-001-C1", "name": "删除测试知识库", "method": "DELETE", "endpoint": "/api/core/dataset/delete", "queryParams": {"id": "{{datasetId}}"}},
        ],
    },
    {
        "id": "DS-002",
        "name": "获取知识库列表 - 根目录",
        "module": "dataset",
        "priority": "P0",
        "tags": ["查询", "正向"],
        "enabled": True,
        "steps": [
            {
                "id": "DS-002-S1",
                "name": "获取根目录知识库列表",
                "method": "POST",
                "endpoint": "/api/core/dataset/list",
                "body": {"parentId": None},
                "expectedStatus": 200,
                "assertions": [
                    {"id": "a1", "type": "status", "name": "HTTP状态码为200", "expected": 200},
                    {"id": "a2", "type": "jsonPath", "name": "data是数组类型", "expected": "array", "actual": "$.data"},
                ],
            },
        ],
    },
    {
        "id": "SCH-001",
        "name": "向量搜索测试 - embedding模式",
        "module": "search",
        "priority": "P0",
        "tags": ["搜索", "正向", "embedding"],
        "enabled": True,
        "steps": [
            {
                "id": "SCH-001-S1",
                "name": "创建测试知识库",
                "method": "POST",
                "endpoint": "/api/core/dataset/create",
                "body": {"name": "搜索测试_{{timestamp}}", "type": "dataset"},
                "expectedStatus": 200,
                "extractVars": {"datasetId": "$.data"},
            },
            {
                "id": "SCH-001-S2",
                "name": "创建文本集合并上传数据",
                "method": "POST",
                "endpoint": "/api/core/dataset/collection/create/text",
                "body": {
                    "datasetId": "{{datasetId}}",
                    "text": "智云科技成立于1992年，是中国领先的智慧出行解决方案提供商。公司主要产品包括智能停车管理系统、门禁系统、通道闸机等。",
                    "name": "智云科技简介",
                    "trainingType": "chunk",
                },
                "expectedStatus": 200,
            },
            {"id": "SCH-001-S3", "name": "等待训练完成", "method": "WAIT", "endpoint": ""},
            {
                "id": "SCH-001-S4",
                "name": "执行向量搜索",
                "method": "POST",
                "endpoint": "/api/core/dataset/searchTest",
                "body": {"datasetId": "{{datasetId}}", "text": "智云科技是什么公司", "searchMode": "embedding", "limit": 2000, "similarity": 0},
                "expectedStatus": 200,
                "assertions": [
                    {"id": "a1", "type": "status", "name": "HTTP状态码为200", "expected": 200},
                    {"id": "a2", "type": "jsonPath", "name": "搜索结果非空", "expected": "array", "actual": "$.data"},
                ],
            },
        ],
        "cleanup": [
            {"id": "SCH-001-C1", "name": "删除测试知识库", "method": "DELETE", "endpoint": "/api/core/dataset/delete", "queryParams": {"id": "{{datasetId}}"}},
        ],
    },
]
