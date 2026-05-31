"""
FastAPI 响应体 Pydantic 模型定义。

每次 POST /generate 后，后端返回一个 GenerateResponse 对象。
前端从中拿到：
  - 步骤进度（steps → PipelineView 渲染进度条）
  - 产出内容（outline/script/review → 对应组件展示）
  - 完整 state（state → 前端保存，下次确认调用时原样传回）

state 字段是这个流水线设计的核心：
  第一次请求：前端不需要 state，后端创建初始 state
  后续请求：前端把上次的 state 传回，后端恢复并继续执行
  这样就实现了"有状态的流水线"通过"无状态的 HTTP API"来驱动。
"""

from pydantic import BaseModel, Field


class StepInfo(BaseModel):
    """流水线中单个步骤的显示信息。

    PipelineView 组件根据 steps 数组渲染进度指示器。
    name   → 步骤机器名（plan/write/review/revise）
    status → idle(灰)/active(蓝)/done(绿) 三种颜色
    label  → 中文标签（策划/写作/审核/修改）
    """
    name: str = Field(..., description="步骤名: plan/write/review/revise")
    status: str = Field(..., description="状态: idle/active/done")
    label: str = Field(..., description="中文标签: 策划/写作/审核/修改")


class GenerateResponse(BaseModel):
    """生成脚本的响应体 —— 每次 POST /generate 的返回值。

    这个模型包含了前端渲染需要的所有信息：
    - step / steps → 流水线进度（PipelineView）
    - outline       → 策划大纲（确认模式下展示）
    - script        → 口播脚本文本（ScriptOutput）
    - review        → 审核结果（评分 + 问题列表）
    - state         → 完整状态，前端保存后下次传回
    """
    # step: 当前流水线走到了哪一步
    #   "plan" / "write" / "review" / "revise" → 正在执行
    #   "wait_confirm" → 暂停，等用户确认
    #   "done"         → 全部完成
    step: str = Field(..., description="当前流水线步骤")

    # steps: 所有步骤的状态列表，前端渲染成进度指示器
    #   例如 [策划done, 写作active, 审核idle, 修改idle]
    steps: list[StepInfo] = Field(default_factory=list, description="所有步骤的状态列表")

    # outline: 策划 Agent 产出的大纲，包含标题/钩子/段落/金句
    outline: dict | None = Field(default=None, description="策划产出的大纲")

    # script: 写作/修改 Agent 产出的口播脚本，含全文和节奏标记
    script: dict | None = Field(default=None, description="生成的脚本")

    # review: 审核 Agent 产出的审核结果，含评分和问题列表
    review: dict | None = Field(default=None, description="审核结果")

    # review_rounds: 审核/修改的完整轮次历史，含每轮审核结果和修改后脚本
    review_rounds: list = Field(default_factory=list, description="审核/修改轮次历史")

    # revision_count: 修改轮次计数，最多 3 轮
    revision_count: int = Field(default=0, description="已修改次数")

    # grade: 最终等级
    #   "normal"   → 审核通过，正常输出
    #   "degraded" → 超过最大修改轮次仍未通过，降级输出
    grade: str = Field(default="normal", description="normal/degraded")

    # needs_human: 是否需要人工介入处理未解决问题
    needs_human: bool = Field(default=False, description="是否需要人工介入")

    # unresolved_issues: 超过 MAX_REVISIONS 后仍未解决的 P0/P1 问题
    unresolved_issues: list = Field(default_factory=list, description="未解决的问题列表")

    # hotspot: Tavily 搜索的热点参考信息（策划阶段展示用）
    hotspot: list = Field(default_factory=list, description="策划阶段搜索的热点参考 [{title, content, url}]")

    # elapsed_time: 从本次调用开始的累积耗时（秒）
    elapsed_time: float = Field(default=0.0, description="已耗时(秒)")

    # state: 完整的流水线内部状态字典。
    # 这是最关键的一个字段 —— 前端不解读它，只保存。
    # 下次调 /generate 确认时原样传回，后端从中恢复流水线状态。
    # 内部字段（_开头的）已在返回前被移除，这里只含前端需要的干净数据。
    state: dict = Field(default_factory=dict, description="完整 state，前端下次调用时回传")


class HealthResponse(BaseModel):
    """健康检查响应。"""
    status: str
    service: str
