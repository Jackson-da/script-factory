"""
编排器 —— 用 while 循环 + dict 实现的自定义状态机。

为什么不用 LangGraph？
  LangGraph 适合复杂分支/并行/条件路由的 Agent 图。
  本项目是线性流水线（策划→写作→审核→修改），只有两种分支：
    1. auto_mode=true → 全自动依次执行
    2. auto_mode=false → 策划完成 → 暂停等人确认
  用 while + dict 实现比 LangGraph 更轻量、更直观。

设计原则：
  - 每次 HTTP 请求只执行流水线的一步（通过 break 控制）
  - 步骤之间通过 state dict 传递数据（无状态 → 有状态）
  - 前端负责保存 state 并在下次请求时传回，实现"跨请求状态保持"
  - Agent 不知道自己前面是谁、后面是谁，只从 state 读数据、写回 state

state dict 是什么？
  一个普通的 Python dict，承载流水线所有数据：
  {
    "step": "write",           # 当前步骤名
    "topic": "打工人如何保持精力",
    "style": "知识",
    "outline": {...},          # 策划产出
    "script": {...},           # 写作产出
    "review": {...},           # 审核产出
    "_agents": {...},          # Agent 实例缓存（不暴露给前端）
    "_steps": [...],           # 步骤状态列表（暴露给前端）
    "_elapsed": 12.5,          # 累积耗时
  }
"""

import logging
import time
from backend.app.agents.planning import PlanningAgent
from backend.app.agents.writing import WritingAgent
from backend.app.agents.review import ReviewAgent
from backend.app.agents.revision import RevisionAgent
from backend.app.guardrails.compliance import run_compliance_check

logger = logging.getLogger(__name__)

# 最大修改轮次 —— 超过此值即使有未解决问题也降级输出，避免死循环
MAX_REVISIONS = 3
# 最低通过分数 —— 即使没有 P0/P1 硬伤，总分低于此值也必须修改
MIN_PASS_SCORE = 90


# ============================================================
# 辅助函数：构建步骤状态列表
# ============================================================
def _build_step_list(state: dict) -> list[dict]:
    """根据 review_rounds 动态生成步骤列表，展示审核↔修改的完整历史。

    不再固定四个步骤，而是：
      plan → write → review_1 → (revise_1) → review_2 → (revise_2) → ...

    修改步骤只在"审核不通过且实际跑过修改"时才出现。
    """
    steps = [
        {"name": "plan",   "status": "idle", "label": "策划"},
        {"name": "write",  "status": "idle", "label": "写作"},
    ]
    current = state.get("step", "plan")
    review_rounds = state.get("review_rounds", [])
    revision_count = state.get("revision_count", 0)

    # ---- 已完成：所有步骤标 done ----
    if current == "done":
        steps[0]["status"] = "done"
        steps[1]["status"] = "done"
        for r in review_rounds:
            steps.append({"name": f"review_{r['round']}", "status": "done", "label": f"审核{r['round']}"})
            if r.get("revised_script"):
                steps.append({"name": f"revise_{r['round']}", "status": "done", "label": f"修改{r['round']}"})
        return steps

    # ---- 等待确认：只有策划 done ----
    if current == "wait_confirm":
        steps[0]["status"] = "done"
        steps[0]["label"] = "策划 ✓"
        return steps

    # ---- 进行中 ----
    # plan / write 的状态根据当前 step 判断
    if current == "plan":
        steps[0]["status"] = "active"
    elif current == "write":
        steps[0]["status"] = "done"
        steps[1]["status"] = "active"
    else:
        # 已进入 review/revise 阶段，plan 和 write 必然已完成
        steps[0]["status"] = "done"
        steps[1]["status"] = "done"

    for r in review_rounds:
        round_num = r["round"]
        is_last = (round_num == len(review_rounds))
        steps.append({"name": f"review_{round_num}", "status": "done", "label": f"审核{round_num}"})
        if r.get("revised_script"):
            # 这轮改过了，如果紧接着是下一轮审核，标 done；否则 active
            status = "active" if (is_last and current == "review") else "done"
            steps.append({"name": f"revise_{round_num}", "status": status, "label": f"修改{round_num}"})
        elif is_last and current == "revise":
            # 刚审核完不通过，马上要修改
            steps.append({"name": f"revise_{round_num}", "status": "active", "label": f"修改{round_num}"})

    # 如果是 review 步骤且当前轮还不在 review_rounds 里（即将执行的新一轮审核）
    if current == "review" and revision_count == len(review_rounds):
        next_round = len(review_rounds) + 1
        steps.append({"name": f"review_{next_round}", "status": "active", "label": f"审核{next_round}"})

    return steps


