# 自媒体口播脚本自动生成工厂

多Agent协作流水线：策划→写作→审核→修改，自动生成短视频口播脚本。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI + LangChain + DeepSeek + Pydantic |
| 前端 | Vue 3 + Vite (Swiss Modernism 2.0) |
| 搜索 | Tavily Search API |
| 编排 | 自定义状态机 (while + dict) |
| 可观测 | LangFuse |
| 部署 | Docker Compose |

## 架构

```
用户输入(选题+风格+时长)
    │
    ▼
策划Agent (deepseek-reasoner + Tavily搜索)
    │
    ▼
[人工确认点]  ← 可选暂停，审阅大纲
    │
    ▼
写作Agent (deepseek-chat)
    │
    ▼
审核Agent (deepseek-reasoner) ──┬── 通过 → 输出
                                │
                                ├── 不通过 → 修改Agent
                                │         │
                                └── 3轮超限 → 降级输出
```

## 快速开始

### 1. 环境准备

```bash
# Python 3.12+
python -m venv .venv
.venv\Scripts\activate
pip install -e .

# Node 18+
npm --prefix frontend install
```

### 2. 配置API Key

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key 和 Tavily API Key
```

### 3. 启动

```bash
# 后端
uvicorn backend.app.main:app --reload

# 前端（另一个终端）
npm --prefix frontend run dev
```

浏览器打开 http://localhost:5173

### 4. Docker 部署

```bash
docker-compose -f docker/docker-compose.yml up -d
```

## 项目结构

```
├── backend/              # 后端
│   ├── app/              # 应用代码
│   │   ├── agents/       # 4个Agent (策划/写作/审核/修改)
│   │   ├── api/          # API路由 + 依赖注入
│   │   ├── core/         # 全局配置
│   │   ├── schemas/      # Pydantic数据模型
│   │   ├── pipeline/     # 编排器状态机
│   │   ├── guardrails/   # 合规护栏
│   │   └── tracker/      # LangFuse可观测
│   ├── tests/            # 测试
│   └── evaluation/       # 评估数据集+对比脚本
├── frontend/             # 前端 Vue 3 + Vite
│   └── src/
│       ├── api/          # API调用封装
│       └── components/   # UI组件
├── docker/               # Docker部署
└── docs/                 # 设计文档+实施计划
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /generate | 生成脚本（首次/确认两种调用方式） |
| GET | /health | 健康检查 |

## 工作流模式

- **全自动模式**: 一次调用 `/generate` → 策划→写作→审核→(修改)×N → 输出终稿
- **人工确认模式**: 首次调用 → 策划完成暂停 → 审阅大纲 → 二次调用确认/重策划/修改大纲 → 继续执行

## 核心指标

- 自动审核一次通过率 ≥ 60%
- 多Agent可用率 > 单Agent可用率
- 合规检查拦截率 = 100%（极限词一个不漏）
- 完整流水线耗时 < 60s
