"""
日志系统配置 — 全局 logger 初始化。

用法：
  在 main.py 的 lifespan 里调用 setup_logging()。
  其他模块只需要：
    import logging
    logger = logging.getLogger(__name__)
    logger.info("xxx")

设计：
  - 控制台 + 文件双输出
  - 文件按天轮转（保留 7 天），路径 logs/app.log
  - 日志级别通过环境变量 LOG_LEVEL 控制（默认 INFO）
  - 格式：时间 | 级别 | 模块 | 消息
"""
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_logging() -> None:
    """配置全局日志系统。

    行为：
    - 控制台输出 ≥INFO 级别（可读性强）
    - 文件输出 ≥DEBUG 级别（留底备查，比控制台更详细）
    - 文件按天轮转：每天午夜生成新文件，旧文件保留 7 天
    - 级别通过环境变量 LOG_LEVEL 覆盖

    为什么控制台和文件用不同级别？
      控制台 INFO：日常开发/运维只看关键流程，不被 DEBUG 刷屏。
      文件 DEBUG：排查问题时 debug 日志都在文件里，grep 就能找。
    """
    # 从环境变量读日志级别（默认 INFO）
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    console_level = getattr(logging, level_name, logging.INFO)
    # 文件始终 DEBUG 级别 —— 留底备查
    file_level = logging.DEBUG

    # 日志格式
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ---- 控制台 handler ----
    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(fmt)

    # ---- 文件 handler ----
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"

    file_handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",       # 每天午夜轮转
        interval=1,
        backupCount=7,         # 保留最近 7 天
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(fmt)
    # 轮转后的文件命名：app.log.2026-05-21
    file_handler.suffix = "%Y-%m-%d"

    # ---- 配置根 logger ----
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # 放行所有级别，由 handler 各自过滤
    root.addHandler(console)
    root.addHandler(file_handler)

    # 减少第三方库日志噪音（uvicorn 等有自己的 logger）
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
