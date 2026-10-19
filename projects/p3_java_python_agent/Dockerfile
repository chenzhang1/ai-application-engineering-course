# 项目三·Python 侧镜像（仅静态检查：沙箱无 Docker，见 _meta/FACTS.md——不声称已构建运行）
# 构建上下文 = 仓库根目录：
#   docker build -f projects/p3_java_python_agent/Dockerfile -t p3-plan-agent .
# Java 服务不进本镜像（AI 服务与业务服务分离部署，教材 ch57 的架构边界）：
#   生产把 PLAN_JAVA_BASE_URL 指向 K8s Service / docker-compose 网络别名。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先装依赖再拷代码：利用层缓存（ch20 多阶段思想的最简形态）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 只拷运行所需：planagent 包 + 契约数据（Java 代码与测试不进运行镜像）
COPY projects/p3_java_python_agent/planagent ./planagent
COPY projects/p3_java_python_agent/data ./data

ENV PLAN_JAVA_BASE_URL=http://host.docker.internal:8080 \
    P3_AUDIT_PATH=/app/audit/audit.jsonl \
    LLM_MODE=mock

EXPOSE 8000

# 容器存活以 /health 为准（ch20 健康检查端点规矩）
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2); sys.exit(0)" || exit 1

# 单 worker：任务状态在进程内存（TaskStore 为进程内实现）；多副本需把任务表外置（README 扩展方向）
CMD ["uvicorn", "planagent.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
