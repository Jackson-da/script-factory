"""合规检测模块单元测试。"""

import pytest
from backend.app.guardrails.compliance import (
    detect_forbidden_words,
    detect_medical_claims,
    detect_political_sensitive,
    run_compliance_check,
    format_check,
)


class TestDetectForbiddenWords:
    """测试广告法极限词检测。"""

    def test_detects_best(self):
        """检测"最好"。"""
        issues = detect_forbidden_words("这款产品是市场上最好的选择")
        assert len(issues) >= 1
        assert any("最好" == i["word"] for i in issues)

    def test_detects_first(self):
        """检测"第一"。"""
        issues = detect_forbidden_words("销量第一的品牌")
        assert any("第一" == i["word"] for i in issues)

    def test_detects_ultimate(self):
        """检测"顶级"。"""
        issues = detect_forbidden_words("顶级的用户体验")
        assert any("顶级" == i["word"] for i in issues)

    def test_all_issues_are_p0(self):
        """所有极限词问题都是 P0 级别。"""
        issues = detect_forbidden_words("最好的第一品牌，顶级享受")
        for issue in issues:
            assert issue["severity"] == "P0"
            assert issue["category"] == "compliance"

    def test_clean_text_no_issues(self):
        """不含违规词的文本返回空列表。"""
        issues = detect_forbidden_words("这是一款性价比不错的日常用品，适合家庭使用")
        assert len(issues) == 0

    def test_case_insensitive(self):
        """大小写不敏感匹配。"""
        # 中文没有大小写，但正则标记了 IGNORECASE，确认不抛异常
        issues = detect_forbidden_words("这款产品是顶级好物")
        assert len(issues) == 1

    def test_each_issue_has_position(self):
        """每个违规词返回位置信息。"""
        issues = detect_forbidden_words("最好的产品")
        assert "position" in issues[0]
        assert isinstance(issues[0]["position"], int)

    def test_each_issue_has_suggestion(self):
        """每个违规词返回修改建议。"""
        issues = detect_forbidden_words("最好的产品")
        assert "suggestion" in issues[0]
        assert len(issues[0]["suggestion"]) > 0

    def test_multiple_words_in_one_text(self):
        """同一文本中多个违禁词全部检出。"""
        issues = detect_forbidden_words("最好的第一品牌，冠军产品顶级享受")
        # 至少检出 4 个
        assert len(issues) >= 4


class TestDetectMedicalClaims:
    """测试医疗敏感断言检测。"""

    def test_detects_cure(self):
        """检测"治愈"。"""
        issues = detect_medical_claims("这个产品可以治愈失眠")
        assert any("治愈" == i["word"] for i in issues)

    def test_detects_eradicate(self):
        """检测"根治"。"""
        issues = detect_medical_claims("根治顽固性皮肤问题")
        assert any("根治" == i["word"] for i in issues)

    def test_detects_miracle_drug(self):
        """检测"神药"。"""
        issues = detect_medical_claims("堪称神药级别的效果")
        assert any("神药" == i["word"] for i in issues)

    def test_detects_anticancer(self):
        """检测"抗癌"。"""
        issues = detect_medical_claims("具有抗癌功效")
        assert any("抗癌" == i["word"] for i in issues)

    def test_clean_text_no_issues(self):
        """不含医疗断言的文本返回空。"""
        issues = detect_medical_claims("多吃蔬菜水果有益健康，保持规律作息")
        assert len(issues) == 0

    def test_all_issues_are_p0(self):
        """所有医疗断言都是 P0 级别。"""
        issues = detect_medical_claims("治愈各种慢性病")
        for issue in issues:
            assert issue["severity"] == "P0"

    def test_detox_beauty_detected(self):
        """检测"排毒养颜"。"""
        issues = detect_medical_claims("这款产品能排毒养颜")
        assert any("排毒养颜" == i["word"] for i in issues)


