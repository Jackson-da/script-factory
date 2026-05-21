"""
Agent 之间传递的 Pydantic 数据模型。

每个模型定义了 Agent 产出的数据结构：
  Outline       → 策划 Agent 产出的大纲
  Script        → 写作/修改 Agent 产出的口播脚本
  Issue         → 审核 Agent 发现的问题
  ReviewResult  → 审核 Agent 的完整审核结果

这些模型的作用：
  1. 类型安全：IDE 有完整的类型提示，防止字段名拼错
  2. 序列化：model_dump() 把对象转 dict 写入 state（dict 才能 JSON 序列化）
  3. 数据校验：如果 LLM 少字段或类型不对，Pydantic 会报错（被 _invoke 捕获走兜底）

为什么 Agent 之间用 dict 传数据而不是 Pydantic 对象？
  因为 state 本身是 dict，需要能在 HTTP 中 JSON 序列化。
  Agent 内部用 Pydantic 保证类型安全，传给 state 时 dump 成 dict。
  下一个 Agent 从 state 读 dict，按需读取字段即可。
"""

from pydantic import BaseModel, Field


# ============================================================
# 策划 Agent → Outline（大纲）
# ============================================================
class Section(BaseModel):
    """大纲中的一个段落。

    每段包含标题和要点列表。
    talking_points 是具体要说的话，不是抽象描述。
    比如 "少吃高糖食物，多吃蛋白质" 而不是 "饮食建议"
    """
    heading: str = Field(..., description="段落标题")
    talking_points: list[str] = Field(default_factory=list, description="要点列表")


class Outline(BaseModel):
    """策划 Agent 产出的大纲结构。

    大纲是脚本的骨架，后续写作 Agent 按这个结构填充。
    key_phrases（金句）至少 3 条，用于结尾引发转赞评。
    """
    title: str = Field(..., description="脚本标题")
    hook: str = Field(..., description="开头钩子，3秒内抓住注意力")
    sections: list[Section] = Field(..., description="大纲段落列表")
    key_phrases: list[str] = Field(default_factory=list, description="金句列表，不少于3条")
    estimated_duration: int = Field(..., description="预估总时长(秒)")


# ============================================================
# 写作/修改 Agent → Script（口播脚本）
# ============================================================
class Script(BaseModel):
    """写作/修改 Agent 产出的口播脚本。

    content:        口播稿全文，含节奏标记（[快]/[慢]/[重音]/[停顿1s]）
    duration_estimate: 实际时长估算
    tone_markers:      用到的节奏标记类型列表
    """
    content: str = Field(..., description="口播稿全文，含节奏标记")
    duration_estimate: int = Field(..., description="预估时长(秒)")
    tone_markers: list[str] = Field(default_factory=list, description="节奏标记: 快/慢/重音等")


# ============================================================
# 审核 Agent → Issue + ReviewResult
# ============================================================
class Issue(BaseModel):
    """审核 Agent 发现的单个问题。

    严重级别：
      P0 = 合规/法律问题（极限词、医疗断言、政治敏感），必须修改
      P1 = 事实/数据错误，必须修改
      P2 = 风格/表达建议，仅记录，修改 Agent 可自行判断是否采纳

    category 问题类型：
      compliance(合规) / facts(事实) / style(风格) / plagiarism(抄袭)
    """
    severity: str = Field(..., description="严重级别: P0=合规(必改) P1=事实(必改) P2=风格(仅记录)")
    category: str = Field(..., description="问题类型: compliance/facts/style/plagiarism")
    location: str = Field(..., description="出问题的原文片段")
    description: str = Field(..., description="问题描述，说明为什么是问题")
    suggestion: str = Field(default="", description="修改建议")


class ReviewResult(BaseModel):
    """审核 Agent 产出的完整审核结果。

    passed:        是否通过（没有 P0/P1 问题则 passed=true）
    issues:        问题列表
    score:         综合评分（0-100）
    dimension_scores: 四维分项评分
    checks:          三项检查通过情况（合规/事实/风格）
    """
    passed: bool = Field(..., description="是否通过审核(P0/P1全清零则通过)")
    issues: list[Issue] = Field(default_factory=list, description="发现的问题列表")
    score: float = Field(..., description="综合评分 0-100")
    dimension_scores: dict = Field(
        default_factory=lambda: {
            "information": 0,   # 信息量
            "oral": 0,          # 口语化
            "compliance": 0,    # 合规性
            "usability": 0,     # 可用率
        },
        description="四维度评分"
    )
    checks: dict = Field(
        default_factory=lambda: {
            "compliance": False,  # 合规检查
            "facts": False,       # 事实核查
            "style": False,       # 风格检查
        },
        description="三项检查通过情况"
    )
