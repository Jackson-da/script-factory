"""extract_json 函数单元测试 —— 覆盖各种 LLM 响应格式。"""

import json
import pytest
from backend.app.agents.base import extract_json


class TestExtractJson:
    """测试从 LLM 文本响应中提取 JSON 对象。"""

    # ---------- 标准格式 ----------
    def test_json_code_block(self):
        """标准 ```json ... ``` 包裹格式。"""
        raw = '```json\n{"name": "测试", "score": 85}\n```'
        result = extract_json(raw)
        assert result == {"name": "测试", "score": 85}

    def test_bare_code_block(self):
        """``` 包裹但未标注 json 语言标记。"""
        raw = '```\n{"name": "测试", "score": 85}\n```'
        result = extract_json(raw)
        assert result == {"name": "测试", "score": 85}

    def test_plain_json(self):
        """纯 JSON，无任何包裹。"""
        raw = '{"name": "测试", "score": 85}'
        result = extract_json(raw)
        assert result == {"name": "测试", "score": 85}

    # ---------- 复杂内容 ----------
    def test_nested_json(self):
        """嵌套 JSON 对象正确解析。"""
        raw = '''```json
{
  "title": "测试大纲",
  "sections": [
    {"heading": "引入", "talking_points": ["要点1", "要点2"]},
    {"heading": "高潮", "talking_points": ["要点3"]}
  ],
  "key_phrases": ["金句1", "金句2"],
  "estimated_duration": 120
}
```'''
        result = extract_json(raw)
        assert result["title"] == "测试大纲"
        assert len(result["sections"]) == 2
        assert result["sections"][0]["talking_points"][0] == "要点1"
        assert result["estimated_duration"] == 120

    def test_array_json(self):
        """JSON 数组也能正确解析。"""
        raw = '[{"name": "A"}, {"name": "B"}]'
        result = extract_json(raw)
        assert isinstance(result, list)
        assert len(result) == 2

    # ---------- 边界情况 ----------
    def test_extra_whitespace(self):
        """JSON 前后有多余空白字符。"""
        raw = '\n\n \t```json\n\n{"name": "测试"}\n\n```\n  '
        result = extract_json(raw)
        assert result == {"name": "测试"}

    def test_llm_speaks_before_json(self):
        """LLM 在 JSON 前后说话（常见于 reasoner 模型）。"""
        raw = '好的，这是大纲：\n```json\n{"title": "测试"}\n```\n希望这个大纲对你有帮助。'
        result = extract_json(raw)
        assert result == {"title": "测试"}

    def test_multiple_code_blocks_takes_first_json(self):
        """多个代码块时取第一个 json 代码块。"""
        raw = '```json\n{"title": "大纲1"}\n```\n```json\n{"title": "大纲2"}\n```'
        result = extract_json(raw)
        assert result == {"title": "大纲1"}

    def test_only_json_code_block_used(self):
        """有 ``` 普通代码块时，优先取 ```json 标记的块。"""
        raw = '```\nsome text\n```\n```json\n{"result": "ok"}\n```'
        result = extract_json(raw)
        assert result == {"result": "ok"}

    # ---------- 异常情况 ----------
    def test_invalid_json_raises(self):
        """畸形 JSON 抛出 JSONDecodeError。"""
        raw = '{"name": "测试", invalid}'
        with pytest.raises(json.JSONDecodeError):
            extract_json(raw)

    def test_trailing_comma_raises(self):
        """JSON 末尾多余逗号抛出异常。"""
        raw = '{"name": "测试",}'
        with pytest.raises(json.JSONDecodeError):
            extract_json(raw)

    def test_single_quotes_raises(self):
        """单引号 JSON（不符合规范）抛出异常。"""
        raw = "{'name': '测试'}"
        with pytest.raises(json.JSONDecodeError):
            extract_json(raw)