class TestDetectPoliticalSensitive:
    """测试政治敏感词检测。"""

    def test_detects_political_word(self):
        """检测到政治敏感词。"""
        issues = detect_political_sensitive("宣扬台独言论")
        assert len(issues) >= 1
        assert any("台独" == i["word"] for i in issues)

    def test_detects_cult_word(self):
        """检测到邪教相关词汇。"""
        issues = detect_political_sensitive("法轮功组织的宣传材料")
        assert any("法轮功" == i["word"] for i in issues)

    def test_detects_gambling_drug_word(self):
        """检测到黄赌毒词汇。"""
        issues = detect_political_sensitive("赌博网站推荐，毒品交易渠道")
        assert len(issues) >= 2

    def test_clean_text_no_issues(self):
        """不含敏感词的文本返回空。"""
        issues = detect_political_sensitive("今天天气真好，适合出去走走")
        assert len(issues) == 0

    def test_all_issues_are_p0(self):
        """所有政治敏感问题都是 P0 级别。"""
        issues = detect_political_sensitive("台独藏独港独")
        for issue in issues:
            assert issue["severity"] == "P0"
            assert issue["category"] == "compliance"

    def test_each_issue_has_fields(self):
        """每个敏感词返回完整信息。"""
        issues = detect_political_sensitive("涉及法轮功的内容")
        assert len(issues) >= 1
        for field in ["severity", "category", "word", "position", "suggestion"]:
            assert field in issues[0]


class TestRunComplianceCheck:
    """测试完整合规检查流程。"""

    def test_passed_when_clean(self):
        """干净文本通过合规检查。"""
        result = run_compliance_check("这是一段普通的产品介绍文字，适合日常使用")
        assert result["passed"] is True
        assert len(result["issues"]) == 0
        assert "通过" in result["summary"]

    def test_failed_when_forbidden_word(self):
        """含极限词 → 不通过。"""
        result = run_compliance_check("这是最好的产品")
        assert result["passed"] is False
        assert len(result["issues"]) >= 1
        assert "检测到" in result["summary"]

    def test_failed_when_medical_claim(self):
        """含医疗断言 → 不通过。"""
        result = run_compliance_check("可以治愈各种疾病")
        assert result["passed"] is False

    def test_failed_when_political_sensitive(self):
        """含政治敏感词 → 不通过。"""
        result = run_compliance_check("涉及法轮功的内容需要删除")
        assert result["passed"] is False

    def test_failed_when_both(self):
        """同时含极限词和医疗断言 → 两者都检出。"""
        result = run_compliance_check("这是最好的产品，还能治愈失眠")
        assert result["passed"] is False
        assert len(result["issues"]) >= 2

    def test_failed_when_all_three_categories(self):
        """三种违规同时出现 → 全部检出。"""
        result = run_compliance_check("最好的产品，治愈失眠，法轮功相关")
        assert result["passed"] is False
        assert len(result["issues"]) >= 3

    def test_issue_structure(self):
        """每个 issue 都包含必要字段。"""
        result = run_compliance_check("最好的产品")
        issue = result["issues"][0]
        for field in ["severity", "category", "word", "position", "suggestion"]:
            assert field in issue


class TestFormatCheck:
    """测试 Pydantic 格式校验。"""

    def test_all_fields_present(self):
        """所有期望字段都存在 → 通过。"""
        data = {"title": "标题", "content": "内容", "score": 85}
        result = format_check(data, ["title", "content", "score"])
        assert result["passed"] is True
        assert len(result["missing_fields"]) == 0

    def test_missing_field_detected(self):
        """缺失字段 → 不通过，列出缺失字段。"""
        data = {"title": "标题"}
        result = format_check(data, ["title", "content", "score"])
        assert result["passed"] is False
        assert "content" in result["missing_fields"]
        assert "score" in result["missing_fields"]

    def test_empty_string_treated_as_missing(self):
        """空字符串视为缺失。"""
        data = {"title": "", "content": "有内容"}
        result = format_check(data, ["title", "content"])
        assert result["passed"] is False
        assert "title" in result["missing_fields"]

    def test_zero_treated_as_missing(self):
        """format_check 用 truthiness 判断：0 是 falsy → 视为缺失。"""
        data = {"score": 0}
        result = format_check(data, ["score"])
        assert result["passed"] is False
        assert "score" in result["missing_fields"]

    def test_empty_list_treated_as_missing(self):
        """format_check 用 truthiness 判断：[] 是 falsy → 视为缺失。"""
        data = {"items": []}
        result = format_check(data, ["items"])
        assert result["passed"] is False
        assert "items" in result["missing_fields"]
