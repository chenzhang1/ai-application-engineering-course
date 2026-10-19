# 全书共享 conftest：无副作用，仅保证 tests 目录可发现
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 默认 Mock 模式，任何示例导入 llm_client 都不会真实联网
os.environ.setdefault("LLM_MODE", "mock")
