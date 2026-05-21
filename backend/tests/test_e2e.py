"""端到端测试（需要 API key）。"""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.config import get_settings


@pytest.fixture
def client():
    """创建测试 HTTP 客户端。"""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health_check(client):
    """测试健康检查接口。"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_generate_missing_topic(client):
    """测试空选题返回 422。"""
    response = await client.post("/generate", json={"topic": "", "style": "知识"})
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.skipif(
    not get_settings().deepseek_api_key or "your-deepseek-key" in get_settings().deepseek_api_key,
    reason="需要真实 DEEPSEEK_API_KEY（非占位符）"
)
async def test_generate_full_pipeline(client):
    """测试完整流水线（需要 API key）。"""
    response = await client.post("/generate", json={
        "topic": "打工人如何保持精力",
        "style": "知识",
        "duration": 60,
        "auto_mode": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert "step" in data
    assert data["step"] in ("done", "wait_confirm", "plan", "write", "review", "revise")
