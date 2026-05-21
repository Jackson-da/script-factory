"""
修改 Agent —— 流水线第四步（可选，仅在审核发现 P0/P1 问题时触发）。

职责：
  1. 读原始脚本 + P0/P1 问题列表
  2. 逐条修改问题（只改有问题的地方，其他地方一个字不动）
  3. P2 风格建议仅供参考，不用强制修改
  4. 输出修改后的 Script 对象

设计原则：
  只改 P0/P1（合规和事实问题必须改）
  不改 P2（风格建议，改不改由修改 Agent 自己判断）
  保留原文的语感、节奏、格式标记

模型选择：deepseek-chat
  修改是执行型任务（根据清单逐一修改），速度快即可。
"""

from langchain_core.messages import SystemMessage, HumanMessage
from backend.app.agents.base import BaseAgent
from backend.app.schemas.agent import Script
from backend.app.tracker.langfuse import trace_agent


class RevisionAgent(BaseAgent):
    """修改 Agent —— 只改 P0/P1，保留原文风格。

    输入：state 中的 script.content / review.issues
    输出：state["script"] = 修改后的 Script 对象
    """

    def __init__(self):
        super().__init__()   # deepseek-chat

    @trace_agent("revision")
    def run(self, state: dict) -> dict:
        """执行修改逻辑。

        流程：
          1. 读取脚本 + 审核问题
          2. 按 severity 分类：P0/P1 必须改，P2 仅供参考
          3. 如果没有必须改的问题，直接返回（不做无用功）
          4. 拼 system prompt（问题清单 + 修改规则 + JSON 格式示例）
          5. 调 LLM → 提取 JSON → 转 Script 对象
          6. 写回 state["script"]

        Args:
            state: 流水线状态字典，包含 script(含 content) / review(含 issues)

        Returns:
            更新后的 state，script 字段已替换为修改后的版本
        """
        script = state.get("script", {})
        content = script.get("content", "")
        review = state.get("review", {})
        all_issues = review.get("issues", [])

        # 第 1 步：分类问题
        must_fix = [i for i in all_issues if i.get("severity") in ("P0", "P1")]
        style_note = [i for i in all_issues if i.get("severity") == "P2"]

        # 如果没有必须改的问题，跳过（虽然理论上不会走到这里）
        # 因为 orchestrator 在 review→done 时已经判了 passed=true
        if not must_fix:
            return state

        # 第 2 步：构造修改清单文本
        fix_list = ""
        for i, issue in enumerate(must_fix, 1):
            sev = issue.get('severity', '')
            desc = issue.get('description', '')
            suggestion = issue.get('suggestion', '')
            fix_list += f"\n{i}.【{sev}】{desc}"
            fix_list += f"\n   建议: {suggestion}"

        # 第 3 步：构造风格建议文本（仅参考）
        note_list = ""
        if style_note:
            note_list = "\n风格建议（仅参考）："
            for issue in style_note:
                note_list += f"\n· {issue.get('description', '')}"

        # 第 4 步：拼 system prompt
        system = f"""你是短视频脚本修改编辑。修改规则：
1.只改列出的问题，其他地方不动
2.保持原文语感和节奏
3.修改后字数与原文基本一致

修改要求：{fix_list}
{note_list}

严格按JSON格式输出修改后的完整脚本（不要输出其他内容）：
```json
{{"content":"修改后的完整口播脚本全文","duration_estimate":{len(content) // 2},"tone_markers":["[快]","[慢]","[重音]"]}}
```"""

        # 第 5 步：调 LLM → 解析 → 转 Script 对象
        messages = [SystemMessage(content=system), HumanMessage(content=f"原文脚本：\n\n{content}\n\n输出修改后的脚本JSON。")]
        new_script = self._invoke(messages, Script, state)

        # 第 6 步：兜底 —— 解析失败时保留原文
        if new_script is None:
            new_script = Script(
                content=content,   # 至少原文不丢
                duration_estimate=script.get("duration_estimate", len(content) // 2),
                tone_markers=[],
            )

        state["script"] = new_script.model_dump()
        return state
