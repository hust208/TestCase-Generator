# TestCase Generator

> 🧪 知识库全流程自动化测试工具 — 从出题、过滤、评测到 API 测试，一站搞定

## ✨ 核心特性

| 功能 | 说明 |
|------|------|
| **智能出题** | 基于 LLM 从知识库文本切片自动生成事实题/归纳题/辨析题/不存在题 |
| **双层过滤** | 规则过滤 + Embedding 语义去重，确保题目质量 |
| **分维度评审** | 独立评判正确性、忠实度、幻觉、检索召回/精确率，避免维度冲突 |
| **多轮稳定评审** | 支持 N 次评审取均值，消除 LLM-as-Judge 单次偏差 |
| **幻觉定位** | 不仅判定是否幻觉，还能定位幻觉片段并给出证据 |
| **API 测试引擎** | 支持 FastGPT / 私有知识库 API 全流程 CRUD 自动化测试 |
| **HTML 报告** | 自动生成可视化评测报告，含维度雷达图、不合格样本明细 |
| **配置化管理** | YAML 配置文件 + 命令行参数，灵活适配不同环境 |

## 📦 项目结构

```
TestCase-Generator/
├── README.md                  # 项目说明
├── LICENSE                    # Apache-2.0 许可证
├── setup.py                   # 安装配置
├── requirements.txt           # Python 依赖
├── .gitignore                 # Git 忽略规则
├── config/
│   └── config.yaml            # 默认配置模板
├── src/
│   ├── __init__.py
│   ├── generator.py           # 智能出题引擎
│   ├── filter.py              # 双层过滤引擎
│   ├── evaluator.py           # 分维度独立评审引擎
│   ├── kb_query.py            # 知识库问答接口
│   ├── api_tester.py          # API 自动化测试引擎
│   ├── report.py              # HTML 报告生成器
│   ├── utils.py               # 公共工具函数
│   ├── types.py               # 类型定义
│   └── config_loader.py       # 配置加载器
├── examples/
│   ├── example_test_set.json  # 示例测试集
│   └── example_eval_result.json # 示例评测结果
│   └── example_api_test.json  # 示例 API 测试结果
├── tests/
│   ├── __init__.py
│   ├── test_generator.py      # 出题引擎单元测试
│   ├── test_filter.py         # 过滤引擎单元测试
│   └── test_evaluator.py      # 评审引擎单元测试
└── main.py                    # 主入口
```

## 🚀 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 配置

编辑 `config/config.yaml`，填入你的 API 地址和密钥：

```yaml
kb_api:
  url: "http://your-kb-api-url/openapi/chat"
  top_k: 3

llm_api:
  url: "http://your-llm-url/v1/completions"
  temperature: 0.1
  max_tokens: 2048

embedding_api:
  url: "http://your-embedding-url/v1/embeddings"

evaluation:
  min_answer_score: 0.8
  sim_dup_threshold: 0.9
  judge_rounds: 3        # 评审轮数，取均值提升稳定性
```

### 运行知识库评测

```bash
# 全流程评测（出题 → 过滤 → 问答 → 评审 → 报告）
python main.py --mode eval --input your_chunks.json

# 仅出题
python main.py --mode generate --input your_chunks.json --output test_set.json

# 仅评审（已有测试集）
python main.py --mode judge --input test_set.json

# 生成 HTML 报告
python main.py --mode report --input eval_result.json
```

### 运行 API 测试

```bash
# FastGPT API 全流程测试
python main.py --mode api-test --config config/config.yaml
```

## 🔬 评审引擎架构

核心改进：**分维度独立评审 + 多轮取均值**

```
传统方式（kb_auto_evaluate.py）:
  一次 LLM 调用 → 同时输出5个维度 → 维度冲突、不稳定

改进方式（本项目）:
  ┌─────────────┐
  │  正确性评审  │ → judge_rounds 次取均值 → answer_correct_score
  ├─────────────┤
  │  忠实度评审  │ → judge_rounds 次取均值 → faithfulness_score
  ├─────────────┤
  │  幻觉检测    │ → judge_rounds 次取均值 → hallucination_score + 定位
  ├─────────────┤
  │  检索召回率  │ → embedding 语义比对    → context_recall
  ├─────────────┤
  │  检索精确率  │ → embedding 语义比对    → context_precision
  └─────────────┘
```

### 幻觉定位示例

```json
{
  "has_hallucination": true,
  "hallucination_score": 0.35,
  "hallucination_details": [
    {
      "claim": "智云科技成立于1998年",
      "evidence": "上下文中明确写的是1992年，此陈述与原文矛盾",
      "type": "contradiction"
    },
    {
      "claim": "智云科技服务超过80万个停车项目",
      "evidence": "上下文中无此数据，原文写的是50万",
      "type": "fabrication"
    }
  ]
}
```

## 📊 输出格式

### 评测结果 (eval_result.json)

```json
{
  "summary": {
    "total_sample": 30,
    "pass_sample": 25,
    "overall_accuracy": 0.8333,
    "hallucination_rate": 0.1333,
    "avg_scores": {
      "answer_correct": 0.85,
      "faithfulness": 0.92,
      "context_recall": 0.78,
      "context_precision": 0.81
    }
  },
  "detail_records": [...]
}
```

### HTML 报告

自动生成含以下内容的可视化报告：
- 📈 评测总览（准确率、幻觉率）
- 🎯 维度雷达图（正确性/忠实度/召回/精确率）
- 📋 不合格样本明细表
- 🔍 幻觉定位详情

## ⚙️ 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--mode` | 运行模式: eval/generate/judge/report/api-test | eval |
| `--input` | 输入文件路径 | - |
| `--output` | 输出文件路径 | - |
| `--config` | 配置文件路径 | config/config.yaml |
| `--judge-rounds` | 评审轮数 | 3 |
| `--min-score` | 最低合格分数 | 0.8 |
| `--num-questions` | 每个chunk生成题目数 | 2 |

## 📝 License

Apache-2.0

---

## 🐳 Docker 郹署

### 快速启动

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际 API 地址

# 2. 配置本地配置
cp config/config.yaml config/local_config.yaml

# 3. 创建输入目录并放置数据
mkdir -p input output
cp your_chunks.json input/chunks.json

# 4. 构建并运行
docker compose build
docker compose up eval          # 知识库评测
docker compose up api-test      # API测试
docker compose up all-tests     # 全流程

# 5. 查看报告
docker compose up report-viewer
# 浏览器访问 http://localhost:8080
```

详细部署说明请参阅 [DOCKER.md](DOCKER.md)
