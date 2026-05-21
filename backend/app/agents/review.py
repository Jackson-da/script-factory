"""
审核 Agent —— 流水线第三步。

职责：
  1. 读脚本全文
  2. 四维打分：信息量 / 口语化 / 合规性 / 可用率
  3. 问题分级：P0=合规必改 / P1=事实必改 / P2=风格建议
  4. (可选) 用 Tavily 做事实核查
  5. 输出 ReviewResult 对象

模型选择：deepseek-reasoner
  审核需要细致分析（找隐藏的极限词、评估口语化程度），用推理模型更准确。

审核结果决定流水线走向：
  没有 P0/P1 → passed=true → 进入 done，输出终稿
  有 P0/P1    → passed=false → 进入 revise 修改步骤
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from backend.app.agents.base import BaseAgent
from backend.app.schemas.agent import ReviewResult, Issue
from backend.app.core.config import get_settings
from backend.app.tracker.langfuse import trace_agent

logger = logging.getLogger(__name__)


class ReviewAgent(BaseAgent):
    """审核 Agent —— 四维审核 + Issue 分级。

    输入：state 中的 script.content / style
    输出：state["review"] = ReviewResult 对象
    """

    def __init__(self):
        super().__init__(model_name=get_settings().deepseek_reasoner_model)

    def _fact_check(self, content: str) -> str:
        """用 Tavily 做事实核查（可选）。

        把脚本中的关键声明拿去搜索，检验真实性。
        搜索失败不阻塞，静默返回空字符串。

        Args:
            content: 脚本全文

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
                query=f"事实核查: {content[:200]}",
                search_depth="basic",
                max_results=2,
            )
            summaries = [r.get("content", "")[:200] for r in result.get("results", [])]
            if summaries:
                logger.debug(f"Tavily 事实核查成功 | 结果数={len(summaries)}")
            else:
                logger.debug("Tavily 事实核查无结果")
            return "\n".join(summaries) if summaries else ""
        except Exception as e:
            logger.warning(f"Tavily 事实核查失败（降级跳过）| error={e}")
            return ""

    @trace_agent("review")
    def run(self, state: dict) -> dict:
        """执行审核逻辑。

        流程：
          1. 读取脚本全文 + 风格
          2. 调 Tavily 做事实核查（可选）
          3. 拼 system prompt（审核维度 + 分级标准 + JSON 格式示例）
          4. 调 LLM → 提取 JSON → 转 ReviewResult 对象
          5. 写回 state["review"]

        Args:
            state: 流水线状态字典，包含 script(含 content) / style

        Returns:
            更新后的 state，包含 review 字段
        """
        script = state.get("script", {})
        content = script.get("content", "")
        style = state.get("style", "知识")

        # 第 1 步：事实核查（有 key 才生效）
        fact_check = self._fact_check(content)
        fact_text = f"\n事实核查参考：\n{fact_check}" if fact_check else ""

        # 第 2 步：拼 system prompt
        # 四个审核维度，每个 25 分，总分 100
        system = f"""你是严格的短视频脚本审核编辑。审核4个维度，每维25分：
1.信息量 2.口语化 3.合规性(极限词/医疗断言) 4.可用率

风格：{style}{fact_text}

Issue分级：P0=合规必改 P1=事实必改 P2=风格建议
passed=true表示没有P0和P1

严格按JSON格式输出（不要输出其他内容）：
```json
{{"passed":true,"issues":[{{"severity":"P0","category":"compliance","location":"原文片段","description":"问题描述","suggestion":"修改建议"}}],"score":85,"dimension_scores":{{"information":22,"oral":20,"compliance":25,"usability":18}},"checks":{{"compliance":true,"facts":true,"style":true}}}}
```"""

        # 第 3 步：调 LLM → 解析 → 转 ReviewResult 对象
        messages = [SystemMessage(content=system), HumanMessage(content=f"请审核以下脚本：\n\n{content}")]
        review = self._invoke(messages, ReviewResult, state)

        # 第 4 步：兜底 —— 解析失败时报系统级 P0 问题
        if review is None:
            review = ReviewResult(
                passed=False,
                issues=[Issue(
                    severity="P0",
                    category="system",
                    location="",
                    description="审核Agent解析失败，请人工审核",
                    suggestion="手动检查脚本内容",
                )],
                score=0,
            )

        state["review"] = review.model_dump()
        return state
