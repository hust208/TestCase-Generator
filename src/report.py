"""
HTML 报告生成器 - 自动生成可视化评测报告

报告内容：
- 📊 评测总览（准确率、幻觉率、样本数）
- 🎯 维度雷达图（正确性/忠实度/召回/精确率）
- 📋 合格/不合格样本明细表
- 🔍 幻觉定位详情
- 📈 多轮评审稳定性分析
"""

import json
from typing import Dict, Any
from datetime import datetime


def generate_html_report(eval_result: Dict, api_test_result: Dict = None) -> str:
    """
    生成 HTML 评测报告

    Args:
        eval_result: 评测汇总结果
        api_test_result: API 测试结果（可选）

    Returns:
        HTML 字符串
    """
    summary = eval_result.get("summary", eval_result)
    records = eval_result.get("detail_records", [])
    avg_scores = summary.get("avg_scores", {})

    # 计算通过/不通过列表
    passed_records = [r for r in records if r.get("passed")]
    failed_records = [r for r in records if not r.get("passed")]

    # 幻觉统计
    hallucination_records = [r for r in records if r.get("has_hallucination")]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>TestCase Generator 评测报告</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, 'Microsoft YaHei', sans-serif; background: #f5f6fa; color: #333; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
h1 { text-align: center; color: #2c3e50; font-size: 28px; margin: 20px 0; }
h2 { color: #34495e; font-size: 22px; margin: 15px 0; border-bottom: 2px solid #3498db; padding-bottom: 8px; }
.report-time { text-align: center; color: #7f8c8d; font-size: 14px; margin-bottom: 20px; }

/* 总览卡片 */
.overview-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }
.card { background: white; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.card-value { font-size: 32px; font-weight: bold; margin: 10px 0; }
.card-label { font-size: 14px; color: #7f8c8d; }
.card.green .card-value { color: #27ae60; }
.card.red .card-value { color: #e74c3c; }
.card.blue .card-value { color: #3498db; }
.card.orange .card-value { color: #f39c12; }

/* 维度评分 */
.dimension-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin: 20px 0; }
.dim-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.dim-name { font-size: 16px; color: #34495e; margin-bottom: 8px; }
.dim-score { font-size: 28px; font-weight: bold; }
.dim-bar { height: 8px; background: #ecf0f1; border-radius: 4px; margin-top: 10px; }
.dim-bar-fill { height: 100%; border-radius: 4px; }

/* 雷达图占位 */
.radar-section { background: white; border-radius: 12px; padding: 20px; margin: 20px 0; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }

/* 表格 */
table { width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
th { background: #34495e; color: white; padding: 12px 15px; text-align: left; font-size: 14px; }
td { padding: 12px 15px; border-bottom: 1px solid #ecf0f1; font-size: 13px; }
tr:hover { background: #f8f9fa; }
.tag { padding: 3px 8px; border-radius: 4px; font-size: 12px; display: inline-block; }
.tag-pass { background: #d4edda; color: #155724; }
.tag-fail { background: #f8d7da; color: #721c24; }
.tag-hallu { background: #fff3cd; color: #856404; }

/* 幻觉详情 */
.hallu-detail { background: #fff3cd; border-radius: 8px; padding: 12px; margin: 8px 0; }
.hallu-type { font-weight: bold; color: #856404; }
.hallu-claim { color: #e74c3c; }
.hallu-evidence { color: #27ae60; }

/* 稳定性分析 */
.stability-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 8px 0; }
.stability-item { background: #ecf0f1; padding: 8px; border-radius: 6px; text-align: center; }

/* API 测试 */
.api-section { background: white; border-radius: 12px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
</style>
</head>
<body>
<div class="container">
<h1>🧪 TestCase Generator 评测报告</h1>
<div class="report-time">生成时间: {now}</div>

<!-- 总览卡片 -->
<h2>📊 评测总览</h2>
<div class="overview-cards">
    <div class="card green">
        <div class="card-label">合格率</div>
        <div class="card-value">{summary.get('overall_accuracy', 0):.1%}</div>
    </div>
    <div class="card red">
        <div class="card-label">幻觉率</div>
        <div class="card-value">{summary.get('hallucination_rate', 0):.1%}</div>
    </div>
    <div class="card blue">
        <div class="card-label">总样本</div>
        <div class="card-value">{summary.get('total_sample', 0)}</div>
    </div>
    <div class="card orange">
        <div class="card-label">不合格</div>
        <div class="card-value">{summary.get('fail_sample', len(failed_records))}</div>
    </div>
</div>

<!-- 维度评分 -->
<h2>🎯 维度评分</h2>
<div class="dimension-grid">
    <div class="dim-card">
        <div class="dim-name">答案正确性</div>
        <div class="dim-score" style="color:#27ae60">{avg_scores.get('answer_correct', 0):.2f}</div>
        <div class="dim-bar"><div class="dim-bar-fill" style="width:{avg_scores.get('answer_correct', 0)*100}%; background:#27ae60"></div></div>
    </div>
    <div class="dim-card">
        <div class="dim-name">忠实度</div>
        <div class="dim-score" style="color:#3498db">{avg_scores.get('faithfulness', 0):.2f}</div>
        <div class="dim-bar"><div class="dim-bar-fill" style="width:{avg_scores.get('faithfulness', 0)*100}%; background:#3498db"></div></div>
    </div>
    <div class="dim-card">
        <div class="dim-name">检索召回率</div>
        <div class="dim-score" style="color:#f39c12">{avg_scores.get('context_recall', 0):.2f}</div>
        <div class="dim-bar"><div class="dim-bar-fill" style="width:{avg_scores.get('context_recall', 0)*100}%; background:#f39c12"></div></div>
    </div>
    <div class="dim-card">
        <div class="dim-name">检索精确率</div>
        <div class="dim-score" style="color:#9b59b6">{avg_scores.get('context_precision', 0):.2f}</div>
        <div class="dim-bar"><div class="dim-bar-fill" style="width:{avg_scores.get('context_precision', 0)*100}%; background:#9b59b6"></div></div>
    </div>
</div>

<!-- 雷达图 -->
<div class="radar-section">
<h3>综合维度雷达图</h3>
<p style="color:#7f8c8d">（建议使用浏览器渲染 canvas 或嵌入 ECharts 实现）</p>
<p>
正确性: {avg_scores.get('answer_correct', 0):.2f} | 
忠实度: {avg_scores.get('faithfulness', 0):.2f} | 
召回率: {avg_scores.get('context_recall', 0):.2f} | 
精确率: {avg_scores.get('context_precision', 0):.2f}
</p>
</div>

<!-- 不合格样本明细 -->
<h2>❌ 不合格样本明细</h2>
<table>
<tr><th>问题</th><th>综合分</th><th>正确性</th><th>忠实度</th><th>幻觉</th><th>状态</th></tr>
"""

    for r in failed_records[:20]:  # 最多显示20条
        correct = r.get("correctness", {}).get("avg_score", 0)
        faithful = r.get("faithfulness", {}).get("avg_score", 0)
        hallu_tag = '<span class="tag tag-hallu">幻觉</span>' if r.get("has_hallucination") else ""
        pass_tag = '<span class="tag tag-fail">不合格</span>'
        html += f"""
<tr>
<td>{r.get('question', '')[:60]}</td>
<td>{r.get('overall_score', 0):.2f}</td>
<td>{correct:.2f}</td>
<td>{faithful:.2f}</td>
<td>{hallu_tag}</td>
<td>{pass_tag}</td>
</tr>"""

    if not failed_records:
        html += '<tr><td colspan="6" style="text-align:center;color:#27ae60">🎉 全部合格！</td></tr>'

    html += "</table>"

    # 幻觉定位详情
    if hallucination_records:
        html += """
<h2>🔍 幻觉定位详情</h2>
<table>
<tr><th>问题</th><th>幻觉陈述</th><th>证据</th><th>类型</th></tr>
"""
        for r in hallucination_records[:10]:
            for detail in r.get("hallucination_details", []):
                html += f"""
<tr>
<td>{r.get('question', '')[:40]}</td>
<td class="hallu-claim">{detail.get('claim', '')}</td>
<td class="hallu-evidence">{detail.get('evidence', '')}</td>
<td class="hallu-type">{detail.get('type', '')}</td>
</tr>"""
        html += "</table>"

    # 合格样本
    html += """
<h2>✅ 合格样本</h2>
<table>
<tr><th>问题</th><th>综合分</th><th>正确性</th><th>忠实度</th><th>召回率</th><th>状态</th></tr>
"""
    for r in passed_records[:20]:
        correct = r.get("correctness", {}).get("avg_score", 0)
        faithful = r.get("faithfulness", {}).get("avg_score", 0)
        recall = r.get("context_recall", 0)
        html += f"""
<tr>
<td>{r.get('question', '')[:60]}</td>
<td>{r.get('overall_score', 0):.2f}</td>
<td>{correct:.2f}</td>
<td>{faithful:.2f}</td>
<td>{recall:.2f}</td>
<td><span class="tag tag-pass">合格</span></td>
</tr>"""
    html += "</table>"

    # API 测试结果（如果有）
    if api_test_result:
        api_results = api_test_result.get("results", [])
        html += """
<h2>🔌 API 测试结果</h2>
<div class="overview-cards">
    <div class="card green">
        <div class="card-label">API通过率</div>
        <div class="card-value">{:.1%}</div>
    </div>
    <div class="card blue">
        <div class="card-label">总用例数</div>
        <div class="card-value">{}</div>
    </div>
</div>
<table>
<tr><th>用例ID</th><th>名称</th><th>模块</th><th>通过步骤</th><th>状态</th></tr>
""".format(
            api_test_result.get("pass_rate", 0),
            api_test_result.get("total_cases", 0),
        )

        for r in api_results:
            status_tag = '<span class="tag tag-pass">通过</span>' if r.get("passed") else '<span class="tag tag-fail">失败</span>'
            html += f"""
<tr>
<td>{r.get('case_id', '')}</td>
<td>{r.get('case_name', '')}</td>
<td>{r.get('module', '')}</td>
<td>{r.get('passed_steps', 0)}/{r.get('total_steps', 0)}</td>
<td>{status_tag}</td>
</tr>"""
        html += "</table>"

    html += """
<div style="text-align:center;color:#7f8c8d;margin-top:30px;font-size:12px">
TestCase Generator v1.0 | Powered by 分维度独立评审引擎
</div>
</div>
</body>
</html>"""

    return html


def save_report(html_content: str, output_path: str = "eval_report.html"):
    """保存 HTML 报告到文件"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[报告] HTML 报告已保存至: {output_path}")
