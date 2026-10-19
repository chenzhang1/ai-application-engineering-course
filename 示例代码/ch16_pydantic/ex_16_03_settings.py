# EX-16-03 | pydantic-settings：.env 加载、环境变量优先级、密钥不进代码
# 运行：python3 示例代码/ch16_pydantic/ex_16_03_settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置：默认值 < .env < 真实环境变量（后者覆盖前者）。"""
    model_config = SettingsConfigDict(
        env_file=".env",        # 相对当前工作目录；工程里常用 env_file=(".env",)
        env_file_encoding="utf-8",
        env_prefix="ORDER_",    # 环境变量名自动变成 ORDER_APP_ENV 这种形式
        extra="ignore",         # .env 里的无关变量不报错
    )

    app_env: str = "dev"                      # ORDER_APP_ENV
    redis_url: str = "redis://127.0.0.1:6379/0"  # ORDER_REDIS_URL
    openai_api_key: str = ""                  # ORDER_OPENAI_API_KEY——只在环境/.env，绝不硬编码
    rate_limit_per_minute: int = 60           # ORDER_RATE_LIMIT_PER_MINUTE


def main() -> None:
    # 层级 1：默认值 + .env（本示例目录的 .env 提供了 app_env=staging 等）
    s1 = Settings(_env_file=".env")  # 显式指定，避免受启动目录影响
    print(f"[.env]      app_env={s1.app_env!r}  redis_url={s1.redis_url!r}  rate_limit={s1.rate_limit_per_minute}")
    print(f"[.env]      openai_api_key 是否像占位符：{s1.openai_api_key.startswith('sk-demo')}")

    # 层级 2：真实环境变量优先级最高（Java 对照：System.getenv / Spring 的 profile 配置覆盖）
    import os
    os.environ["ORDER_APP_ENV"] = "production"
    os.environ["ORDER_RATE_LIMIT_PER_MINUTE"] = "120"
    s2 = Settings(_env_file=".env")
    print(f"[env覆盖]   app_env={s2.app_env!r}  rate_limit={s2.rate_limit_per_minute}（env > .env > 默认值）")
    del os.environ["ORDER_APP_ENV"], os.environ["ORDER_RATE_LIMIT_PER_MINUTE"]

    # 工程检查：生产环境绝不允许空密钥——配置校验也是校验
    if s1.app_env == "production" and not s1.openai_api_key:
        raise RuntimeError("生产环境必须配置 ORDER_OPENAI_API_KEY")


if __name__ == "__main__":
    main()