# ============================================================
# 核心函数：执行流水线一步
# ============================================================
def run_pipeline(state: dict) -> dict:
    """执行流水线的下一步。

    每次 HTTP 请求调用一次，只往前走一步（通过 break 保证）。
    哪个 Agent 被执行由 state["step"] 决定。

    执行流程（以策划为例）：
      1. 读取 step
      2. 调用对应 Agent
      3. 更新 step 指向下一步
      4. break 退出循环

    为什么 while 循环里每次只跑一次就 break？
      一次 HTTP 请求只跑一步 → 前端每次都能拿到进度更新。
      如果一次请求跑完全程，前端要等 30-60 秒才能看到结果，
      中间看不到任何进度，体验很差。

    Args:
        state: 流水线状态字典（包含 step、数据、Agent 实例等）

    Returns:
        更新后的 state 字典（step 已指向下一步）
    """
    start_time = time.time()

    # ---------- 首次调用时初始化 Agent ----------
    # _agents 是内部字段，不会被序列化返回给前端。
    # 但同一个请求内（单次 pipeline 调用）可能会多次用到同一个 Agent
    # （比如 review → revise → review 循环），缓存避免重复创建。
    if "_agents" not in state:
        state["_agents"] = {
            "planning": PlanningAgent(),
            "writing": WritingAgent(),
            "review": ReviewAgent(),
            "revision": RevisionAgent(),
        }
        state["revision_count"] = state.get("revision_count", 0)
        state.setdefault("review_rounds", [])  # 审核/修改轮次历史
        # 兜底：如果 step 不在已知列表中，强制从 plan 开始
        if state["step"] not in ("plan", "wait_confirm", "write", "review", "revise", "done"):
            state["step"] = "plan"

    agents = state["_agents"]

    # ---------- 状态机主循环 ----------
    # while 循环确保自动模式下可以连续执行多步。
    # 但由于每个分支最后都有 break（除了自动模式 plan→write 这种情况），
    # 每次请求实际只执行一步。
    while state["step"] != "done":
        step = state["step"]

        # ======== 策划步骤：生成大纲 ========
        if step == "plan":
            # 调策划 Agent：搜热点 + 调 LLM → 输出结构化大纲
            state = agents["planning"].run(state)

            if state.get("auto_mode", True):
                # 全自动模式：设下一步为写作，break 返回给前端
                # （之前少写了 break，导致 plan 跑完不返回，while 循环立刻进 write，
                #   一次请求跑了两步，前端看到策划和写作瞬间一起变绿）
                state["step"] = "write"
            else:
                # 人工确认模式：暂停，等前端传回确认信号
                state["step"] = "wait_confirm"
            break   # 一次请求只推进一步，把当前进度返回前端

        # ======== 等待确认步骤：只在前端发回 confirm_action 时才进入 ========
        elif step == "wait_confirm":
            action = state.get("confirm_action", "continue")

            if action == "continue":
                # 用户说"没问题，继续" → 进入写作
                state["step"] = "write"
            elif action == "replan":
                # 用户说"重新策划，要求是 XXX" → 清空大纲，重走策划
                state["outline"] = None
                state["step"] = "plan"
            elif action == "revise_outline":
                # 用户说"按我的 feedback 修改大纲" → 重走策划（带 feedback）
                state["step"] = "plan"

            # 不管哪种操作，都暂停等下一次 HTTP 请求
            break

        # ======== 写作步骤：大纲 → 口播脚本 ========
        elif step == "write":
            state = agents["writing"].run(state)
            # 护栏 ①：写作完成后立即执行正则合规检测
            # 正则 100% 拦截极限词/医疗断言/政治敏感，不依赖 LLM 自觉
            script_content = state.get("script", {}).get("content", "")
            if script_content:
                compliance_result = run_compliance_check(script_content)
                issues_found = compliance_result.get("issues", [])
                state["_compliance_issues"] = issues_found
                if issues_found:
                    logger.warning(f"护栏① 写作后合规检测命中 {len(issues_found)} 条")
            state["step"] = "review"
            logger.info(f"step: write → review")
            break   # 暂停，让前端展示进度

        # ======== 审核步骤：四维打分 + 问题分级 ========
        elif step == "review":
            state = agents["review"].run(state)

            review = state.get("review", {})
            issues = review.get("issues", [])

            # 护栏 ③：合并正则合规检测结果到 LLM 审核结果
            # 正则做硬拦截（100% 拦截率），LLM 做语义补充，两条防线互补
            compliance_issues = state.pop("_compliance_issues", [])
            if compliance_issues:
                issues = list(issues) + compliance_issues
                review["issues"] = issues
                # 有合规命中时更新 passed 状态
                review["passed"] = False
                state["review"] = review
                logger.warning(f"护栏③ 审核阶段合并合规问题 {len(compliance_issues)} 条")

            # 存一轮审核快照（给前端展示轮次历史）
            round_num = len(state.setdefault("review_rounds", [])) + 1
            state["review_rounds"].append({
                "round": round_num,
                "review": state.get("review"),
                "revised_script": None,  # 还没改，修改完成后补上
            })

            # 分离 P0/P1（必须改）和 P2（仅记录）
            must_fix = [i for i in issues if i.get("severity") in ("P0", "P1")]
            score = review.get("score", 0)

            # 分数过低但没有硬伤 → 从低分维度生成修改建议
            if not must_fix and score < MIN_PASS_SCORE:
                dims = review.get("dimension_scores", {})
                # 找出低于 20 分的维度（满分 25），这些是拖后腿的
                weak_dims = [
                    f"{name}（{dims.get(key, 0)}/25）"
                    for key, name in [
                        ("information", "信息量不足"),
                        ("oral", "不够口语化"),
                        ("compliance", "合规性偏低"),
                        ("usability", "可用率偏低"),
                    ]
                    if dims.get(key, 0) < 20
                ]
                if weak_dims:
                    synthetic = {
                        "severity": "P1",
                        "category": "style",
                        "location": "全文",
                        "description": f"综合评分仅 {score} 分（最低通过线 {MIN_PASS_SCORE}），以下维度严重不足：{'；'.join(weak_dims)}",
                        "suggestion": "请针对上述低分维度整体优化脚本，提升内容质量和表达效果",
                    }
                    must_fix.append(synthetic)
                    issues.append(synthetic)
                    review["issues"] = issues
                    state["review"] = review
                logger.info(f"总分 {score} < {MIN_PASS_SCORE}，从弱维度生成 {len(must_fix)} 条修改要求")

            if not must_fix:
                # 没有要改的 → 通过，输出终稿
                state["final_script"] = state.get("script")
                state["grade"] = "normal"
                state["step"] = "done"
                logger.info(f"审核通过（分数 {score}，{len(issues)} 个 P2 建议仅记录）→ done")

            elif state.get("revision_count", 0) >= MAX_REVISIONS:
                # 改了 3 次还有问题 → 不再改了，降级输出
                state["final_script"] = state.get("script")
                state["unresolved_issues"] = must_fix
                state["needs_human"] = True
                state["grade"] = "degraded"
                state["step"] = "done"
                logger.warning(f"降级输出 | {len(must_fix)} 个 P0/P1 未解决（已达 {MAX_REVISIONS} 轮上限）")

            else:
                # 有问题且还有修改额度 → 进入修改步骤
                state["step"] = "revise"
                logger.info(f"审核不通过（{len(must_fix)} 个 P0/P1 需修改，分数 {score}）→ revise（第 {state.get('revision_count', 0) + 1} 轮）")

            break   # 暂停

        # ======== 修改步骤：只改 P0/P1，保留原文风格 ========
        elif step == "revise":
            state = agents["revision"].run(state)
            state["revision_count"] = state.get("revision_count", 0) + 1
            # 把改完的脚本记到当前轮的 revised_script
            if state.get("review_rounds"):
                state["review_rounds"][-1]["revised_script"] = state.get("script")
            # 护栏 ②：修改完成后再次执行合规检测
            # 防止 LLM 修改时引入新的违规词（如 "最好"→"极致"）
            script_content = state.get("script", {}).get("content", "")
            if script_content:
                compliance_result = run_compliance_check(script_content)
                issues_found = compliance_result.get("issues", [])
                state["_compliance_issues"] = issues_found
                if issues_found:
                    logger.warning(f"护栏② 修改后合规检测命中 {len(issues_found)} 条")
            state["step"] = "review"   # 改完回到审核，形成 review↔revise 循环
            rc = state.get("revision_count", 0)
            logger.info(f"step: revise → review（第 {rc} 轮修改完成）")
            break   # 暂停

        # ======== 未知步骤 → 兜底结束 ========
        else:
            state["step"] = "done"
            break

    # ---------- 更新内部元信息 ----------
    # 累积耗时（后续请求的耗时也加进去）
    elapsed = time.time() - start_time
    state["_elapsed"] = state.get("_elapsed", 0) + elapsed

    # 生成步骤状态列表（前端进度条数据）
    state["_steps"] = _build_step_list(state)

    return state


