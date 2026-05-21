"""
Agent 基类 —— 所有 Agent 的公共逻辑和统一接口。

每个 Agent 继承 BaseAgent，只需实现 run(state) → state。

BaseAgent 提供：
  1. __init__():     初始化 LLM 客户端（ChatOpenAI → DeepSeek API）
  2. _invoke():      统一的 LLM 调用 + JSON 解析 + 异常处理流程
  3. extract_json(): 从 LLM 文本响应中提取 JSON（处理 markdown 代码块包裹）

为什么不用 LangChain 的 ChatPromptTemplate？
  踩过坑。LangChain 的 f-string 模板解析器会对花括号二次解析，
  与 Python f-string 冲突，导致 "Invalid format specifier" 错误。
  解决方案：直接用 SystemMessage(content=f"...") 拼 prompt 字符串，
  绕过 LangChain 的模板系统，只经过 Python f-string 一次解析。

为什么不用 PydanticOutputParser / with_structured_output？
  踩过坑。PydanticOutputParser 把 JSON Schema 塞进 prompt，
  DeepSeek 有时候不填内容而是回吐 Schema 本身。
  with_structured_output 在 DeepSeek 上也不稳定。
  解决方案：prompt 里写一行的 JSON 示例，用 json.loads() 手动解析。
"""

import json
import logging
import traceback
from abc import ABC, abstractmethod
from langchain_openai import ChatOpenAI
from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


# ============================================================
# 公共函数：从 LLM 响应中提取 JSON
# ============================================================
def extract_json(raw: str) -> dict:
    """从 LLM 文本响应中提取 JSON 对象。

    LLM 经常把 JSON 包在 markdown 代码块里（```json ... ```）。
    这个函数处理所有常见情况：
      - ```json {...} ```  → 去掉代码块标记，取中间 JSON
      - ``` {...} ```      → 同上
      - {...}              → 直接解析

    Args:
        raw: LLM 的原始文本响应

    Returns:
        dict: 解析后的 JSON 字典

    Raises:
        json.JSONDecodeError: JSON 格式错误时抛出，由 _invoke 捕获
    """
    text = raw.strip()
    # 先尝试标准 json 代码块
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    # 解析并返回
    return json.loads(text.strip())


# ============================================================
# Agent 基类
# ============================================================
class BaseAgent(ABC):
    """所有 Agent 的抽象基类。

    子类需要实现：
      run(self, state: dict) -> dict

    子类的 run 通常做三件事：
      1. 从 state 读取自己需要的数据
      2. 拼 prompt → 调 _invoke() → 拿到 Pydantic 模型
      3. 把结果 model_dump() 写回 state

    _invoke() 封装了通用流程：调 LLM → 提取 JSON → 解析 → 兜底异常。
    """

    def __init__(self, model_name: str | None = None):
        """初始化 LLM 客户端。

        默认用 deepseek-chat（快+便宜，适合写作和修改）。
        策划和审核通过 model_name 参数改用 deepseek-reasoner。

        ChatOpenAI 为什么能调 DeepSeek？
          DeepSeek 的 API 与 OpenAI 完全兼容。
          只要把 openai_api_base 设为 DeepSeek 的地址，
          把 openai_api_key 设为 DeepSeek 的 key 即可。

        Args:
            model_name: DeepSeek 模型名。不传则用 .env 中的 deepseek_chat_model。
        """
        settings = get_settings()
        self.model_name = model_name or settings.deepseek_chat_model
        self.llm = ChatOpenAI(
            model=self.model_name,
            openai_api_key=settings.deepseek_api_key,
            openai_api_base=settings.deepseek_base_url,
            temperature=0.7,     # 0.7：有点创造性但不跑偏
            max_tokens=4096,     # 单次最多输出 4096 token
        )

    # ============================================================
    # 统一调用流程：发消息 → 拿文本 → 提取 JSON → 转 Pydantic 对象
    # ============================================================
    def _invoke(self, messages: list, schema: type, state: dict):
        """调 LLM 并返回解析后的 Pydantic 对象。

        流程：
          1. self.llm.invoke(messages) → LLM 返回文本响应
          2. extract_json(raw)        → 从文本中提取 JSON
          3. schema(**data)           → JSON 转 Pydantic 模型

        Args:
            messages: SystemMessage + HumanMessage 组成的消息列表
            schema:   Pydantic 模型类（如 Outline、Script、ReviewResult）
            state:    当前 state（备用，_invoke 暂时不用它）

        Returns:
            schema 对应的 Pydantic 实例，或 None（解析失败时）
        """
        response = self.llm.invoke(messages)
        raw = response.content

        # 提取 token 用量（DeepSeek 兼容 OpenAI SDK，token 信息在 usage_metadata）
        token_usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            token_usage = {
                "input_tokens": response.usage_metadata.get("input_tokens", 0),
                "output_tokens": response.usage_metadata.get("output_tokens", 0),
                "total_tokens": response.usage_metadata.get("total_tokens", 0),
            }
        state["_last_tokens"] = token_usage
        # 汇总累计 token（用于前端展示总消耗）
        if token_usage:
            acc = state.get("_total_tokens", {})
            for k in ("input_tokens", "output_tokens", "total_tokens"):
                acc[k] = acc.get(k, 0) + token_usage.get(k, 0)
            state["_total_tokens"] = acc

        try:
            data = extract_json(raw)
            return schema(**data)
        except Exception:
            # 解析失败 → 记 warning 日志，返回 None
            # 各 Agent 的 run 函数收到 None 后会构造兜底对象
            logger.warning(f"[{self.__class__.__name__}] JSON 解析失败，使用兜底")
            logger.debug(traceback.format_exc())
            return None

    @abstractmethod
    def run(self, state: dict) -> dict:
        """执行 Agent 核心逻辑。子类必须实现。

        Args:
            state: 当前流水线状态字典

        Returns:
            更新后的状态字典
        """
        pass
