# Mockwise · AI 模拟面试助手

> 面向求职者的 AI 一对一 / 一对多模拟面试工具，支持结构化、无领导小组、半结构化三种面试形式，提供「配置—模拟—评估—回放—改进」闭环训练。

- **前端**：Vue 3 + Vite + Ant Design Vue + Pinia + ECharts
- **后端**：FastAPI + SQLAlchemy 2.0 + PyMySQL
- **数据库**：MySQL 8.0+

---

## 📌 项目背景

求职市场每年产生数千万次模拟面试需求，但市面上产品普遍存在三个痛点：

1. **题型单一**：多数产品只能做 1v1 单面，无法覆盖真实求职中占比 30%+ 的群面场景
2. **评估主观**：反馈停留在"表达流畅""逻辑清晰"等空话，缺少可量化的客观指标
3. **闭环断裂**：练完只给一个总分，无法回到具体某一题看到自己哪里答得不好

Mockwise 针对以上三点设计了差异化方案，并完整跑通了从数据库建模 → 后端 API → 前端交互 → 数据可视化的全栈链路。

---

## ✨ 核心亮点

| 模块 | 设计要点 |
| --- | --- |
| **三种面试形式** | 结构化 / 无领导小组 / 半结构化 在同一产品内统一编排，切换无需重新登录 |
| **群面状态机** | 6 人同台、抢麦、打断统计、独立数据建模（`group_participants` / `group_utterances` / `group_events` 三张表），是本项目最具差异化的部分 |
| **多维度评分** | 5 维度（内容 / 逻辑 / 表达 / 应变 / 印象）+ 客观指标（语速 / 停顿 / 口头禅 / 打断次数），维度分采用 `DimensionBar` 横向条形图可视化 |
| **逐题回放** | `GET /api/v1/sessions/{id}/questions/{sq_id}` 支持跳转到任一题单独回看，关联报告、推荐改进点、维度分三项数据 |
| **聚合视图** | MySQL 视图 `v_user_dashboard` 单查询完成工作台 KPI 聚合，避免 N+1 |
| **认证与配额** | JWT 鉴权 + 月度配额扣减（`user_quotas`）+ 连续打卡天数统计，逻辑写在 `crud/session.finish()` 事务里 |
| **数据规模** | 后端 Python 约 **5,000 行** / 18 张表 + 1 视图 / 12 个路由模块 / 39 个前端源文件 |

> **后续规划**：接入真实 LLM 面试官、ASR 转写、AI 评分；当前评分逻辑为基于关键词命中 + 字数/时长权重的 demo 算法，已在代码中预留 `crud/llm_service.py` 替换位。

---

## 🖼️ 预览

> 待截图替换：`docs/screenshots/` 下放置以下 4 张图后即可显示。

| | |
| --- | --- |
| ![工作台](docs/screenshots/01-dashboard.png) | ![作答页](docs/screenshots/02-answer.png) |
| **工作台** —— KPI 聚合 + 趋势图 + 推荐套题 | **作答页** —— 单题作答 + 维度提示 |
| ![报告](docs/screenshots/03-report.png) | ![群面](docs/screenshots/04-group.png) |
| **综合报告** —— 5 维度条形图 + 改进建议 | **群面** —— 6 人同台 + 抢麦 |

跑起来后用浏览器访问 `http://localhost:5173`，按以下顺序截图：登录 → 工作台 → 选形式 → 作答 → 报告 → 群面。

---

## 目录结构

```
ai模拟作业/
├── 模拟面试AI助手-需求分析文档.md      # 需求文档
├── mock_interview_schema.sql           # 原始数据库 schema
├── 原型 - 模拟面试助手-PC端.html        # 产品原型
├── backend/                            # FastAPI 后端
│   ├── app/
│   │   ├── main.py                     # 入口（含 CORS、建表、路由装配）
│   │   ├── core/                       # config / database / security(JWT)
│   │   ├── models/                     # ORM 模型（20+ 表，6 个域）
│   │   ├── schemas/                    # Pydantic 响应模型
│   │   ├── crud/                       # 业务 CRUD + demo 评分逻辑
│   │   └── api/v1/                     # 路由（auth/dashboard/sessions/...）
│   ├── db/seed.sql                     # 纯 SQL 种子数据（可选）
│   ├── seed.py                         # Python 一键建表 + 种子数据（推荐）
│   ├── requirements.txt
│   └── .env.example
└── frontend/                           # Vue3 前端
    ├── src/
    │   ├── main.js / App.vue
    │   ├── router/                     # 路由 + 登录守卫
    │   ├── store/                      # Pinia（user / flow）
    │   ├── api/                        # axios 封装 + 各模块 API
    │   ├── layouts/MainLayout.vue      # 顶栏 + tabs
    │   ├── components/                 # StepsIndicator / KpiCard / ScoreRing / DimensionBar
    │   ├── views/                      # Login/Dashboard/SelectForm/SelectSet/Answer/Report/History/QuestionDetail
    │   └── styles/global.css           # 设计令牌（与 HTML 原型同步）
    └── vite.config.js                  # 含 /api 代理到 8000
```

---

## 快速开始

### 1. 准备 MySQL

```sql
CREATE DATABASE mockwise DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

### 2. 启动后端

> **环境要求**：请使用 **Python 3.12**（`pydantic==1.10.13` 与 Python 3.13 不兼容，3.13 下启动会报 `ForwardRef._evaluate() missing 'recursive_guard'`）。项目已预置完整环境 `backend/venv312`，可直接使用：

```bash
cd backend
# 方式 A（推荐）：直接用预置的 venv312（已装齐 requirements.txt + httpx + pypdf）
venv312\Scripts\activate                                # Windows
# source venv312/bin/activate                            # macOS/Linux

