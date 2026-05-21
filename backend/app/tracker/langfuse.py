"""
LangFuse 可观测追踪。
记录每个Agent的耗时，有 Key 时上报 LangFuse Dashboard，没有时退化为 logging 输出。
"""

import logging
import time
import functools
from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


# 模块级开关：有 LangFuse key 才尝试启用
# 占位符（xxx、your-xxx 等）等同于未配置，避免 401
_settings = get_settings()
_LANGFUSE_ENABLED = bool(
    _settings.langfuse_public_key
    and _settings.langfuse_secret_key
    and "xxx" not in _settings.langfuse_public_key
    and "xxx" not in _settings.langfuse_secret_key
    and "your-langfuse" not in _settings.langfuse_public_key.lower()
)
_langfuse = None

if _LANGFUSE_ENABLED:
    try:
        from langfuse import Langfuse
        _langfuse = Langfuse(
            public_key=_settings.langfuse_public_key,
            secret_key=_settings.langfuse_secret_key,
            host=_settings.langfuse_host,
        )
    except Exception:
        _langfuse = None


def trace_agent(agent_name: str):
    """装饰器：追踪 Agent.run() 的每次调用。

    行为：
    - 始终在终端 print 耗时日志
    - 如果配置了 LangFuse → 同时创建 observation span 上报 Dashboard

    Args:
        agent_name: Agent 名称标识（planning/writing/review/revision）

    Returns:
        装饰器函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, state):
            t0 = time.time()
            span = None

            # 有 LangFuse → 创建 observation span（v3 API）
            if _langfuse is not None:
                try:
                    span = _langfuse.start_observation(
                        name=f"agent.{agent_name}",
                        as_type="agent",
                        input={"step": state.get("step", "?")},
                    )
                except Exception:
                    span = None

            try:
                result = func(self, state)
                elapsed = time.time() - t0

                # 日志输出（始终生效）
                tokens = state.get("_last_tokens", {})
                if tokens:
                    logger.info(f"[Agent] {agent_name} | {elapsed:.1f}s | {tokens.get('input_tokens', 0)}+{tokens.get('output_tokens', 0)}={tokens.get('total_tokens', 0)} tokens | rev={state.get('revision_count', 0)}")
                else:
                    logger.info(f"[Agent] {agent_name} | {elapsed:.1f}s | rev={state.get('revision_count', 0)}")

                # LangFuse span 更新 + 关闭
                if span is not None:
                    try:
                        span.update(
                            metadata={
                                "agent": agent_name,
                                "elapsed": elapsed,
                                "step": state.get("step"),
                                "revision_count": state.get("revision_count", 0),
                            }
                        )
                        span.end()
                    except Exception:
                        pass

                return result

            except Exception as e:
                elapsed = time.time() - t0
                logger.error(f"[Agent] {agent_name} | {elapsed:.1f}s | ERROR: {e}")
                if span is not None:
                    try:
                        span.update(metadata={"error": str(e), "elapsed": elapsed})
                        span.end()
                    except Exception:
                        pass
                raise

        return wrapper
    return decorator


def flush():
    """刷新 LangFuse 缓冲区，确保数据发送完成。"""
    if _langfuse is not None:
        try:
            _langfuse.flush()
        except Exception:
            pass
