"""
全局配置管理 —— 所有环境变量和 API key 的单一入口。

为什么需要这个模块？
  敏感信息（API key、base URL 等）不能硬编码在代码里。
  它们来自 .env 文件或系统环境变量，统一在一处读取和管理。

用法（全局只要一个 Settings 实例）：
  from backend.app.core.config import get_settings
  settings = get_settings()
  key = settings.deepseek_api_key

Pydantic Settings 原理：
  BaseSettings 在实例化时自动从两个来源读取配置：
  1. .env 文件（通过 env_file 指定）
  2. 系统环境变量（优先级更高，可覆盖 .env）
  读取后的值会做类型校验（str 还是 str，int 才是 int）。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置类。

    每个字段对应一个配置项。
    .env 文件中大写同名变量（如 DEEPSEEK_API_KEY）会自动映射。
    环境变量优先于 .env 文件。
    """

    # model_config 是 Pydantic V2 的配置方式（替代旧版 class Config）
    # env_file:      从 .env 文件读取（相对于项目根目录）
    # case_sensitive: 环境变量名不区分大小写（DEEPSEEK_API_KEY = deepseek_api_key）
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ---------- DeepSeek API 配置 ----------
    # deepseek_api_key:    DeepSeek 开放平台申请的 API key
    # deepseek_base_url:   API 基础地址（兼容 OpenAI SDK 格式）
    # deepseek_reasoner_model: 推理模型（用于策划 + 审核，推理能力强但较慢）
    # deepseek_chat_model:     对话模型（用于写作 + 修改，速度快成本低）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_reasoner_model: str = "deepseek-reasoner"
    deepseek_chat_model: str = "deepseek-chat"

    # ---------- Tavily 搜索 API ----------
    # 用于策划 Agent 搜热点话题、审核 Agent 做事实核查
    # 不需要搜索功能时可以不填
    tavily_api_key: str = ""
    # 限定搜索域名（逗号分隔），只搜中文内容平台，为空则不限
    tavily_include_domains: str = (
        # 社交/视频
        "weibo.com,douyin.com,bilibili.com,xiaohongshu.com,"
        # 门户/新闻
        "news.qq.com,thepaper.cn,ifeng.com,sohu.com,sina.com.cn,163.com,guancha.cn,"
        # 科技/商业
        "36kr.com,huxiu.com,ithome.com,"
        # 问答/知识
        "zhihu.com,baidu.com,csdn.net,juejin.cn,jianshu.com"
    )

    # ---------- LangFuse 可观测性（层 4 启用）----------
    # LLM 调用追踪、性能监控、成本统计
    # 不需要可观测性时可以不填
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


@lru_cache()
def get_settings() -> Settings:
    """获取全局配置单例（带缓存）。

    @lru_cache() 的作用：
      第一次调用时创建 Settings 实例并缓存。
      后续调用直接返回缓存值，不会重复读取 .env 文件。
      既保证全局唯一，又避免 I/O 开销。

    为什么不用全局变量？
      全局变量在模块被 import 时就初始化，此时 .env 可能还没加载。
      用缓存函数延迟到第一次调用时才初始化，更安全。

    Returns:
        Settings: 全局唯一的配置实例
    """
    return Settings()
