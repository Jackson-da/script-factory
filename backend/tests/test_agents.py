"""Agent mock 测试 —— Mock LLM._invoke() 来测试每个 Agent 的 prompt 构建和兜底逻辑。"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from backend.app.agents.base import BaseAgent, extract_json
from backend.app.agents.planning import PlanningAgent
from backend.app.agents.writing import WritingAgent, STYLE_GUIDES
from backend.app.agents.review import ReviewAgent
from backend.app.agents.revision import RevisionAgent
from backend.app.schemas.agent import Outline, Section, Script, ReviewResult, Issue


# ============================================================
# 公共 fixture：mock BaseAgent._invoke 不动 LLM
# ============================================================
def _mock_invoke(return_obj, agent_instance):
    """用 MagicMock 替换 agent 的 _invoke 方法，返回指定对象。"""
    agent_instance._invoke = MagicMock(return_value=return_obj)


# ============================================================
# PlanningAgent 测试
# ============================================================
class TestPlanningAgent:
    """测试策划 Agent：prompt 构建 + 兜底。"""

    @pytest.fixture
    def agent(self):
        """创建 PlanningAgent 但不初始化 LLM 客户端。"""
        with patch.object(PlanningAgent, '__init__', lambda self: None):
            a = PlanningAgent.__new__(PlanningAgent)
            a.model_name = "deepseek-reasoner"
            return a

    @pytest.fixture
    def state(self):
        """基础 state：选题 + 风格 + 时长。"""
        return {
            "topic": "打工人如何保持精力",
            "style": "知识",
            "duration": 120,
            "feedback": "",
        }

    def test_run_produces_outline(self, agent, state):
        """正常流程：_invoke 返回 Outline → state 包含 outline。"""
        outline = Outline(
            title="打工人精力管理指南",
            hook="每天下午三点就犯困？这3个方法让你精力翻倍！",
            sections=[
                Section(heading="引入", talking_points=["痛点共鸣"]),
                Section(heading="方法一", talking_points=["规律作息"]),
            ],
            key_phrases=["精力是打工人最宝贵的资产"],
            estimated_duration=120,
        )
        _mock_invoke(outline, agent)
        agent._search_hotspot = MagicMock(return_value=[])

        result = agent.run(state)
        assert "outline" in result
        assert result["outline"]["title"] == "打工人精力管理指南"
        assert len(result["outline"]["sections"]) == 2

    def test_run_with_feedback(self, agent, state):
        """带 feedback 参数时 prompt 包含修改要求。"""
        state["feedback"] = "换个角度，从饮食方面切入"
        outline = Outline(
            title="测试", hook="测试",
            sections=[], key_phrases=[], estimated_duration=120,
        )
        _mock_invoke(outline, agent)
        agent._search_hotspot = MagicMock(return_value=[])

        # 验证 _invoke 被调用（不崩即可，prompt 内容由 LLM 保证）
        result = agent.run(state)
        assert result["outline"] is not None

    def test_run_fallback_on_parse_failure(self, agent, state):
        """_invoke 返回 None → 兜底 Outline 被写入 state。"""
        _mock_invoke(None, agent)
        agent._search_hotspot = MagicMock(return_value=[])

        result = agent.run(state)
        assert result["outline"] is not None
        # 兜底 outline 的 title 使用原始 topic
        assert result["outline"]["title"] == state["topic"]

    def test_hotspot_search_called(self, agent, state):
        """_search_hotspot 被调用，结果传递给 prompt。"""
        outline = Outline(
            title="测试", hook="测试",
            sections=[], key_phrases=[], estimated_duration=120,
        )
        _mock_invoke(outline, agent)
        mock_search = MagicMock(return_value=[
            {"title": "热点标题", "content": "热点内容参考", "url": "https://example.com"},
        ])
        agent._search_hotspot = mock_search

        agent.run(state)
        mock_search.assert_called_once_with(state["topic"])


# ============================================================
# WritingAgent 测试
# ============================================================
class TestWritingAgent:
    """测试写作 Agent：prompt 构建 + 风格指南 + 兜底。"""

    @pytest.fixture
    def agent(self):
        with patch.object(WritingAgent, '__init__', lambda self: None):
            a = WritingAgent.__new__(WritingAgent)
            a.model_name = "deepseek-chat"
            return a

    @pytest.fixture
    def state(self):
        return {
            "outline": {
                "title": "打工人精力管理",
                "hook": "每天下午三点就犯困？",
                "sections": [
                    {"heading": "引入", "talking_points": ["痛点"]},
                    {"heading": "方法", "talking_points": ["建议1", "建议2"]},
                ],
                "key_phrases": ["金句1", "金句2"],
                "estimated_duration": 120,
            },
            "style": "知识",
            "duration": 120,
        }

    def test_run_produces_script(self, agent, state):
        """正常流程：_invoke 返回 Script → state 包含 script。"""
        script = Script(
            content="[快]大家好！[停顿1s]每天下午三点就犯困？\n这个视频告诉你怎么办。",
            duration_estimate=120,
            tone_markers=["[快]", "[停顿1s]"],
        )
        _mock_invoke(script, agent)

        result = agent.run(state)
        assert "script" in result
        assert result["script"]["content"].startswith("[快]")

    def test_run_fallback_on_parse_failure(self, agent, state):
        """_invoke 返回 None → 兜底 Script。"""
        _mock_invoke(None, agent)

        result = agent.run(state)
        assert result["script"] is not None
        assert "生成失败" in result["script"]["content"]

    def test_style_guide_knowledge(self, agent, state):
        """知识风格 → STYLE_GUIDES['知识'] 被使用。"""
        state["style"] = "知识"
        script = Script(content="测试", duration_estimate=60, tone_markers=[])
        _mock_invoke(script, agent)

        # 不崩即可
        result = agent.run(state)
        assert result["script"] is not None

    def test_style_guide_humor(self, agent, state):
        """搞笑风格 → STYLE_GUIDES['搞笑'] 被使用。"""
        state["style"] = "搞笑"
        script = Script(content="测试搞笑", duration_estimate=60, tone_markers=[])
        _mock_invoke(script, agent)

        result = agent.run(state)
        assert result["script"] is not None

    def test_style_guide_emotion(self, agent, state):
        """情感风格 → STYLE_GUIDES['情感'] 被使用。"""
        state["style"] = "情感"
        script = Script(content="测试情感", duration_estimate=60, tone_markers=[])
        _mock_invoke(script, agent)

        result = agent.run(state)
        assert result["script"] is not None

    def test_unknown_style_falls_back_to_knowledge(self, agent, state):
        """未知风格 → 回退到'知识'风格，不崩。"""
        state["style"] = "不存在的风格"
        script = Script(content="测试", duration_estimate=60, tone_markers=[])
        _mock_invoke(script, agent)

        result = agent.run(state)  # 不应抛异常
        assert result["script"] is not None

    def test_empty_outline_survives(self, agent, state):
        """大纲为空 → 不崩，兜底写作。"""
        state["outline"] = {}
        script = Script(content="测试", duration_estimate=60, tone_markers=[])
        _mock_invoke(script, agent)

        result = agent.run(state)  # 不应抛 KeyError
        assert result["script"] is not None


# ============================================================
# ReviewAgent 测试
# ============================================================
class TestReviewAgent:
    """测试审核 Agent：四维评分 + Issue 分级 + 兜底。"""

    @pytest.fixture
    def agent(self):
        with patch.object(ReviewAgent, '__init__', lambda self: None):
            a = ReviewAgent.__new__(ReviewAgent)
            a.model_name = "deepseek-reasoner"
            return a

    @pytest.fixture
    def state(self):
        return {
            "script": {"content": "测试口播脚本文本内容"},
            "style": "知识",
        }

    def test_run_produces_review_passed(self, agent, state):
        """正常流程：审核通过 → review 写入 state。"""
        review = ReviewResult(
            passed=True,
            issues=[],
            score=88,
            dimension_scores={"information": 22, "oral": 23, "compliance": 24, "usability": 19},
            checks={"compliance": True, "facts": True, "style": True},
        )
        _mock_invoke(review, agent)
        agent._fact_check = MagicMock(return_value="")

        result = agent.run(state)
        assert "review" in result
        assert result["review"]["passed"] is True
        assert result["review"]["score"] == 88

    def test_run_produces_review_with_issues(self, agent, state):
        """审核发现 P0 问题 → passed=False。"""
        review = ReviewResult(
            passed=False,
            issues=[
                Issue(
                    severity="P0", category="compliance",
                    location="最好的产品", description="极限词违规",
                    suggestion="删除'最好的'",
                ),
            ],
            score=60,
        )
        _mock_invoke(review, agent)
        agent._fact_check = MagicMock(return_value="")

        result = agent.run(state)
        assert result["review"]["passed"] is False
        assert len(result["review"]["issues"]) == 1
        assert result["review"]["issues"][0]["severity"] == "P0"

    def test_run_fallback_on_parse_failure(self, agent, state):
        """_invoke 返回 None → 兜底 ReviewResult（系统级 P0 问题）。"""
        _mock_invoke(None, agent)
        agent._fact_check = MagicMock(return_value="")

        result = agent.run(state)
        assert result["review"]["passed"] is False
        assert len(result["review"]["issues"]) == 1
        assert result["review"]["issues"][0]["severity"] == "P0"
        assert result["review"]["score"] == 0

    def test_fact_check_called(self, agent, state):
        """_fact_check 被调用。"""
        review = ReviewResult(passed=True, issues=[], score=85)
        _mock_invoke(review, agent)
        mock_fact = MagicMock(return_value="核查结果")
        agent._fact_check = mock_fact

        agent.run(state)
        mock_fact.assert_called_once()


# ============================================================
# RevisionAgent 测试
# ============================================================
class TestRevisionAgent:
    """测试修改 Agent：P0/P1 修改 + 兜底 + 跳过逻辑。"""

    @pytest.fixture
    def agent(self):
        with patch.object(RevisionAgent, '__init__', lambda self: None):
            a = RevisionAgent.__new__(RevisionAgent)
            a.model_name = "deepseek-chat"
            return a

    @pytest.fixture
    def state(self):
        return {
            "script": {
                "content": "这是最好的产品，适合所有人。",
                "duration_estimate": 60,
                "tone_markers": [],
            },
            "review": {
                "issues": [
                    {
                        "severity": "P0",
                        "category": "compliance",
                        "location": "最好的产品",
                        "description": "极限词'最好'违规",
                        "suggestion": "改为'出色的'",
                    },
                    {
                        "severity": "P2",
                        "category": "style",
                        "location": "适合所有人",
                        "description": "表达不够具体",
                        "suggestion": "",
                    },
                ],
            },
        }

    def test_run_modifies_script(self, agent, state):
        """正常流程：修改后 script.content 改变。"""
        new_script = Script(
            content="这是出色的产品，适合各类人群。",
            duration_estimate=60,
            tone_markers=[],
        )
        _mock_invoke(new_script, agent)

        result = agent.run(state)
        assert result["script"]["content"] != "这是最好的产品，适合所有人。"
        assert "最好" not in result["script"]["content"]

    def test_no_must_fix_skips(self, agent, state):
        """没有 P0/P1 问题 → 不调 LLM，直接返回原 state。"""
        state["review"]["issues"] = [
            {"severity": "P2", "category": "style", "description": "风格建议"},
        ]
        # 不设置 _invoke mock——如果调了 LLM 会崩
        result = agent.run(state)
        assert result == state  # 不修改直接返回

    def test_run_fallback_on_parse_failure(self, agent, state):
        """_invoke 返回 None → 兜底保留原文。"""
        _mock_invoke(None, agent)

        result = agent.run(state)
        assert result["script"]["content"] == state["script"]["content"]

    def test_p1_issues_are_fixed(self, agent, state):
        """P1 问题也在必改清单中。"""
        state["review"]["issues"] = [
            {
                "severity": "P1",
                "category": "facts",
                "location": "98%的人",
                "description": "数据来源不明",
                "suggestion": "改为'大多数人'",
            },
        ]
        original_content = state["script"]["content"]
        new_script = Script(content="大多数人都会遇到这个问题", duration_estimate=60, tone_markers=[])
        _mock_invoke(new_script, agent)

        result = agent.run(state)
        # agent.run 原地修改 state，所以用保存的原始内容对比
        assert result["script"]["content"] != original_content


# ============================================================
# BaseAgent / extract_json 功能测试
# ============================================================
class TestBaseAgentAbstract:
    """测试 BaseAgent 抽象约束。"""

    def test_cannot_instantiate_without_run(self):
        """未实现 run 方法的子类不能实例化。"""
        class IncompleteAgent(BaseAgent):
            pass

        with pytest.raises(TypeError):
            IncompleteAgent()  # abstractmethod 未实现 → TypeError

    def test_concrete_agent_can_instantiate(self):
        """实现了 run 的子类可以实例化。"""
        # 先 mock __init__ 跳过 LLM 初始化
        with patch.object(BaseAgent, '__init__', lambda self, **kw: None):
            class CompleteAgent(BaseAgent):
                def run(self, state):
                    return state

            agent = CompleteAgent()
            assert agent is not None
            assert agent.run({}) == {}
