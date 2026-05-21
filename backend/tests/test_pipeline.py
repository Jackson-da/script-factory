"""编排器单元测试 —— 覆盖 init_state、_build_step_list、run_pipeline mock。"""

import pytest
from unittest.mock import MagicMock, patch
from backend.app.pipeline.orchestator import init_state, run_pipeline, _build_step_list


# ============================================================
# init_state 测试
# ============================================================
class TestInitState:
    """测试初始状态创建。"""

    def test_default_values(self):
        """默认值：style=知识, duration=120, auto_mode=True。"""
        state = init_state(topic="测试选题")
        assert state["topic"] == "测试选题"
        assert state["style"] == "知识"
        assert state["duration"] == 120
        assert state["auto_mode"] is True
        assert state["step"] == "plan"
        assert state["revision_count"] == 0
        assert state["outline"] is None
        assert state["script"] is None

    def test_custom_values(self):
        """自定义参数全部生效。"""
        state = init_state(topic="搞笑段子", style="搞笑", duration=60, auto_mode=False)
        assert state["topic"] == "搞笑段子"
        assert state["style"] == "搞笑"
        assert state["duration"] == 60
        assert state["auto_mode"] is False

    def test_all_fields_initialized(self):
        """所有已知字段都有初始值，避免 KeyError。"""
        state = init_state(topic="测试")
        expected_keys = [
            "step", "topic", "style", "duration", "auto_mode",
            "confirm_action", "feedback", "outline", "script",
            "review", "revision_count", "final_script",
            "needs_human", "grade", "unresolved_issues", "_elapsed",
        ]
        for key in expected_keys:
            assert key in state, f"字段 {key} 缺失"


# ============================================================
# _build_step_list 测试 —— 覆盖所有状态分支
# ============================================================
class TestBuildStepList:
    """测试步骤状态列表生成逻辑（不依赖 LLM）。"""

    # ---------- done 状态 ----------
    def test_done_with_revision(self):
        """done + revision_count>0 → 四个步骤全 done。"""
        state = {"step": "done", "revision_count": 2}
        steps = _build_step_list(state)
        assert all(s["status"] == "done" for s in steps)

    def test_done_without_revision(self):
        """done + revision_count=0 → 修改标为 skipped。"""
        state = {"step": "done", "revision_count": 0}
        steps = _build_step_list(state)
        assert steps[0]["status"] == "done"   # 策划
        assert steps[1]["status"] == "done"   # 写作
        assert steps[2]["status"] == "done"   # 审核
        assert steps[3]["status"] == "skipped"  # 修改

    # ---------- wait_confirm 状态 ----------
    def test_wait_confirm(self):
        """wait_confirm → 策划 done✓，其余 idle。"""
        state = {"step": "wait_confirm"}
        steps = _build_step_list(state)
        assert steps[0]["status"] == "done"
        assert "✓" in steps[0]["label"]
        assert steps[1]["status"] == "idle"
        assert steps[2]["status"] == "idle"
        assert steps[3]["status"] == "idle"

    # ---------- 标准中间步骤 ----------
    def test_plan_active(self):
        """step=plan → 策划 active，其余 idle。"""
        state = {"step": "plan"}
        steps = _build_step_list(state)
        assert steps[0]["status"] == "active"
        assert steps[1]["status"] == "idle"
        assert steps[2]["status"] == "idle"
        assert steps[3]["status"] == "idle"

    def test_write_active(self):
        """step=write → 策划 done，写作 active。"""
        state = {"step": "write"}
        steps = _build_step_list(state)
        assert steps[0]["status"] == "done"
        assert steps[1]["status"] == "active"
        assert steps[2]["status"] == "idle"
        assert steps[3]["status"] == "idle"

    def test_review_active(self):
        """step=review → 策划+写作 done，审核 active。"""
        state = {"step": "review"}
        steps = _build_step_list(state)
        assert steps[0]["status"] == "done"
        assert steps[1]["status"] == "done"
        assert steps[2]["status"] == "active"
        assert steps[3]["status"] == "idle"

    def test_revise_active(self):
        """step=revise → 前三个 done，修改 active。"""
        state = {"step": "revise"}
        steps = _build_step_list(state)
        assert steps[0]["status"] == "done"
        assert steps[1]["status"] == "done"
        assert steps[2]["status"] == "done"
        assert steps[3]["status"] == "active"

    # ---------- 返回结构 ----------
    def test_step_list_length(self):
        """始终返回 4 个步骤。"""
        steps = _build_step_list({"step": "plan"})
        assert len(steps) == 4

    def test_step_names(self):
        """步骤名固定为 plan/write/review/revise。"""
        steps = _build_step_list({"step": "plan"})
        names = [s["name"] for s in steps]
        assert names == ["plan", "write", "review", "revise"]

    def test_step_labels(self):
        """中文标签正确（done 状态不额外加 ✓）。"""
        state = {"step": "done", "revision_count": 1}
        steps = _build_step_list(state)
        assert steps[0]["label"] == "策划"
        assert steps[1]["label"] == "写作"
        assert steps[2]["label"] == "审核"
        assert steps[3]["label"] == "修改"


