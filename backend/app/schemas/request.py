"""
FastAPI 请求体 Pydantic 模型定义。

两个请求模型对应前端两种调用场景：
1. GenerateRequest：用户填完表单首次点击"生成脚本"
2. ConfirmRequest： 流水线暂停后用户确认继续/重新策划

Pydantic 在这里的作用：
  - 自动校验：Field(ge=30, le=600) → 时长小于 30 秒直接返回 422
  - 自动文档：FastAPI 的 /docs 页面自动展示字段说明
  - 类型安全：IDE 有完整的类型提示
"""

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """首次生成请求 —— 用户输入选题 + 风格 + 时长。

    示例 JSON（前端发的就是这个格式）：
    {
      "topic": "打工人如何保持精力",
      "style": "知识",
      "duration": 120,
      "auto_mode": true
    }
    """
    # topic 必填，最少 2 字（"AI" 这种太短没意义），最多 200 字
    topic: str = Field(..., min_length=2, max_length=200, description="选题主题")

    # style 可选，默认"知识"风格。前端是下拉框三选一：知识 / 搞笑 / 情感
    style: str = Field(default="知识", description="账号风格: 知识/搞笑/情感")

    # duration 可选，默认 120 秒（2 分钟）。范围限制 30~600 秒
    # ge=30:  大于等于 30 秒（太短没内容）
    # le=600: 小于等于 600 秒（太长不适合口播）
    duration: int = Field(default=120, ge=30, le=600, description="目标时长(秒)")

    # auto_mode 可选，默认 true（全自动，一气呵成）
    # false 时：策划完成后暂停，展示大纲给用户确认，再继续
    auto_mode: bool = Field(default=True, description="True=全自动, False=策划后人工确认")


class ConfirmRequest(BaseModel):
    """确认/继续请求 —— 用户确认大纲或干预流水线方向。

    这个是第二次以及后续调用 /generate 的请求体。
    前端从上次响应中拿到 state 字典，加上 confirm_action 和 feedback，
    封装后再次发回后端，后端恢复上次的状态后继续执行下一步。

    state 这个字段为什么是一个 dict 而不是强类型？
      因为流水线每个步骤填入不同的字段（outline/script/review），
      无法用一个固定的 Pydantic 模型描述所有阶段。
      用 dict 灵活，FastAPI 不做校验，直接透传。

    示例 JSON：
    {
      "confirm_action": "continue",
      "feedback": "",
      "state": { "step": "wait_confirm", "topic": "...", "outline": {...}, ... }
    }
    """
    # confirm_action 必填，三种取值：
    #   "continue"       → 确认大纲，继续写作
    #   "replan"         → 重新策划（带 feedback 说明要求）
    #   "revise_outline" → 修改大纲（不改方向，只调细节）
    confirm_action: str = Field(
        ...,
        description="确认动作: continue(继续) / replan(重新策划) / revise_outline(修改大纲)"
    )

    # feedback 可选，重新策划或修改大纲时把用户的要求传进来
    # 比如 "能不能加一个养生的角度" 或 "金句太水了，换犀利一点的"
    feedback: str = Field(default="", description="用户反馈意见")

    # state 必填，是上次 POST /generate 响应中的 state 字段。
    # 后端收到后恢复到上次的状态，读取 confirm_action 决定下一步怎么走。
    state: dict = Field(..., description="上一轮返回的完整 state 字典")
