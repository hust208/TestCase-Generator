# TestCase Generator - Docker 部署指南

## 📦 快速开始

### 1. 准备配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入实际 API 地址和密钥
vi .env

# 复制配置模板为本地配置
cp config/config.yaml config/local_config.yaml

# 编辑 local_config.yaml，根据 .env 中的地址调整
vi config/local_config.yaml
```

### 2. 创建输入/输出目录

```bash
mkdir -p input output

# 将知识库文本切片放入 input 目录
cp your_chunks.json input/chunks.json
# 或将已有测试集放入
cp your_test_set.json input/test_set.json
```

### 3. 构建镜像

```bash
docker compose build
```

### 4. 运行评测

```bash
# 知识库全流程评测
docker compose up eval

# 仅出题
docker compose up generate

# 仅评审（已有测试集）
docker compose up judge

# API 自动化测试
docker compose up api-test

# 生成 HTML 报告
docker compose up report

# 全流程（评测 + API测试 + 报告）
docker compose up all-tests
```

### 5. 查看报告

```bash
# 启动报告查看服务
docker compose up report-viewer

# 浏览器访问
# http://localhost:8080
```

---

## 🔧 环境变量说明

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_URL` | LLM API 地址 | `http://host.docker.internal:8000/v1/chat/completions` |
| `EMB_API_URL` | Embedding API 地址 | `http://host.docker.internal:8001/v1/embeddings` |
| `KB_API_URL` | 知识库问答 API | `http://jszsk.jieshun.cn:3000/openapi/chat` |
| `FASTGPT_URL` | FastGPT 平台地址 | `http://host.docker.internal:3000` |
| `FASTGPT_API_KEY` | FastGPT API 密钥 | `your-api-key` |
| `JUDGE_ROUNDS` | 评审轮数 | `3` |
| `MIN_SCORE` | 合格阈值 | `0.8` |

> `host.docker.internal` 是 Docker 访问宿主机服务的特殊域名（适用于 Docker Desktop）

---

## 📂 目录映射

| 容器路径 | 主机路径 | 说明 |
|---------|---------|------|
| `/app/config/local_config.yaml` | `./config/local_config.yaml` | 本地配置（含密钥） |
| `/app/input` | `./input` | 输入文件（chunks/test_set） |
| `/app/output` | `./output` | 输出文件（结果/报告） |

---

## 🏗️ 架构图

```
┌─────────────────────────────────────────────┐
│              Docker Network                  │
│                                              │
│  ┌──────────────┐    ┌───────────────────┐  │
│  │  tcg-eval    │    │  tcg-api-test     │  │
│  │  知识库评测   │    │  FastGPT API测试   │  │
│  └──────┬───────┘    └────────┬──────────┘  │
│         │                     │              │
│         ▼                     ▼              │
│  ┌──────────────────────────────────────┐   │
│  │           /app/output/               │   │
│  │  eval_result.json | bad_samples.json │   │
│  │  eval_report.html                    │   │
│  └──────────────────┬───────────────────┘   │
│                     │                        │
│                     ▼                        │
│  ┌──────────────────────────┐               │
│  │  tcg-report-viewer       │               │
│  │  Nginx (port 8080)       │               │
│  │  → http://localhost:8080 │               │
│  └──────────────────────────┘               │
│                                              │
│  ← host.docker.internal → 宿主机服务        │
│    (LLM / Embedding / KB API)               │
└─────────────────────────────────────────────┘
```

---

## ⚠️ 生产环境建议

1. **安全性**：`.env` 和 `local_config.yaml` 不要提交到 Git
2. **网络**：如果 LLM/API 在远程服务器，直接使用 URL 而非 `host.docker.internal`
3. **持久化**：使用 named volumes 替代 bind mounts 用于生产环境
4. **资源限制**：添加 `deploy.resources.limits` 限制 CPU/内存

```yaml
# docker-compose.yml 中添加资源限制示例
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
```

---

## 🔄 常用操作

```bash
# 查看运行日志
docker compose logs eval

# 重新构建（代码更新后）
docker compose build --no-cache

# 清理所有容器和镜像
docker compose down --rmi all

# 仅运行单次评测（完成后自动退出）
docker compose run --rm eval

# 指定输入文件
docker compose run --rm eval -- --input /app/input/my_test_set.json
```