# ============================================================
# run_pipeline mock 测试 —— 不调真实 LLM
# ============================================================
class TestRunPipelineMock:
    """Mock Agent.run() 来测试编排器状态机逻辑。"""

    def _make_mock_state(self, step="plan", auto_mode=True):
        """构造一个带 mock Agent 的初始 state。"""
        state = init_state(topic="测试选题", auto_mode=auto_mode)
        state["step"] = step
        # 预注入 mock agents
        state["_agents"] = {
            "planning": MagicMock(),
            "writing": MagicMock(),
            "review": MagicMock(),
            "revision": MagicMock(),
        }
        return state

    # ---------- plan 步骤 ----------
    def test_plan_auto_mode_proceeds_to_write(self):
        """全自动模式：plan 完成后 step 变为 write。"""
        state = self._make_mock_state(step="plan", auto_mode=True)
        # mock planning agent 返回 state（不改 step，由编排器改）
        def mock_run(s):
            s["outline"] = {"title": "测试大纲"}
            return s
        state["_agents"]["planning"].run = mock_run

        state = run_pipeline(state)
        assert state["step"] == "write"
        assert state["outline"] is not None

    def test_plan_manual_mode_waits_for_confirm(self):
        """人工确认模式：plan 完成后 step 变为 wait_confirm。"""
        state = self._make_mock_state(step="plan", auto_mode=False)
        def mock_run(s):
            s["outline"] = {"title": "测试大纲"}
            return s
        state["_agents"]["planning"].run = mock_run

        state = run_pipeline(state)
        assert state["step"] == "wait_confirm"

    # ---------- wait_confirm 步骤 ----------
    def test_wait_confirm_continue(self):
        """确认继续 → step 进入 write。"""
        state = self._make_mock_state(step="wait_confirm", auto_mode=False)
        state["confirm_action"] = "continue"
        state = run_pipeline(state)
        assert state["step"] == "write"

    def test_wait_confirm_replan(self):
        """重新策划 → step 回到 plan，outline 清空。"""
        state = self._make_mock_state(step="wait_confirm", auto_mode=False)
        state["outline"] = {"title": "旧大纲"}
        state["confirm_action"] = "replan"
        state = run_pipeline(state)
        assert state["step"] == "plan"
        assert state["outline"] is None

    def test_wait_confirm_revise_outline(self):
        """修改大纲 → step 回到 plan（保留 feedback）。"""
        state = self._make_mock_state(step="wait_confirm", auto_mode=False)
        state["confirm_action"] = "revise_outline"
        state = run_pipeline(state)
        assert state["step"] == "plan"

    # ---------- write 步骤 ----------
    def test_write_proceeds_to_review(self):
        """写作完成 → step 进入 review。"""
        state = self._make_mock_state(step="write", auto_mode=True)
        state["outline"] = {"title": "测试大纲", "hook": "钩子", "sections": [], "key_phrases": []}
        def mock_run(s):
            s["script"] = {"content": "测试脚本内容"}
            return s
        state["_agents"]["writing"].run = mock_run

        state = run_pipeline(state)
        assert state["step"] == "review"
        assert state["script"] is not None

    # ---------- review 分支逻辑 ----------
    def test_review_passed_goes_to_done(self):
        """审核无 P0/P1 → done，final_script 就位。"""
        state = self._make_mock_state(step="review", auto_mode=True)
        state["script"] = {"content": "测试脚本"}
        def mock_run(s):
            s["review"] = {
                "passed": True,
                "issues": [],  # 无 P0/P1
                "score": 85,
            }
            return s
        state["_agents"]["review"].run = mock_run

        state = run_pipeline(state)
        assert state["step"] == "done"
        assert state["final_script"] is not None
        assert state["grade"] == "normal"

    def test_review_has_p0_goes_to_revise(self):
        """审核有 P0 → step 进入 revise。"""
        state = self._make_mock_state(step="review", auto_mode=True)
        state["script"] = {"content": "测试脚本"}
        state["revision_count"] = 0
        def mock_run(s):
            s["review"] = {
                "passed": False,
                "issues": [
                    {"severity": "P0", "category": "compliance", "description": "极限词违规"},
                ],
                "score": 60,
            }
            return s
        state["_agents"]["review"].run = mock_run

        state = run_pipeline(state)
        assert state["step"] == "revise"

    def test_review_p2_only_goes_to_done(self):
        """审核只有 P2 风格建议 → done（P2 不阻塞）。"""
        state = self._make_mock_state(step="review", auto_mode=True)
        state["script"] = {"content": "测试脚本"}
        def mock_run(s):
            s["review"] = {
                "passed": True,
                "issues": [
                    {"severity": "P2", "category": "style", "description": "开头可以更有力"},
                ],
                "score": 82,
            }
            return s
        state["_agents"]["review"].run = mock_run

        state = run_pipeline(state)
        assert state["step"] == "done"

    def test_review_max_revisions_degraded(self):
        """超过 MAX_REVISIONS 还有 P0 → done + degraded。"""
        state = self._make_mock_state(step="review", auto_mode=True)
        state["script"] = {"content": "测试脚本"}
        state["revision_count"] = 3  # = MAX_REVISIONS
        def mock_run(s):
            s["review"] = {
                "passed": False,
                "issues": [
                    {"severity": "P0", "category": "compliance", "description": "还是有极限词"},
                ],
                "score": 55,
            }
            return s
        state["_agents"]["review"].run = mock_run

        state = run_pipeline(state)
        assert state["step"] == "done"
        assert state["grade"] == "degraded"
        assert state["needs_human"] is True
        assert len(state["unresolved_issues"]) == 1

    # ---------- revise 步骤 ----------
    def test_revise_goes_back_to_review(self):
        """修改完成 → 回到 review 形成循环。"""
        state = self._make_mock_state(step="revise", auto_mode=True)
        state["script"] = {"content": "原始脚本"}
        state["review"] = {
            "issues": [{"severity": "P0", "description": "极限词"}]
        }
        state["revision_count"] = 0
        def mock_run(s):
            s["script"] = {"content": "修改后脚本"}
            return s
        state["_agents"]["revision"].run = mock_run

        state = run_pipeline(state)
        assert state["step"] == "review"
        assert state["revision_count"] == 1

    # ---------- 未知 step 兜底 ----------
    def test_unknown_step_falls_back_to_done(self):
        """未知 step → 直接 done 兜底。"""
        state = self._make_mock_state(step="unknown_step")
        state = run_pipeline(state)
        assert state["step"] == "done"

    # ---------- _steps 和 _elapsed ----------
    def test_run_pipeline_sets_steps(self):
        """run_pipeline 后 _steps 字段非空。"""
        state = self._make_mock_state(step="plan", auto_mode=True)
        def mock_run(s):
            s["outline"] = {"title": "大纲"}
            return s
        state["_agents"]["planning"].run = mock_run

        state = run_pipeline(state)
        assert "_steps" in state
        assert len(state["_steps"]) == 4

    def test_run_pipeline_sets_elapsed(self):
        """run_pipeline 后 _elapsed 大于 0。"""
        state = self._make_mock_state(step="plan", auto_mode=True)
        def mock_run(s):
            s["outline"] = {"title": "大纲"}
            return s
        state["_agents"]["planning"].run = mock_run

        state = run_pipeline(state)
        assert state["_elapsed"] > 0
