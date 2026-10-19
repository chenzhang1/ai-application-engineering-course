# EX-20-01 | ch20 部署用多阶段 Dockerfile（沙箱无 Docker，仅作静态检查对象，见 ex_20_01）
# 构建命令（读者环境执行）：docker build -t order-service:latest examples/ch20_deploy/
# 运行命令：docker run -p 8917:8917 --read-only --tmpfs /tmp order-service:latest
# 说明：构建产物只含运行时依赖（无编译工具链、无构建缓存），镜像更小、攻击面更小。

# ── 阶段一：构建阶段（builder）——装全量工具链，编译/下载依赖 ────────────────
FROM python:3.12-slim AS builder
# 缩小基础镜像：slim 变体（~50MB 级）而不是完整 Debian；固定版本号避免"下次构建行为漂移"
WORKDIR /build
# 先只 COPY 依赖清单再安装：代码改动时命中 Docker 缓存，不必重装依赖（层缓存关键技巧）
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
# --prefix 把包装到独立目录，供第二阶段整体拷贝；--no-cache-dir 不留 pip 缓存

# ── 阶段二：运行阶段——只带解释器 + 已装好的依赖 + 应用代码 ─────────────────
FROM python:3.12-slim
# 重新从 slim 开始：builder 里的 gcc/构建缓存统统不进最终镜像
WORKDIR /app
COPY --from=builder /install /usr/local
# 只拷贝运行所需文件，.git/测试/示例不进镜像（.dockerignore 配合更佳）
COPY app.py .
# 非 root 运行：容器被攻破时攻击者不是 root（生产镜像的标配）
RUN useradd --create-home appuser
USER appuser
EXPOSE 8917
# 健康检查：编排器据此自动重启僵死容器（K8s 下通常由探针替代，见 ch20 正文）
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8917/healthz', timeout=2)" || exit 1
# uvicorn 生产参数：多 worker、 keep-alive 超时（参数含义见 ex_20_02 与 ch20 正文）
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8917", \
     "--workers", "2", "--timeout-keep-alive", "5"]
