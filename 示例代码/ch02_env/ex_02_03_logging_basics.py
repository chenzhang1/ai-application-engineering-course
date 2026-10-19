# EX-02-03 | 运行命令: python3 示例代码/ch02_env/ex_02_03_logging_basics.py
"""logging 基础：级别、格式、惰性参数、异常堆栈记录（对照 logback/slf4j）。

注意两点与 Java 的差异：
1. logging 默认输出到 stderr（logback 的 ConsoleAppender 默认 stdout）；
2. 推荐惰性写法 logger.info("金额=%s", amount) 而不是 f-string：
   级别未开启时字符串拼接不会发生（等价于 slf4j 的 {} 占位符）。
"""
from __future__ import annotations

import logging

# Java: private static final Logger log = LoggerFactory.getLogger(PayService.class);
logger = logging.getLogger("demo.pay")


def configure_logging(level: int = logging.INFO) -> None:
    """一次性配置（等价于 logback.xml 做的事，这里用代码做）。"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def charge(amount: int) -> None:
    """演示正常路径与异常路径的日志写法。"""
    logger.debug("进入 charge，金额=%s", amount)  # 惰性 %s：级别不够时不开销
    if amount < 0:
        try:
            raise ValueError(f"金额不能为负: {amount}")
        except ValueError:
            logger.exception("下单失败，amount=%s", amount)  # 自动带堆栈
            raise
    logger.info("扣款成功 amount=%s", amount)


def main() -> None:
    configure_logging(logging.DEBUG)
    charge(100)
    try:
        charge(-1)
    except ValueError:
        logger.error("调用方收到失败，已按降级流程处理")


if __name__ == "__main__":
    main()