# 方式 B：自建环境（务必用 Python 3.12）
# python3.12 -m venv .venv && .venv\Scripts\activate
# source .venv/bin/activate                            # macOS/Linux
pip install -r requirements.txt

# 配置数据库连接（按需修改）
copy .env.example .env                                 # Windows
# cp .env.example .env                                  # macOS/Linux

# 一键建表 + 写入 demo 数据（推荐，会自动按 ORM 建表，含 password_hash 字段）
python seed.py

# 启动
uvicorn app.main:app --reload --port 8000
```

后端启动后访问 `http://127.0.0.1:8000/docs` 查看 OpenAPI 文档。

> **demo 账号**：`13800000000` / `123456`（也可在前端注册新号，自动初始化 3 次/月配额）。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`，用 demo 账号登录即可。

> Vite 已配置 `/api` 代理到后端 8000 端口，无需额外处理跨域。

---

## 主要 API

| 模块 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| 鉴权 | POST | `/api/v1/auth/login` | 手机号 + 密码登录 |
| 鉴权 | POST | `/api/v1/auth/register` | 注册（自动初始化配额） |
| 鉴权 | GET  | `/api/v1/auth/me` | 当前用户 |
| 工作台 | GET | `/api/v1/dashboard` | KPI 聚合数据 |
| 工作台 | GET | `/api/v1/dashboard/trend` | 得分趋势 |
| 工作台 | GET | `/api/v1/dashboard/recommend` | 推荐套题 |
| 工作台 | GET | `/api/v1/dashboard/form-stats` | 选形式页统计 |
| 题库 | GET | `/api/v1/question-sets` | 套题列表 |
| 题库 | GET | `/api/v1/question-sets/{id}` | 套题详情（含题目） |
| 场次 | POST | `/api/v1/sessions` | 开始一场模拟 |
| 场次 | GET | `/api/v1/sessions/{id}` | 场次详情 |
| 场次 | POST | `/api/v1/sessions/{id}/questions/{sq_id}/answer` | 提交单题作答 |
| 场次 | POST | `/api/v1/sessions/{id}/finish` | 结束场次 + 生成报告 |
| 场次 | GET | `/api/v1/sessions/{id}/questions/{sq_id}` | 逐题详情回放 |
| 报告 | GET | `/api/v1/reports/{id}` | 报告详情 |
| 报告 | GET | `/api/v1/reports/by-session/{session_id}` | 按场次取报告 |
| 群面 | GET | `/api/v1/group/sessions/{session_id}` | 群面讨论详情 |
| 群面 | POST | `/api/v1/group/sessions/{session_id}/raise` | 举手发言 |

统一响应结构：`{ "code": 0, "msg": "ok", "data": ... }`

---

## 核心流程

```
工作台 ──开始全真模拟──▶ 选形式 ──下一步──▶ 选套题 ──开始作答──▶ 作答（逐题提交） ──生成报告──▶ 综合报告
                                                                                      └─▶ 逐题详情/回放
```

- 作答页支持「语音」和「文字」两种模式（demo 用模拟转写，未接真实 ASR/TTS）
- 每题提交后由后端 `crud/session.submit_answer` 生成 demo 维度评分 / 指标 / 高光 / 建议
- 全部题完成后调用 `finish` 自动生成综合报告 + 扣减配额 + 更新连续天数 + 写练习历史

---

## 数据库说明

后端 ORM 覆盖了 `mock_interview_schema.sql` 中的全部 20+ 张表（用户域 / 招聘域 / 题库域 / 配置域 / 模拟域 / 群面域 / 报告域），并额外增加 `users.password_hash` 字段以支持密码登录。

两种初始化方式任选其一：

1. **推荐**：`python seed.py` —— 按 ORM 自动建表（含 password_hash）+ 写入 demo 数据
2. **手动 SQL**：先执行 `mock_interview_schema.sql` 建表，再执行 `backend/db/seed.sql` 插入数据；并补一条 `ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NOT NULL DEFAULT '' AFTER phone;`

---

## 设计令牌（与 HTML 原型同步）

| 用途 | 颜色 |
| --- | --- |
| 主色 | `#3E63DD` |
| 成功绿 | `#2FA36B` |
| 警示橙 | `#E8912D` |
| 背景 | `#F7F8FA` |
| 卡片 | `#FFFFFF` |

卡片圆角 16px / 按钮 10px / 胶囊 999px。前端已在 `src/styles/global.css` 与 `App.vue` 的 `a-config-provider` 主题 token 中同步配置。

---

## 待办 / 后续

- [ ] 接入真实 ASR（语音转写）+ TTS（AI 面试官语音）
- [ ] 群面 AI 候选人 prompt 工程（当前为数据结构预留）
- [ ] 「同岗位百分位」真实埋点统计（当前为 demo 估算）
- [ ] 简历 & JD 解析（v1.1，对应 P2）
- [ ] 移动端断点细化（375px）

---

## 📄 License

MIT License —— 欢迎 fork、学习、二次开发。

## 👤 作者

**刘怡然** · 智能科学与技术 · 求职意向：AI 应用开发实习

- 仓库：`https://github.com/<your-name>/mockwise`
- 联系方式：`<your-email@example.com>`

> 把上面仓库地址和邮箱替换成你的真实信息再 push。
