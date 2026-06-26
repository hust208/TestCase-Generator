"""
TestCase Generator - 主入口

运行模式：
  --mode eval       : 全流程评测（出题→过滤→问答→评审→报告）
  --mode generate   : 仅出题
  --mode judge      : 仅评审（已有测试集）
  --mode report     : 仅生成HTML报告
  --mode api-test   : API自动化测试
"""

import argparse
import json
import sys
import os

# 添加 src 目录到搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.config_loader import load_config, get_config_value
from src.generator import generate_test_questions, generate_from_chunks
from src.filter import filter_questions
from src.evaluator import evaluate_batch
from src.kb_query import query_knowledge_base
from src.api_tester import ApiTester, FASTGPT_TEST_CASES
from src.report import generate_html_report, save_report


def run_full_eval(config: Dict, chunks: List[str] = None, test_set_path: str = None):
    """全流程评测：出题→过滤→问答→评审→报告"""
    output_config = config.get("output", {})
    llm_url = get_config_value(config, "llm_api.url", "")
    embedding_url = get_config_value(config, "embedding_api.url", "")

    # 1. 获取测试集
    if test_set_path and os.path.exists(test_set_path):
        print(f"\n[加载] 使用已有测试集: {test_set_path}")
        with open(test_set_path, "r", encoding="utf-8") as f:
            test_set = json.load(f)
    elif chunks:
        print(f"\n[出题] 从 {len(chunks)} 个切片生成测试题...")
        raw_questions = generate_from_chunks(
            chunks=chunks,
            num_q_per_chunk=get_config_value(config, "generation.num_questions_per_chunk", 2),
            type_weights=get_config_value(config, "generation.question_types"),
            llm_url=llm_url,
        )
        test_set = filter_questions(raw_questions, config, embedding_url)
        # 保存测试集
        test_set_file = output_config.get("test_set_path", "test_set.json")
        with open(test_set_file, "w", encoding="utf-8") as f:
            json.dump(test_set, f, ensure_ascii=False, indent=2)
        print(f"[保存] 有效测试题 {len(test_set)} 条 → {test_set_file}")
    else:
        print("[ERROR] 需要提供 --input（测试集或文本切片）")
        return

    if not test_set:
        print("[ERROR] 无有效测试题，评测终止")
        return

    # 2. 执行评测
    print(f"\n{'='*60}")
    print(f"[评测] 开始评测 {len(test_set)} 条测试题...")
    print(f"{'='*60}")

    eval_result, bad_samples = evaluate_batch(
        test_set=test_set,
        kb_query_func=lambda q: query_knowledge_base(q, config),
        config=config,
    )

    # 3. 保存结果
    result_file = output_config.get("result_path", "eval_result.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(eval_result, f, ensure_ascii=False, indent=2)
    print(f"\n[保存] 评测结果 → {result_file}")

    bad_file = output_config.get("bad_sample_path", "bad_samples.json")
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(bad_samples, f, ensure_ascii=False, indent=2)
    print(f"[保存] 不合格样本 → {bad_file}")

    # 4. 生成报告
    html = generate_html_report(eval_result)
    report_file = output_config.get("report_path", "eval_report.html")
    save_report(html, report_file)

    # 5. 打印汇总
    print(f"\n{'='*60}")
    print(f"📊 评测汇总")
    print(f"{'='*60}")
    print(f"总样本数:     {eval_result['total_sample']}")
    print(f"合格样本:     {eval_result['pass_sample']}")
    print(f"不合格样本:   {eval_result['fail_sample']}")
    print(f"整体准确率:   {eval_result['overall_accuracy']:.2%}")
    print(f"幻觉发生率:   {eval_result['hallucination_rate']:.2%}")
    avg = eval_result.get("avg_scores", {})
    print(f"维度平均分:")
    print(f"  答案正确性: {avg.get('answer_correct', 0):.2f}")
    print(f"  忠实度:     {avg.get('faithfulness', 0):.2f}")
    print(f"  检索召回率: {avg.get('context_recall', 0):.2f}")
    print(f"  检索精确率: {avg.get('context_precision', 0):.2f}")


def run_generate_only(config: Dict, chunks: List[str], output_path: str = None):
    """仅出题模式"""
    llm_url = get_config_value(config, "llm_api.url", "")
    embedding_url = get_config_value(config, "embedding_api.url", "")

    raw_questions = generate_from_chunks(
        chunks=chunks,
        num_q_per_chunk=get_config_value(config, "generation.num_questions_per_chunk", 2),
        type_weights=get_config_value(config, "generation.question_types"),
        llm_url=llm_url,
    )
    test_set = filter_questions(raw_questions, config, embedding_url)

    out_file = output_path or config.get("output", {}).get("test_set_path", "test_set.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(test_set, f, ensure_ascii=False, indent=2)
    print(f"\n[完成] 生成 {len(test_set)} 条有效测试题 → {out_file}")


def run_judge_only(config: Dict, test_set_path: str, output_path: str = None):
    """仅评审模式（已有测试集）"""
    with open(test_set_path, "r", encoding="utf-8") as f:
        test_set = json.load(f)

    eval_result, bad_samples = evaluate_batch(
        test_set=test_set,
        kb_query_func=lambda q: query_knowledge_base(q, config),
        config=config,
    )

    out_file = output_path or config.get("output", {}).get("result_path", "eval_result.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(eval_result, f, ensure_ascii=False, indent=2)

    bad_file = config.get("output", {}).get("bad_sample_path", "bad_samples.json")
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(bad_samples, f, ensure_ascii=False, indent=2)

    html = generate_html_report(eval_result)
    report_file = config.get("output", {}).get("report_path", "eval_report.html")
    save_report(html, report_file)

    print(f"\n[完成] 评测结果 → {out_file}")
    print(f"[完成] HTML报告 → {report_file}")


def run_report_only(eval_result_path: str, output_path: str = None):
    """仅报告模式"""
    with open(eval_result_path, "r", encoding="utf-8") as f:
        eval_result = json.load(f)

    html = generate_html_report(eval_result)
    report_file = output_path or "eval_report.html"
    save_report(html, report_file)


def run_api_test(config: Dict):
    """API 自动化测试模式"""
    tester = ApiTester(config)
    result = tester.run_all_cases(FASTGPT_TEST_CASES)

    # 保存结果
    api_result_file = config.get("output", {}).get("api_test_result_path", "api_test_result.json")
    with open(api_result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 生成含 API 测试的 HTML 报告
    html = generate_html_report({}, result)
    save_report(html, "api_test_report.html")

    print(f"\n{'='*60}")
    print(f"🔌 API 测试汇总")
    print(f"{'='*60}")
    print(f"总用例数:   {result['total_cases']}")
    print(f"通过用例:   {result['passed_cases']}")
    print(f"失败用例:   {result['failed_cases']}")
    print(f"通过率:     {result['pass_rate']:.1%}")
    print(f"结果文件:   {api_result_file}")


def main():
    parser = argparse.ArgumentParser(description="TestCase Generator - 知识库全流程自动化测试工具")
    parser.add_argument("--mode", choices=["eval", "generate", "judge", "report", "api-test"],
                        default="eval", help="运行模式")
    parser.add_argument("--input", help="输入文件路径（测试集JSON或文本切片JSON）")
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--judge-rounds", type=int, default=3, help="评审轮数")
    parser.add_argument("--min-score", type=float, default=0.8, help="最低合格分数")
    parser.add_argument("--num-questions", type=int, default=2, help="每个chunk生成题目数")

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 命令行参数覆盖配置
    config.setdefault("evaluation", {})
    config["evaluation"]["judge_rounds"] = args.judge_rounds
    config["evaluation"]["min_answer_score"] = args.min_score
    config.setdefault("generation", {})
    config["generation"]["num_questions_per_chunk"] = args.num_questions

    # 执行对应模式
    if args.mode == "eval":
        if args.input and os.path.exists(args.input):
            # 判断是测试集还是文本切片
            with open(args.input, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0 and "question" in data[0]:
                # 已有测试集
                run_full_eval(config, test_set_path=args.input)
            elif isinstance(data, list) and isinstance(data[0], str):
                # 文本切片列表
                run_full_eval(config, chunks=data)
            else:
                print("[ERROR] 输入文件格式无法识别")
        else:
            # 使用示例数据
            sample_chunks = [
                "智云科技成立于1992年，是中国领先的智慧出行解决方案提供商。"
                "公司主要产品包括智能停车管理系统、门禁系统、通道闸机、充电桩等。"
                "在全国设有100多个分支机构，累计服务超过50万个停车项目。"
            ]
            run_full_eval(config, chunks=sample_chunks)

    elif args.mode == "generate":
        if args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and isinstance(data[0], str):
                run_generate_only(config, chunks=data, output_path=args.output)
            else:
                print("[ERROR] 出题模式需要文本切片列表作为输入")
        else:
            print("[ERROR] 出题模式需要 --input 参数")

    elif args.mode == "judge":
        if args.input:
            run_judge_only(config, args.input, args.output)
        else:
            print("[ERROR] 评审模式需要 --input 参数（测试集JSON）")

    elif args.mode == "report":
        if args.input:
            run_report_only(args.input, args.output)
        else:
            print("[ERROR] 报告模式需要 --input 参数（评测结果JSON）")

    elif args.mode == "api-test":
        run_api_test(config)


if __name__ == "__main__":
    main()
