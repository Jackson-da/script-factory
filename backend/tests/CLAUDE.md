# CLAUDE.md — tests

## 地图

| 文件 | 测什么 | 需要 API Key |
|------|--------|-------------|
| `test_pipeline.py` | 编排器状态机、步骤流转、兜底逻辑 | 否 |
| `test_compliance.py` | 极限词/医疗断言/政治敏感/格式校验 | 否 |
| `test_agents.py` | 4 个 Agent mock 测试、兜底、搜索调用 | 否 |
| `test_extract_json.py` | JSON 解析：代码块/嵌套/异常输入 | 否 |
| `test_e2e.py` | health/422/完整流水线 | **是** |

## 规则

**1. test_e2e.py 的 skipif 必须检查两件事。** 不仅要检查 `DEEPSEEK_API_KEY` 环境变量存在，还要检查它不是占位符（不能包含 `"your-deepseek-key"`）。否则拿占位符跑测试会浪费调用。

```python
@pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY")
    or "your-deepseek-key" in os.getenv("DEEPSEEK_API_KEY", ""),
    reason="需要真实的 DeepSeek API Key"
)
```

**2. E2E 测试用 httpx.AsyncClient + ASGITransport。** 不需要启动真实服务器，直接在进程内测 FastAPI app：

```python
from httpx import AsyncClient, ASGITransport
async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
    response = await client.post("/generate", json={...})
```

**3. 前四个测试文件可以脱机跑。** 不调任何外部 API，CI 里直接 `pytest backend/tests/ -v --ignore=backend/tests/test_e2e.py`。
