# EX-02-02 | 运行命令:
#   方式一（环境变量）: APP_APP_NAME=客服助手 APP_LLM_MODE=mock APP_API_KEY=demo-key-not-real python3 examples/ch02_env/ex_02_02_settings_env.py
#   方式二（.env 文件）: python3 examples/ch02_env/ex_02_02_settings_env.py examples/ch02_env/.env.example
#   方式三（优先级演示）: APP_APP_NAME=命令行优先 python3 examples/ch02_env/ex_02_02_settings_env.py examples/ch02_env/.env.example
"""用 pydantic-settings 读取配置与密钥（.env 文件 + 环境变量，密钥不进代码）。

依赖：pydantic-settings==2.16.0（见 requirements.txt）。
要点：
1. 密钥类型用 SecretStr，repr/str 自动打码，防止日志泄漏；
2. 环境变量优先级高于 .env 文件（CI/容器注入直接生效）；
3. 必填项缺失时启动即失败（fail fast），而不是跑到一半才炸。
"""
from __future__ import annotations

import sys
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置：环境变量（APP_ 前缀）> .env 文件 > 代码默认值。"""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",  # 相对“当前工作目录”解析
        env_file_encoding="utf-8",
        extra="ignore",  # .env 里的无关变量不报错
    )

    app_name: str = "unknown-app"
    llm_mode: str = "mock"  # mock=不联网；real=真实调用
    api_key: SecretStr  # 必填：不给就拒绝启动

    def masked_key(self) -> str:
        """打码后的密钥，可以安全进日志。"""
        value = self.api_key.get_secret_value()
        return f"{value[:4]}****({len(value)} 位)"


def load_settings(env_file: Path | None = None) -> Settings:
    """加载配置；显式传入 env_file 时优先生效（用于演示与测试）。"""
    if env_file is not None:
        return Settings(_env_file=env_file)
    return Settings()


def main() -> None:
    env_file = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    settings = load_settings(env_file)
    print(f"应用名     : {settings.app_name}")
    print(f"运行模式   : {settings.llm_mode}")
    print(f"密钥打码   : {settings.masked_key()}")
    print(f"直接打印   : {settings.api_key}")  # SecretStr 自动打码


if __name__ == "__main__":
    main()
