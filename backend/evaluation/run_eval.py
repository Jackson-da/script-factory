"""
评估脚本：单Agent vs 多Agent流水线对比。
对每个选题×风格组合，分别生成单Agent版和多Agent版，
由审核Agent盲评打分，输出对比报告。
"""

import json
import sys
import io
import time
from pathlib import Path

# UTF-8 输出（避免 Windows GBK 编码报错）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 单Agent：一个 prompt 直接出完整脚本
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from backend.app.core.config import get_settings

# 多Agent：走完整流水线
from backend.app.pipeline.orchestator import init_state, run_pipeline


def run_single_agent(topic: str, style: str, duration: int) -> str:
    """单Agent直接写脚本（不经过策划/审核/修改流程）。

    Args:
        topic: 选题
        style: 风格
        duration: 时长

    Returns:
        脚本文本
    """
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.deepseek_chat_model,
        openai_api_key=settings.deepseek_api_key,
        openai_api_base=settings.deepseek_base_url,
        temperature=0.7,
        max_tokens=4096,
    )
    system = f"""你是一个短视频口播脚本写手。
账号风格：{style}
时长要求：约{duration}秒口语文本
选题：{topic}

请直接输出一个完整口播脚本，包含：
1. 吸引人的开场钩子
2. 核心内容展开
3. 金句收尾

脚本要口语化，能直接读出来。"""
    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=f"请为选题「{topic}」写一个{style}风格的口播脚本")])
    return response.content


def run_multi_agent(topic: str, style: str, duration: int) -> dict:
    """多Agent流水线走完整流程。

    run_pipeline 设计为每次 HTTP 请求只推进一步。
    评估脚本不走 HTTP，需要用 while 循环反复调用直到 done。

    Args:
        topic: 选题
        style: 风格
        duration: 时长

    Returns:
        完整 state 字典
    """
    state = init_state(topic=topic, style=style, duration=duration, auto_mode=True)
    while state.get("step") != "done":
        state = run_pipeline(state)
    return state


def evaluate_script(content: str, topic: str, style: str) -> dict:
    """用审核Agent单独评估一个脚本。

    Args:
        content: 脚本文本
        topic: 选题
        style: 风格

    Returns:
        评分结果字典
    """
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.deepseek_reasoner_model,
        openai_api_key=settings.deepseek_api_key,
        openai_api_base=settings.deepseek_base_url,
        temperature=0.3,
        max_tokens=2048,
    )

    # 用 SystemMessage + HumanMessage 直接拼，绕过 LangChain 模板的花括号冲突
    from langchain_core.messages import SystemMessage, HumanMessage
    system = f"""你是短视频脚本评审专家。给以下脚本打分(0-100)：
- 信息量(25分): 是否有实质性内容
- 口语化(25分): 能否读出嘴
- 合规性(25分): 有无极限词/敏感内容
- 可用率(25分): 能否直接拿去拍

选题: {topic} | 风格: {style}
请只输出一个JSON: {{"score": 85, "dimensions": {{"information": 20, "oral": 20, "compliance": 25, "usability": 20}}}}"""

    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=content)])

    try:
        raw = response.content.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"score": 0, "error": "parse failed"}


def main():
    """主评估流程。"""
    data_path = Path(__file__).parent / "topics.json"
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("=" * 60)
    print("评估：单Agent vs 多Agent流水线")
    print(f"数据集：{len(data['topics'])}个选题 × 3种风格 = {len(data['topics']) * 3}个样本")
    print("=" * 60)

    single_scores = []
    multi_scores = []
    results = []

    for item in data["topics"]:
        topic = item["topic"]
        for style in item["styles"]:
            duration = 120
            print(f"\n📝 {topic} | {style} | {duration}s")

            # 单Agent
            t0 = time.time()
            single_script = run_single_agent(topic, style, duration)
            single_elapsed = time.time() - t0
            single_eval = evaluate_script(single_script, topic, style)
            single_score = single_eval.get("score", 0)
            single_scores.append(single_score)
            print(f"  单Agent: {single_score}分 ({single_elapsed:.1f}s)")

            # 多Agent
            t0 = time.time()
            multi_state = run_multi_agent(topic, style, duration)
            multi_elapsed = time.time() - t0
            multi_script = (multi_state.get("final_script") or multi_state.get("script") or {}).get("content", "")
            multi_review = multi_state.get("review", {})
            multi_score = multi_review.get("score", 0)
            multi_scores.append(multi_score)
            revisions = multi_state.get("revision_count", 0)
            print(f"  多Agent: {multi_score}分 ({multi_elapsed:.1f}s, {revisions}轮修改)")

            results.append({
                "topic": topic,
                "style": style,
                "single_score": single_score,
                "multi_score": multi_score,
                "single_elapsed": single_elapsed,
                "multi_elapsed": multi_elapsed,
                "revisions": revisions,
                "grade": multi_state.get("grade", "normal"),
            })

    # 汇总
    print("\n" + "=" * 60)
    print("评估结果汇总")
    print("=" * 60)

    avg_single = sum(single_scores) / len(single_scores) if single_scores else 0
    avg_multi = sum(multi_scores) / len(multi_scores) if multi_scores else 0

    print(f"单Agent平均分: {avg_single:.1f}")
    print(f"多Agent平均分: {avg_multi:.1f}")
    print(f"提升: {avg_multi - avg_single:.1f}分")
    print(f"多Agent通过率: {sum(1 for s in multi_scores if s >= 60) / len(multi_scores) * 100:.0f}%")

    # 按风格分组
    styles = ["知识", "搞笑", "情感"]
    for style in styles:
        style_results = [r for r in results if r["style"] == style]
        if style_results:
            avg_s = sum(r["single_score"] for r in style_results) / len(style_results)
            avg_m = sum(r["multi_score"] for r in style_results) / len(style_results)
            print(f"\n{style}风格 — 单Agent: {avg_s:.1f} | 多Agent: {avg_m:.1f} | 提升: {avg_m - avg_s:.1f}")

    # 保存详细结果
    output_path = Path(__file__).parent / "eval_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "single_avg": avg_single,
                "multi_avg": avg_multi,
                "improvement": avg_multi - avg_single,
                "multi_pass_rate": sum(1 for s in multi_scores if s >= 60) / len(multi_scores),
            },
            "details": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到 {output_path}")


if __name__ == "__main__":
    main()
