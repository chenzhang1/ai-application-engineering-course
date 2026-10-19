# P1 企业文档知识库 —— FastAPI 服务包
"""app 包：schemas（Pydantic 契约）/ security（多租户权限）/ lexical（词面特征）
/ judge（证据充分性判定）/ kb（向量库与问答核心）/ main（FastAPI 路由）。

导入约定：包内统一用绝对导入 `from app.xxx import ...`，
前提是项目根目录（本文件上一级）在 sys.path 中——
uvicorn 从项目根启动、测试/test_p1.py 与 eval/run_eval.py 均已显式插入。
"""
