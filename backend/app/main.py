"""
FastAPI 应用入口 —— 整个后端的启动点。

启动命令：uvicorn backend.app.main:app --reload

本文件只做"组装"工作，不包含业务逻辑：
1. 创建 FastAPI app 实例（整个 Web 服务的核心对象）
2. 挂载 CORS 中间件（允许前端跨域访问）
3. 注册 API 路由（将 router.py 中的端点绑定到 app）
4. 提供 /health 健康检查（供探测和监控使用）

架构关系：
  main.py (组装层)
    ├── router.py (路由层：接收 HTTP 请求，分发处理)
    │     └── orchestrator.py (编排层：状态机驱动 Agent 流水线)
    │           ├── planning.py (策划 Agent)
    │           ├── writing.py (写作 Agent)
    │           ├── review.py (审核 Agent)
    │           └── revision.py (修改 Agent)
    └── core/config.py (配置层：从 .env 读取 API key 等)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import router
from backend.app.tracker.langfuse import flush as langfuse_flush


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。启动时无操作，关闭时刷新 LangFuse 缓冲区。"""
    yield
    langfuse_flush()

# ============================================================
# 1. 创建 FastAPI 应用实例
# ============================================================
# FastAPI() 是整个 Web 框架的入口对象。
# 所有路由、中间件、启动/关闭事件都挂在这个对象上。
# uvicorn 启动时读的就是这个 app 变量。
app = FastAPI(
    title="自媒体口播脚本自动生成工厂",
    description="多Agent协作流水线：策划→写作→审核→修改",
    version="0.1.0",
    lifespan=lifespan,
)

# ============================================================
# 2. CORS 跨域中间件
# ============================================================
# 问题背景：
#   前端跑在 localhost:5173（Vite 开发服务器）
#   后端跑在 localhost:8000（uvicorn）
#   浏览器"同源策略"会拦截不同端口之间的 HTTP 请求。
#
# CORS 中间件的作用：
#   在响应头里加上 Access-Control-Allow-Origin: http://localhost:5173
#   浏览器看到这个头就知道"后端允许请求"，不再拦截。
#
# allow_origins:  只允许 Vue 开发服务器的来源，生产环境需改为真实域名
# allow_methods:  放开所有 HTTP 方法（GET/POST/PUT/DELETE/OPTIONS）
# allow_headers:  放开所有请求头（Content-Type/Authorization 等）
# allow_credentials: 允许浏览器携带 Cookie（如需要 Session 时有用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 3. 注册 API 路由
# ============================================================
# include_router 把 router.py 中定义的所有端点（/generate、/health 等）
# 挂载到 app 上。
# router 的 prefix="" 意味着路径不加前缀。
# 如果 prefix="/api/v1"，所有路径都会变成 /api/v1/generate
app.include_router(router)


# ============================================================
# 4. 健康检查端点
# ============================================================
# /health 是基础设施接口，不涉及业务逻辑。
# 用途：
#   - K8s / Docker 的 liveness probe（探活）
#   - 负载均衡器的 health check（健康探测）
#   - 运维监控（确认服务是否正常运行）
# 返回 200 即表示服务存活。
@app.get("/health")
async def health_check():
    """健康检查接口。返回服务名称和运行状态。"""
    return {"status": "ok", "service": "script-factory"}

