"""
API 路由定义 —— 整个后端唯一的 HTTP 接口层。

本模块包含两个端点：
  POST /generate — 脚本生成流水线（核心业务）
  GET  /health   — 健康检查

POST /generate 设计要点：
  同一个接口支持两种调用方式，通过请求体字段自动区分：

  1. 首次调用：{ topic, style, duration, auto_mode }
     └─ 创建初始 state，执行流水线第一步（策划）

  2. 确认调用：{ confirm_action, feedback, state }
     └─ 恢复上次 state，根据 confirm_action 继续执行下一步

  为什么合并成一个接口而不是拆成 /generate 和 /confirm？
    因为两步用的是同一个流水线 (pipeline)，拆开会重复差不多的逻辑。
    通过 body 中是否有 topic 或 confirm_action 来区分更简洁。

  为什么 state 要在请求/响应中来回传？
    HTTP 本身是无状态的（每次请求独立）。
    而流水线是有状态的（需要知道当前在第几步、数据积累到哪了）。
    解决办法：后端把 state 序列化返回给前端，前端原样保存。
    下次请求时随参数一起发回，后端恢复状态继续执行。
    这就是 "REST API 驱动有状态流水线" 的标准做法。
"""

import logging
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import ValidationError
from backend.app.schemas.request import GenerateRequest, ConfirmRequest
from backend.app.schemas.response import GenerateResponse, StepInfo
from backend.app.api.deps import get_pipeline, limiter
from backend.app.pipeline.orchestator import init_state

logger = logging.getLogger(__name__)

# APIRouter 是 FastAPI 的"子应用"。
# 可以理解为"路由器"：它管理一组相关的端点。
# 在 main.py 中通过 app.include_router(router) 挂载到主应用。
# prefix="" 表示所有路径不加前缀。
router = APIRouter(prefix="")


# ============================================================
# 辅助函数：state 字典 → API 响应对象
# ============================================================
def _state_to_response(state: dict) -> GenerateResponse:
    """将内部 state 字典转换为前端可消费的 JSON 响应。

    这个函数做了两件重要的事：
    1. 从 state 中提取前端需要的结构化字段（steps/outline/script 等）
    2. 清理内部字段（_agents、_elapsed、_steps 等），
       这些字段要么不可序列化（Agent 对象），要么前端不需要，
       打包前必须移除。

    Args:
        state: 流水线内部状态字典，可能包含 _agents/_steps/_elapsed 等内部字段

    Returns:
        GenerateResponse: 过滤和格式化后的响应对象，可直接 JSON 序列化
    """
    # Step 1: 取出并解析步骤状态列表。
    # _steps 是 orchestrator._build_step_list() 生成的。
    # 每个元素可能是 dict 或 StepInfo 对象，统一转成 StepInfo。
    steps = [
        StepInfo(**s) if isinstance(s, dict) else s
        for s in state.pop("_steps", [])
    ]

    # Step 2: 取出累积耗时
    elapsed = state.pop("_elapsed", 0)

    # Step 3: 删除 Agent 实例（Python 对象不能被 JSON 序列化）。
    # 下次请求时 orchestrator 检测到 _agents 不在 state 中，
    # 会自动重新创建 Agent 实例。
    state.pop("_agents", None)

    # Step 4: 构建干净的 state 副本。
    # 所有 _ 开头的键都是内部字段，不暴露给前端。
    # 只保留业务数据：topic/style/duration/outline/script/review 等。
    serializable_state = {
        k: v for k, v in state.items()
        if not k.startswith("_")
    }

    # Step 5: 组装响应
    return GenerateResponse(
        step=state.get("step", "plan"),
        steps=steps,
        outline=state.get("outline"),
        script=state.get("script"),
        review=state.get("review"),
        revision_count=state.get("revision_count", 0),
        grade=state.get("grade", "normal"),
        needs_human=state.get("needs_human", False),
        unresolved_issues=state.get("unresolved_issues", []),
        elapsed_time=elapsed,
        state=serializable_state,
    )