# ============================================================
# 辅助函数：创建初始状态
# ============================================================
def init_state(
    topic: str,
    style: str = "知识",
    duration: int = 120,
    auto_mode: bool = True
) -> dict:
    """创建流水线的初始状态字典。

    这是每次"首次调用"的起点。
    所有数据字段初始化为 None，Agent 一步一步填充。

    Args:
        topic:     选题主题（前端 InputForm 的输入）
        style:     账号风格，默认"知识"
        duration:  目标时长(秒)，默认 120
        auto_mode: 是否全自动（true=一口气跑完，false=策划后暂停）

    Returns:
        dict: 初始状态字典，step 始终为 "plan"
    """
    return {
        "step": "plan",              # 从策划开始
        "topic": topic,
        "style": style,
        "duration": duration,
        "auto_mode": auto_mode,
        "confirm_action": "",        # 用户确认动作（二次调用时填入）
        "feedback": "",              # 用户反馈（二次调用时填入）
        "outline": None,             # 策划 Agent 产出（执行后填入）
        "script": None,              # 写作/修改 Agent 产出（执行后填入）
        "review": None,              # 审核 Agent 产出（执行后填入）
        "revision_count": 0,         # 修改次数计数器
        "final_script": None,        # 终稿（done 时填入）
        "needs_human": False,        # 是否需要人工处理
        "grade": "normal",           # 最终等级
        "unresolved_issues": [],     # 未解决的问题列表
        "review_rounds": [],         # 审核/修改轮次历史（前端展示用）
        "hotspot": [],              # Tavily 搜索的热点信息 [{title, content, url}]
        "_elapsed": 0,               # 内部：累积耗时
    }
