# P1 入库管线包：加载（loaders）→ 清洗（cleaner）→ 切分入库（pipeline）
"""用法（项目根目录下）：
    python3 -m ingest.pipeline            # 把 data/*.md 全部入库到默认存储
    P1_STORE_PATH=/tmp/x.json python3 -m ingest.pipeline
"""
