"""
策划 Agent —— 流水线第一步。

职责：
  1. 读 topic + style + duration
  2. (可选) 用 Tavily 搜索相关热点素材
  3. 调 deepseek-reasoner（推理模型）生成结构化大纲
  4. 输出 Outline 对象：标题、钩子、段落列表、金句

模型选择：deepseek-reasoner
  策划需要深度分析能力（理解选题角度、梳理逻辑结构），
  用推理模型比对话模型效果好。

Tavily 搜索：
  如果配置了 tavily_api_key，会搜"热门话题 短视频"作为参考素材。
  搜索失败不阻塞主流程 —— 没有热点信息照样能生成大纲。
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from backend.app.agents.base import BaseAgent
from backend.app.schemas.agent import Outline, Section
from backend.app.core.config import get_settings
from backend.app.tracker.langfuse import trace_agent

logger = logging.getLogger(__name__)


class PlanningAgent(BaseAgent):
    """策划 Agent —— MCN 资深编导角色。

    输入：state 中的 topic / style / duration / feedback
    输出：state["outline"] = Outline 对象
    """

    def __init__(self):
        # 指定用 deepseek-reasoner，推理能力强
        super().__init__(model_name=get_settings().deepseek_reasoner_model)

    def _search_hotspot(self, topic: str) -> str:
        """用 Tavily 搜索给定选题的热门话题。

        搜索不会阻塞 —— API key 缺失或网络错误时静默返回空字符串。

        Args:
            topic: 选题关键词

        Returns:
            搜索结果的文本拼接，或空字符串
        """
        settings = get_settings()
        if not settings.tavily_api_key:
            return ""
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=settings.tavily_api_key)
            result = client.search(
                query=f"{topic} 热门话题 短视频",
                search_depth="basic",
                max_results=3,
            )
            summaries = [r.get("content", "")[:300] for r in result.get("results", [])]
            if summaries:
                logger.debug(f"Tavily 搜索成功 | query={topic} | 结果数={len(summaries)}")
            else:
                logger.debug(f"Tavily 搜索无结果 | query={topic}")
            return "\n".join(summaries) if summaries else ""
        except Exception as e:
            logger.warning(f"Tavily 搜索失败（降级跳过）| query={topic} | error={e}")
            return ""   # 搜索失败不阻塞，继续正常的策划流程

    @trace_agent("planning")
    def run(self, state: dict) -> dict:
        """执行策划逻辑。

        流程：
          1. 从 state 提取参数
          2. 搜热点素材（可选）
          3. 拼 system prompt（编导角色设定 + 大纲要求 + JSON 格式示例）
          4. 调 LLM → 提取 JSON → 转 Outline 对象
          5. 写回 state["outline"]

        Args:
            state: 流水线状态字典，从中读取 topic/style/duration/feedback

        Returns:
            更新后的 state，包含 outline 字段
        """
        topic = state.get("topic", "")
        style = state.get("style", "知识")
        duration = state.get("duration", 120)
        feedback = state.get("feedback", "")

        # 第 1 步：搜热点（有 key 才生效）
        hotspot = self._search_hotspot(topic)
        hotspot_text = f"\n热点参考：\n{hotspot}" if hotspot else ""
        feedback_text = f"\n修改要求：{feedback}" if feedback else ""

        # 第 2 步：拼 system prompt
        # 包括：角色设定、输出要求、JSON 格式示例
        # 为什么 JSON 示例里是 {{ 而不是 { ？
        #   Python f-string 会把 {{ 转成 { ，最终 LLM 看到的是 { 。
        #   只用 Python f-string（不是 LangChain 模板），不会二次解析。
        system = f"""你是MCN资深编导，为{style}类账号策划口播大纲。

选题：{topic}
风格：{style}
时长：{duration}秒（约{duration // 2}字）
{hotspot_text}{feedback_text}

要求：开头3秒钩子抓住注意力，结构清晰（引入→展开→高潮→收尾），至少3条金句。

严格按JSON格式输出（不要输出其他内容）：
```json
{{"title":"标题","hook":"钩子文案","sections":[{{"heading":"段名","talking_points":["要点"]}}],"key_phrases":["金句1","金句2","金句3"],"estimated_duration":{duration}}}
```"""

        # 第 3 步：构建消息 → 调 LLM → 解析 JSON → 转 Pydantic 对象
        messages = [SystemMessage(content=system), HumanMessage(content="输出策划大纲JSON。")]
        outline = self._invoke(messages, Outline, state)

        # 第 4 步：兜底 —— LLM 解析失败时用简化版大纲
        if outline is None:
            outline = Outline(
                title=topic,
                hook="",
                sections=[Section(heading="内容", talking_points=["策划Agent解析失败，请重试"])],
                key_phrases=[],
                estimated_duration=duration,
            )

        # 第 5 步：写回 state
        state["outline"] = outline.model_dump()
        return state
