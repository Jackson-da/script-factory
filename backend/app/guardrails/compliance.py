"""
合规检测模块。
提供：极限词检测、医疗敏感词过滤、政治敏感词过滤、Pydantic格式校验。
审核Agent在评分前调用此模块做硬性合规扫描。
"""

import logging
import re

logger = logging.getLogger(__name__)


# 广告法极限词 —— 正则匹配
FORBIDDEN_WORDS_PATTERN = re.compile(
    r"(最好|第一|国家级|唯一|顶级|极致|绝对|永久|万能|"
    r"首选|冠军|王牌|无敌|史上最强|世界第一|全国第一|"
    r"最便宜|最低价|最先进|最高级|最新科技)",
    re.IGNORECASE
)

# 医疗敏感断言
MEDICAL_CLAIMS_PATTERN = re.compile(
    r"(治愈|根治|神药|特效药|一针见效|药到病除|"
    r"百分百有效|彻底消除|永不复发|祖传秘方|"
    r"抗癌|降三高|排毒养颜)",
    re.IGNORECASE
)

# 政治敏感词库 —— 平台合规红线，命中任一条立即拦截
POLITICAL_SENSITIVE = [
    # === 政治体制 ===
    "亡党亡国", "颜色革命", "多党制", "军队国家化", "三权分立",
    "新闻自由", "宪政", "普世价值", "公民社会", "新自由主义",
    # === 主权领土 ===
    "台独", "港独", "藏独", "疆独", "东突",
    "两个中国", "一中一台", "西藏独立", "新疆独立",
    # === 历史事件 ===
    "六四", "天安门事件", "法轮功", "法轮大法", "九评共产党",
    # === 邪教/非法组织 ===
    "全能神", "门徒会", "呼喊派", "被立王", "主神教",
    "实际神", "三班仆人派", "灵灵教",
    # === 网络违法 ===
    "翻墙", "VPN推荐", "科学上网", "暗网",
    # === 暴恐 ===
    "圣战", "自杀式袭击", "恐怖主义", "炸弹制作",
    # === 黄赌毒 ===
    "色情", "赌博网站", "赌场", "毒品", "吸毒",
    "制毒", "贩毒", "嫖娼", "卖淫",
]


def detect_forbidden_words(text: str) -> list[dict]:
    """检测广告法极限词。

    Args:
        text: 待检测文本

    Returns:
        检测到的违规词列表，每个违规词包含 {word, position}
    """
    issues = []
    for match in FORBIDDEN_WORDS_PATTERN.finditer(text):
        issues.append({
            "severity": "P0",
            "category": "compliance",
            "word": match.group(),
            "position": match.start(),
            "suggestion": f"删除或替换极限词'{match.group()}'，改用客观描述",
        })
    return issues


def detect_medical_claims(text: str) -> list[dict]:
    """检测医疗健康类敏感断言。

    Args:
        text: 待检测文本

    Returns:
        检测到的违规断言列表
    """
    issues = []
    for match in MEDICAL_CLAIMS_PATTERN.finditer(text):
        issues.append({
            "severity": "P0",
            "category": "compliance",
            "word": match.group(),
            "position": match.start(),
            "suggestion": f"医疗断言'{match.group()}'违规，非专业医疗脚本需删除",
        })
    return issues


def detect_political_sensitive(text: str) -> list[dict]:
    """检测政治敏感内容（基础版）。

    Args:
        text: 待检测文本

    Returns:
        检测到的敏感词列表
    """
    issues = []
    for word in POLITICAL_SENSITIVE:
        pos = text.find(word)
        if pos != -1:
            issues.append({
                "severity": "P0",
                "category": "compliance",
                "word": word,
                "position": pos,
                "suggestion": f"删除敏感词'{word}'",
            })
    return issues


def run_compliance_check(text: str) -> dict:
    """执行完整合规检查。

    Args:
        text: 待检测文本

    Returns:
        {passed: bool, issues: list[dict], summary: str}
    """
    all_issues = []
    all_issues.extend(detect_forbidden_words(text))
    all_issues.extend(detect_medical_claims(text))
    all_issues.extend(detect_political_sensitive(text))

    passed = len(all_issues) == 0
    if passed:
        logger.debug("合规检测通过")
    else:
        categories = set(i.get("category", "unknown") for i in all_issues)
        logger.info(f"合规检测命中 {len(all_issues)} 条 | 类别: {categories}")

    return {
        "passed": passed,
        "issues": all_issues,
        "summary": f"检测到 {len(all_issues)} 个合规问题" if all_issues else "合规检测通过",
    }


def format_check(data: dict, expected_fields: list[str]) -> dict:
    """Pydantic 格式校验。

    校验关键字段是否存在且非空。

    Args:
        data: 待校验的字典
        expected_fields: 必须存在的字段列表

    Returns:
        {passed: bool, missing_fields: list[str]}
    """
    missing = [f for f in expected_fields if not data.get(f)]
    return {
        "passed": len(missing) == 0,
        "missing_fields": missing,
    }
