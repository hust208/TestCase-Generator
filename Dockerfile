# ============================================================
# TestCase Generator - Docker 多阶段构建
# ============================================================
# 阶段1: builder - 安装依赖
# 阶段2: app - 运行应用
# ============================================================

# ---- 阶段1: 安装依赖 ----
FROM python:3.11-slim AS builder

WORKDIR /build

# 复制依赖文件
COPY requirements.txt .

# 安装依赖到独立目录（便于后续复制）
pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- 阶段2: 运行应用 ----
FROM python:3.11-slim AS app

LABEL maintainer="hust208"
LABEL description="TestCase Generator - 知识库全流程自动化测试工具"
LABEL version="1.0.0"

# 安装阶段从 builder 复制依赖
COPY --from=builder /install /usr/local

WORKDIR /app

# 复制项目文件
COPY src/ ./src/
COPY main.py .
COPY config/ ./config/
COPY examples/ ./examples/
COPY tests/ ./tests/
COPY setup.py .
COPY requirements.txt .

# 创建输出目录（评测结果、报告等）
RUN mkdir -p /app/output

# 设置环境变量
ENV PYTHONPATH=/app/src
ENV TCG_OUTPUT__RESULT_PATH=/app/output/eval_result.json
ENV TCG_OUTPUT__BAD_SAMPLE_PATH=/app/output/bad_samples.json
ENV TCG_OUTPUT__TEST_SET_PATH=/app/output/test_set.json
ENV TCG_OUTPUT__REPORT_PATH=/app/output/eval_report.html

# 健康检查（验证 Python 环境正常）
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import src; print('OK')" || exit 1

# 默认入口：全流程评测
ENTRYPOINT ["python", "main.py"]

# 默认参数
CMD ["--mode", "eval", "--config", "config/config.yaml"]