# ============================================================
# 核心端点：POST /generate
# ============================================================
@router.post("/generate", response_model=GenerateResponse)
@limiter.limit("10/minute")   # 同一 IP 每分钟最多 10 次生成请求
async def generate_script(
    request: Request,
    body: dict = Body(...),
    pipeline=Depends(get_pipeline),
):
    """生成口播脚本 —— 多 Agent 流水线的 HTTP 入口。

    两种调用方式：

    【方式一：首次调用】
      前端发送：{ "topic": "打工人如何保持精力", "style": "知识", "duration": 120, "auto_mode": true }
      后端处理：创建初始 state → 执行策划 Agent → 返回大纲 + 新的 state

    【方式二：确认调用】
      前端发送：{ "confirm_action": "continue", "feedback": "", "state": {上次返回的 state} }
      后端处理：恢复 state → 根据 state["step"] 执行下一步 → 返回新结果 + state

    参数说明：
      body:     请求体（dict），通过 Body(...) 声明为必填
      pipeline: 通过 Depends 注入的编排器函数（来自 deps.get_pipeline）

    为什么用 dict 而不是 Union[GenerateRequest, ConfirmRequest]？
      FastAPI 对 Body() 中的 Union 类型支持不稳定（遇到过 500 错误）。
      改用 dict 手动判断字段，更可靠。
    """
    # ---------- 分支 A：首次调用（有 topic）----------
    if "topic" in body:
        # 用 Pydantic 校验参数（类型 + 范围）
        try:
            req = GenerateRequest(**body)
        except ValidationError as e:
            # 参数不符合要求 → 422 Unprocessable Entity
            logger.warning(f"首次调用参数校验失败: {e}")
            raise HTTPException(status_code=422, detail=f"参数校验失败: {e}")
        logger.info(f"首次调用 | topic={req.topic} | style={req.style} | duration={req.duration}s | auto={req.auto_mode}")

        # 题目不能是纯空格
        if not req.topic.strip():
            raise HTTPException(status_code=422, detail="选题不能为空")

        # 创建初始 state 字典
        # init_state 做的事：
        #   step="plan", step 以外所有数据字段（outline/script/review）初始化为 None
        state = init_state(
            topic=req.topic.strip(),
            style=req.style,
            duration=req.duration,
            auto_mode=req.auto_mode,
        )

    # ---------- 分支 B：确认调用（有 confirm_action）----------
    elif "confirm_action" in body:
        try:
            confirm = ConfirmRequest(**body)
        except ValidationError as e:
            logger.warning(f"确认调用参数校验失败: {e}")
            raise HTTPException(status_code=422, detail=f"参数校验失败: {e}")

        # 从请求中恢复上次的 state
        state = confirm.state
        # 把确认动作和反馈写回 state，流水线下一步会用
        state["confirm_action"] = confirm.confirm_action
        state["feedback"] = confirm.feedback
        logger.info(f"确认调用 | action={confirm.confirm_action} | step={state.get('step', '?')}")

        # 如果已经是完成状态，不再执行，直接返回
        if state.get("step") == "done":
            logger.info("流水线已完成，直接返回")
            return _state_to_response(state)

    # ---------- 都不是 → 422 ----------
    else:
        logger.warning("请求体既无 topic 也无 confirm_action")
        raise HTTPException(
            status_code=422,
            detail="请传入 topic（首次生成）或 confirm_action+state（确认操作）"
        )

    # ---------- 执行流水线 ----------
    # pipeline 就是 orchestrator.run_pipeline
    # 它读到 state["step"]，执行对应的 Agent，推进一步，break 返回。
    # 返回值是更新后的 state（step 已指向下一步）。
    state = pipeline(state)

    # 记录流水线执行结果
    elapsed = state.get("_elapsed", 0)
    grade = state.get("grade", "normal")
    revision_count = state.get("revision_count", 0)
    logger.info(
        f"流水线执行完毕 | step={state.get('step', '?')} | grade={grade} | "
        f"revisions={revision_count} | elapsed={elapsed:.1f}s"
    )

    return _state_to_response(state)
