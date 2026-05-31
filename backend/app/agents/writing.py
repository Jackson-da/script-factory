"""
写作 Agent —— 流水线第二步。

职责：
  1. 读大纲（title/hook/sections/key_phrases）
  2. 按风格指南写口播脚本
  3. 嵌入节奏标记（[快][慢][重音][停顿1s]）
  4. 输出 Script 对象

模型选择：deepseek-chat
  写作是执行型任务（照着大纲写出文本），不需要深度推理，
  用对话模型速度快、成本低。

风格指南：
  三种风格各有不同的语气、节奏和写作手法，
  通过 STYLE_GUIDES 字典映射到具体指导。
"""

from langchain_core.messages import SystemMessage, HumanMessage
from backend.app.agents.base import BaseAgent
from backend.app.schemas.agent import Script
from backend.app.tracker.langfuse import trace_agent

# 三种账号风格的写作指南
# 每个风格描述语气、节奏、修辞手法，注入到 system prompt 中
STYLE_GUIDES = {
    "搞笑": "语气幽默吐槽，节奏快，多用生活化比喻和网络梗，每30秒至少一个笑点",
    "知识": "像朋友聊天一样讲干货，用「你知道吗」「举个例子」「说白了就是」自然过渡，每说完一个观点立刻接一个具体例子",
    "情感": "语气温暖真诚，第一人称叙事，重情绪共鸣，多用「你知道吗」「你有没有想过」句式",
}

# 口语化强制规则 —— 注入 prompt 防止 LLM 写出作文体
ORAL_RULES = """
【口语化铁律 —— 必须遵守，违者重写】
1. 禁止书面语结构：不要用「A：B」「C：D」「E：F」这种冒号分点格式，这是作文不是人话
2. 禁止论证词汇：不要出现「首先/其次/再次」「综上所述」「从XX角度看」「究其原因」
3. 句式要短：每句不超过25个字，长句拆成短句。口语不是念论文，观众用耳朵听不是用眼睛读
4. 拒绝书面感词汇：把「该」「其」「此」「已」「亦」「均」「即」改成口语说法
5. 多用设问：问句先抛出来再回答，模拟真实聊天节奏。比如「那问题来了——X到底怎么回事？其实就三点」
6. 加语气词：适当加「你看」「说白了」「你猜怎么着」「这事吧」「说真的」让文本有"人味"
7. 每段只讲一个点：讲完就收，不要在同一段里塞三个论点。一段=一个想法+一个例子+一句话收尾

反面教材（这他X绝对不是口播）：
  "国内压力：美债突破35万亿，通胀居高不下，特朗普急需外交成绩单稳住选票"
正确写法（这才是人话）：
  "咱们先看美国那边什么情况。美债，35万亿了。通胀，压都压不住。特朗普现在急啊——他得给选民一个交代，对吧？"

反面教材：
  "国际棋局：俄乌、中东两场冲突拖住美国，中国却成了全球产业链稳压器"
正确写法：
  "再看看国际上。俄乌在打，中东在烧，美国两只脚都陷进去了。而中国呢？全球产业链现在离不了中国。"
"""


class WritingAgent(BaseAgent):
    """写作 Agent —— 口播脚本写手。

    输入：state 中的 outline(大纲) / style(风格) / duration(时长)
    输出：state["script"] = Script 对象（含全文 + 节奏标记）
    """

    def __init__(self):
        super().__init__()   # 默认用 deepseek-chat

    @trace_agent("writing")
    def run(self, state: dict) -> dict:
        """执行写作逻辑。

        流程：
          1. 提取大纲各部分（标题、钩子、段落、金句）
          2. 拼 system prompt（包含风格指南 + 节奏标记要求 + JSON 格式示例）
          3. 调 LLM → 提取 JSON → 转 Script 对象
          4. 写回 state["script"]

        Args:
            state: 流水线状态字典，包含 outline/style/duration

        Returns:
            更新后的 state，包含 script 字段
        """
        outline = state.get("outline", {})
        style = state.get("style", "知识")
        duration = state.get("duration", 120)

        # 获取风格指南（未知风格回退到"知识"）
        style_guide = STYLE_GUIDES.get(style, STYLE_GUIDES["知识"])

        # 第 1 步：把大纲改写为可读文本段落
        sections_text = ""
        for i, s in enumerate(outline.get("sections", []), 1):
            heading = s.get("heading", "")
            points = "；".join(s.get("talking_points", []))
            sections_text += f"\n第{i}段: {heading}\n要点: {points}"

        # 第 2 步：拼 system prompt
        # 包含：风格指南、口语化铁律、目标字数、节奏标记说明、JSON 格式示例
        system = f"""你是{style}类短视频口播写手。

风格指南：{style_guide}

{ORAL_RULES}

目标：约{duration // 2}字，{duration}秒
节奏标记：[快]/[慢]/[重音]/[停顿1s]

大纲：
标题：{outline.get('title', '')}
钩子：{outline.get('hook', '')}
段落：{sections_text}
金句：{'；'.join(outline.get('key_phrases', []))}

严格按JSON格式输出完整口播脚本（不要输出其他内容）：
```json
{{"content":"完整口播稿全文，含[快][慢][重音][停顿1s]等标记","duration_estimate":{duration},"tone_markers":["[快]","[慢]","[重音]"]}}
```"""

        # 第 3 步：调 LLM → 解析 → 转 Script 对象
        messages = [SystemMessage(content=system), HumanMessage(content="输出完整口播脚本JSON。")]
        script = self._invoke(messages, Script, state)

        # 第 4 步：兜底
        if script is None:
            script = Script(content="写作Agent生成失败，请重试", duration_estimate=duration, tone_markers=[])

        state["script"] = script.model_dump()
        return state
