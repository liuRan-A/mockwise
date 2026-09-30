# MockWise 后端工程体系化演进路线（验证基线）

> 目标：把 MockWise 从「Prompt + 单轮 LLM 调用的 Demo」升级为具备完整工程能力的产品级后端。
> 方法：**逐维度审计 → 逐阶段实现 → 每阶段给出可验证证据**，不一次性堆叠，不盲目上多智能体炫技。
> 审计时间：2026-09-30。审计对象：`backend/app` 全部源码 + `requirements.txt`。

---

## 一、当前现状速览（已实现的好地基）

| 能力 | 现状 | 评价 |
| --- | --- | --- |
| Web 框架 / 接口 | FastAPI + 路由分层（`api/v1/*`）+ 统一响应 `R{code,msg,data}` + `Page` 分页 | ✅ 规范 |
| ORM / 数据库 | SQLAlchemy 2.0 + MySQL，有 `pool_pre_ping`/`pool_recycle`，`get_db` 每请求一会话 | ✅ 可用 |
| 鉴权 | JWT + `get_current_user` / `get_admin_user` 两档角色 | ⚠️ 仅 2 档，无细粒度 |
| LLM 服务 | `services/llm.py` 单轮调用 + **优雅降级**（无 Key/超时/异常 → 规则评分兜底） | ✅ 容错设计好 |
| 评分流水线 | `crud/session.py` 提交作答 → DeepSeek 评分 / 规则兜底 → 维度分 / 指标 / 高光 / 建议 / 参考答案 | ✅ 闭环完整 |
| 语音 | WebSocket 转发讯飞 IAT，未配置走演示模式 | ✅ 降级友好 |

**结论**：业务闭环（出题→作答→评分→报告→回放）已经完整且容错好。短板集中在**工程化体系**（日志/异常/权限粒度/并发安全）、**Agent 能力**（无编排/重试/校验）、**上下文工程**（无记忆/RAG/窗口管理）、**可观测性**（零）、**人机协同**（零）。

---

## 二、五维度逐条审计（现状 vs 标准）

### ① 完整后端工程体系（接口 / 数据库 / 权限 / 日志 / 异常 / 并发）
| 子项 | 现状 | 缺口 |
| --- | --- | --- |
| 接口 | `router.py` 统一注册，`R` 响应封装 | ✅ 基本完备，缺统一的查询参数校验 helper |
| 数据库 | 有连接池保活，但**未配置 `pool_size`/`max_overflow`/`pool_timeout`**；用 `create_all` 自动建表（无迁移） | ⚠️ 池规模默认 5，并发上不去；无迁移工具 |
| 权限控制 | 仅 `user`/`admin` 两档；敏感操作（删用户/删套题/发布）**无权限点、无审计、无速率限制** | ❌ 缺 RBAC 权限点 + 操作审计 |
| 日志 | 仅 `logging.basicConfig(level=INFO)`；无结构化、无 `trace_id`、无访问日志/耗时 | ❌ 完全缺失 |
| 异常捕获 | 仅 1 个 catch-all handler，且把 `f"服务器内部错误: {exc}"` **原始异常回传前端**（信息泄露）；未对 DB/422 分级 | ❌ 泄露 + 无分级体系 |
| 多用户并发 | 同步引擎 + 线程池可扛 demo 级；`group.append_timeline` **无锁**，多用户抢同一讨论时间线会竞态 | ❌ 写操作缺并发控制（行锁/乐观锁） |

### ② Agent 核心能力（拆解 / 规划 / 重试 / 校验 / 多 Agent）
| 子项 | 现状 | 缺口 |
| --- | --- | --- |
| 任务拆解 / 步骤规划 | 无 | ❌ 当前是「一次 POST 出结果」 |
| 失败重试 | 仅 `catch → 返回 None → 降级`，**无 retry/backoff**，坏 JSON 不重试 | ❌ |
| 结果校验 | 有 `_safe_json` + 字段 clamp，但**无 schema 校验 + 校验失败重试**（validate-then-retry） | ⚠️ |
| 多 Agent 协作 | 无；群面 `peer_talk` 是单 persona 单轮，**AI 互怼不流畅**（已知问题） | ❌ 需按需引入编排，而非硬上框架 |

### ③ 上下文工程（任务上下文 / 用户记忆 / 知识库 / 工具结果）
| 子项 | 现状 | 缺口 |
| --- | --- | --- |
| 用户记忆 | 简历画像（`Resume.parsed_json`）已存库，但面试中**未主动召回** weaknesses/preferences | ❌ 记忆沉睡 |
| 知识库片段 | 题目/参考答案是现成的，但每次都整段重发，无 RAG 检索注入 | ❌ |
| 工具返回结果 | 评分结果未缓存复用，可能重复调用 | ⚠️ |
| 上下文窗口 | 每次把整段 transcript（截 2500 字）重发，无分层（system/task/history/current）、无 token 预算 | ❌ 属 prompt-stuffing |

### ④ 评估与可观测性（全链路追踪 / 成功率 / 耗时 / Token 成本 / 量化评测）
| 子项 | 现状 | 缺口 |
| --- | --- | --- |
| 全链路追踪 | 无 `trace_id`，无调用链 | ❌ |
| 指标 | DeepSeek 返回的 `usage`（token）**被直接丢弃**；无成功率/耗时记录 | ❌ |
| 量化评测 | 无评测集，无法衡量评分质量稳定性 | ❌ |

### ⑤ 人机协同机制（高危操作人工审核 / 人工卡点 / 不全自动化）
| 子项 | 现状 | 缺口 |
| --- | --- | --- |
| 高危操作审核 | 删除用户/套题、发布问卷、改人设**即时生效、无审批、无审计** | ❌ |
| 人工卡点 | AI 生成内容（参考答案/评分阈值）发布前无人工复核 | ❌ |

---

## 三、分阶段路线图（每阶段可独立验证）

> 顺序设计逻辑：① 是其他所有维度的地基；④ 可观测性用于**量化验证** ②/③ 的效果，所以紧随；⑤ 人机协同在最上层，依赖 ① 的审计与 ④ 的追踪。

### Phase 1 — 工程体系地基（对应标准①）【本次实施】
- 结构化日志（`JsonFormatter` + 请求上下文 `trace_id`/`uid` 注入）
- 请求中间件：注入 `trace_id` + 访问日志（方法/路径/状态码/耗时）
- 异常体系：`AppError` 分级 + 安全 handler（不再泄露原始异常，返回 `trace_id` 便于排查）
- RBAC：权限点常量 + `require_permission` 依赖 + `admin_audit` 审计表 + 敏感操作留痕
- 并发安全：连接池规模配置（`pool_size`/`max_overflow`/`pool_timeout`）+ `append_timeline` 行锁串行化
- **验证证据**：启动后看结构化日志；注入异常看安全返回 + `trace_id`；并发脚本压 `append_timeline` 无错乱；审计表有删除/发布记录。

### Phase 2 — Agent 核心能力（对应标准②）【本次实施】
- 加固 LLM 客户端 `services/llm_client.py`：`tenacity` 网络重试+退避（超时/限流/5xx）、`structured()` 做 schema 校验+**校验失败重试**（validate-retry）、Token 用量埋点钩子（为 P4 预留）。
- 轻量 Agent 编排层 `services/agent.py`：`AgentStep`+`Plan`+`AgentContext`，实现 拆解→规划→执行→校验→重试（含兜底），框架无关、自带单测。
- 群面多智能体编排 `services/group_agent.py`：`PeerTurn`(Pydantic v1 schema 强校验)、`PeerAgent`、`GroupOrchestrator`（三阶段+轮次调度+上下文窗口+cites 引用校验）；`peer-talk` 端点改用编排生成，LLM 不可用/校验耗尽**自动降级模板**，前端无感。
- **验证证据**：沙箱自测通过 —— ① orchestrator 单测（先失败后成功 + 校验失败走兜底）；② `structured` 注入坏返回验证重试生效、耗尽抛 `UpstreamError`、字段校验生效。本机还需：`npm run dev` 跑一场群面，看 AI 轮次是否更连贯、引用彼此姓名。

### Phase 3 — 上下文工程（对应标准③）【本次实施】
- **上下文分层构建器** `services/context.py`：`ContextLayer`（SYSTEM/TASK/USER_MEMORY/KNOWLEDGE/TOOL/HISTORY）+ `ContextBuilder`，每片段带优先级，在 token 预算内**优先保留高优先级、裁剪低优先级**；必需层（priority≥9，如承载作答的 TASK）超预算也保留；同 key 去重；`assemble()` 返回 `meta`（各层纳入/裁剪、估算 token、是否超预算）供 P4 消费。
- **用户记忆层** `models/memory.py` + `crud/memory.py`：新增 `candidate_memory` 表（weak_dims/strong_dims/weak_cats/prefs/session_count），每场结束由 `update_from_session` 累积（计数+滚动均值），评分/反馈/群面时由 `retrieve_relevant` **只召回与当前维度/类别相关**的片段；无记忆返回 None（不污染上下文），样本 <2 场不给总体概览（避免以偏概全）。
- **知识片段按需检索** `services/knowledge.py`：`get_question_knowledge` 只从**本题**参考答案抽「采分点+常见失分点」，长度受控（≤360 字），无参考返回 None——绝不把全库塞进 prompt。
- **接入点**：`llm.score_answer`（预算 3200）、`llm.analyze_answer`（预算 1600，实时反馈走快路径）、`crud.session.submit_answer`、`api/v1/sessions.get_feedback`、`group_agent.generate_turn`（注入真人候选人薄弱点让 AI 群面有针对性交锋）。
- **验证证据（本次实测）**：`python scripts/verify_context.py` 22 项断言全通过 ——
  - 预算裁剪：有预算时 knowledge/user_memory 纳入、低优先级 history 被裁；极小预算时 TASK 仍保留且如实标记 `over_budget`；
  - **token 对比：全量注入 1779 → 按需注入 489，节省 72.5%**，且按需注入仍含任务/本题知识/相关记忆，不含简历全文与全库参考；
  - 记忆闭环：2 场累积后，召回「逻辑结构」只点名逻辑结构（均分 58.0）不夹带应急应变，长度 ≤240；
  - 真实装配：`import app.main` OK，`/health` 返回 200 且回写 `X-Trace-Id`，未鉴权请求正确 401，共 71 条路由（含 14 条 `/admin/content/*`）。

### Phase 4 — 评估与可观测性（对应标准④）【本次实施】
- **数据模型** `models/observability.py`：4 张表 —— `llm_call_log`（LLM 调用明细：trace/span/场景/模型/入出 token/耗时/成本/成败/**ctx_meta**）、`trace_span`（通用调用段，带 parent 用于还原链路）、`eval_run` / `eval_sample`（量化评测的汇总结论与样本级原始结果）。
- **全链路追踪** `services/tracing.py`：`scene(...)` 场景标记 + `span(...)` 调用段（父子关系）+ `attach_ctx_meta()` 承接 Phase 3 上下文元数据；把 Phase 2 暴露的用量钩子**升级为落库钩子**（`install_usage_hook`）。**铁律：所有观测写入都在 try/except 内，数据库不可用时只降频告警，绝不阻断业务。**
- **指标聚合** `services/metrics.py`：成功率、平均/P50/P95 耗时、Token 与成本、分场景拆分、按 `trace_id` 还原链路、以及消费 ctx_meta 的「平均上下文 token / 各层纳入率 / 超预算率」。
- **量化评测** `services/eval.py`：固定 6 条样本（含 1 条边界样本），支持 repeat 重复跑测**评分稳定性**（标准差/极差）；**离线模式注入确定性假 LLM（不联网、不烧钱、可复现）**，真实模式下 Token/成本从 `llm_call_log` 实取。
- **管理接口** `api/v1/observability.py`：`/admin/observability/*` 共 7 个端点，均需 `view:stats` 权限；管理后台新增「可观测性」Tab（指标卡 + 分场景表 + 上下文效果 + 一键跑评测）。
- **验证证据（本次实测）**：`python scripts/verify_observability.py` —— 8 组断言全通过（落库/元数据一次性消费/指标聚合/链路还原/评测报告/上下文指标），且**在真实 MySQL + 管理员登录下跑通了完整接口链路**（见下方实测记录）。

<details>
<summary>Phase 4 实测输出（点击展开）</summary>

```
T1 用量钩子落库   trace_id=trace-verify-001 scene=score_answer
                  tokens: prompt=800 completion=489 total=1289  latency=1234ms
                  cost_cny=0.005512  user_id=42
                  ctx_meta={"included_layers":["task","knowledge","user_memory"],...}
T3 指标聚合       总调用=5 成功=4 成功率=0.8
                  耗时: 均值=886.8ms  P50=500.0ms  P95=1926.8ms
                  tokens=3609  成本=¥0.013872  单次均值=¥0.002774
                  分场景: score_answer(2次,成功率0.5,P95=2056.7ms)
                          group_turn(2次,成功率1.0,P95=318.0ms)
                          analyze_answer(1次,成功率1.0,P95=500ms)
T4 链路还原       POST /api/v1/sessions/peer-talk → group_orchestrator.generate_turn
                  链路合计 tokens=1650 成本=¥0.006 LLM 耗时=950ms
T5 量化评测       样本=6 重复=3 总运行=18 成功率=0.8333 降级率=0.1667
                  评分稳定性: 标准差均值=1.901 最大极差=4.6
                  边界样本（作答过短）被正确识别为失败 ✓
T6 上下文指标     样本=3 平均上下文 tokens=796.3 超预算率=0.6667
                  各层纳入率={'task':1.0,'knowledge':0.3333,'user_memory':0.3333}
```
真实 MySQL 端到端：`login 200 → metrics/llm 200 → eval/run 200(run_id=3, 成功率0.8333, std=1.901, P95=1.15ms) → eval/latest 200 → eval/runs 200`；路由总数 71 → 78（新增 7 条 `/admin/observability/*`）。
</details>

### Phase 5 — 人机协同（对应标准⑤）【本次已实施 ✅】
- 高危操作「草稿 → 待审 → 管理员复核」状态机 + 审批接口 + 审计留痕
- **分级卡点**：只有 `delete / publish / unpublish` 进审批；`create / update` 即时生效
  （若全部排队，人会闭眼点通过，卡点反而失效）
- **变更快照**：提交时冻结「变更前实体 + 将写入内容」，复核人看得到要删/改的是什么
- **失败不吞**：批准后应用失败 → 回滚 + 保持 pending + 记 `last_error`，可修正后重试
- **防重复**：终态审批单再次处理抛 409（防连点/并发双审）
- **可控降级**：`APPROVAL_ENABLED=False` 时全部即时生效；`force=1` 需持 `approve` 权限
- **验证证据**：`scripts/verify_approval.py` **26 项断言全过** + 真实 MySQL 端到端
  （删除→待审→批准生效；重复批准 409；未登录 401；普通用户 403）

---

## 四、本次交付（Phase 1）文件清单
- 新增 `backend/app/core/logging_config.py` — 结构化日志
- 新增 `backend/app/core/middleware.py` — 请求上下文 + 访问日志
- 新增 `backend/app/core/errors.py` — 异常体系 + 安全 handler
- 新增 `backend/app/core/rbac.py` — 权限点 + 依赖 + 审计 helper
- 新增 `backend/app/models/audit.py` — 审计表
- 修改 `backend/app/core/database.py` — 连接池调优
- 修改 `backend/app/crud/group.py` — `append_timeline` 行锁串行
- 修改 `backend/app/api/deps.py` — 注入 `uid` 到上下文
- 修改 `backend/app/main.py` — 装配日志/中间件/异常 handler/审计模型
- 修改 `backend/app/api/v1/content.py`、`admin.py` — 敏感操作留审计痕

## 五、Phase 2 交付文件清单
- 新增 `backend/app/services/llm_client.py` — 加固 LLM 客户端（重试 + 校验重试 + 用量钩子）
- 新增 `backend/app/services/agent.py` — 轻量 Agent 编排层（含 `__main__` 自测）
- 新增 `backend/app/services/group_agent.py` — 群面多智能体编排（PeerTurn / PeerAgent / GroupOrchestrator）
- 修改 `backend/app/api/v1/sessions.py` — `peer-talk` 改用 `generate_group_turn`（返回结构不变，前端无感）
- 修改 `backend/app/services/llm.py` — `_chat_json` 委托 `llm_client.chat_json`（全局获得重试+用量）
- 修改 `backend/app/core/errors.py` — fastapi 延迟导入（核心错误模块在无 fastapi 环境也可导入，便于测试与解耦）
- 修改 `backend/requirements.txt` — 新增 `tenacity==8.2.3`

## 六、Phase 3 交付文件清单
- 新增 `backend/app/services/context.py` — 分层上下文构建器（优先级 + token 预算 + 去重 + meta 埋点，含 `__main__` 自测）
- 新增 `backend/app/services/knowledge.py` — 本题知识片段按需检索（RAG-lite，长度受控，含 `__main__` 自测）
- 新增 `backend/app/models/memory.py` + `crud/memory.py` — 候选人长期记忆表与累积/召回（滚动均值、按需点名）
- 新增 `backend/scripts/verify_context.py` — Phase 3 量化验证脚本（22 项断言：预算裁剪 / token 对比 / 记忆闭环 / 知识片段）
- 修改 `backend/app/services/llm.py` — `score_answer` 与 `analyze_answer` 均改走 `ContextBuilder`，返回 `ctx_meta`
- 修改 `backend/app/crud/session.py` — `submit_answer` 召回记忆+知识后评分；`analyze_transcript` 透传上下文；报告生成后写回长期记忆
- 修改 `backend/app/api/v1/sessions.py` — `get_feedback` 装配上下文、接入结构化日志
- 修改 `backend/app/services/group_agent.py` — 注入真人候选人薄弱点，让 AI 群面有针对性交锋
- 修改 `backend/app/main.py` — 注册 `CandidateMemory` 模型（自动建表）

## 七、Phase 4 交付文件清单
- 新增 `backend/app/models/observability.py` — 可观测性 4 张表（`llm_call_log` / `trace_span` / `eval_run` / `eval_sample`）
- 新增 `backend/app/services/tracing.py` — 全链路追踪层（scene / span / ctx_meta 承接 / 用量落库钩子，含 `__main__` 自测）
- 新增 `backend/app/services/metrics.py` — 指标聚合（成功率 / P50·P95 / Token / 成本 / 分场景 / 链路还原 / 上下文命中，含 `__main__` 自测）
- 新增 `backend/app/services/eval.py` — 量化评测集与执行器（固定样本 + 重复跑测稳定性 + 离线假 LLM，含 `__main__` 自测）
- 新增 `backend/app/api/v1/observability.py` — 7 个管理端点，均需 `view:stats` 权限
- 新增 `backend/scripts/verify_observability.py` — Phase 4 量化验证脚本（8 组断言，内存 SQLite，不联网不烧钱）
- 修改 `backend/app/core/config.py` — 增加单价配置（`LLM_PRICE_IN_PER_1K` / `LLM_PRICE_OUT_PER_1K` / `OBS_PERSIST`）
- 修改 `backend/app/core/rbac.py` — **修正 bug**：`record_audit` 此前误用 `user_id_var` 当 `trace_id`，导致审计表 trace_id 存的是用户 ID
- 修改 `backend/app/services/llm.py` — `score_answer` / `analyze_answer` / `analyze_resume` / `generate_reference_answer` 标注场景 + 挂载 ctx_meta
- 修改 `backend/app/services/group_agent.py` — 群面生成标注 `group_turn` 场景
- 修改 `backend/app/api/v1/router.py`、`main.py` — 注册可观测性路由与模型，启动时安装落库钩子
- 修改 `frontend/src/api/admin.js`、`frontend/src/views/Admin.vue` — 新增「可观测性」Tab（指标卡 / 分场景 / 上下文效果 / 一键评测）

## 八、Phase 5 交付文件清单（人机协同）
- 新增 `backend/app/models/approval.py` — `content_approval` 表（目标/动作/风险/payload/快照/状态/提交人/复核人/意见/trace）
- 新增 `backend/app/services/approval.py` — 审批状态机（风险分级 · requires_approval · submit · approve · reject · cancel · apply 分派）
- 新增 `backend/app/api/v1/approval.py` — 6 个审批端点，读需 `manage:content`、批准/驳回需 `approve`
- 新增 `backend/scripts/verify_approval.py` — Phase 5 验证脚本（真实 MySQL，26 项断言）
- 修改 `backend/app/core/config.py` — `APPROVAL_ENABLED` / `APPROVAL_ACTIONS` / `APPROVAL_ALLOW_SELF`
- 修改 `backend/app/api/v1/content.py` — 删除套题/题目/人设、上下架 接入人工卡点（返回 `need_approval`，`force=1` 需审批权）
- 修改 `backend/app/api/v1/router.py`、`main.py` — 注册审批路由与模型
- 修改 `frontend/src/api/admin.js`、`frontend/src/views/Admin.vue` — 新增「审批卡点」Tab（待审列表 / 详情快照 / 批准·驳回填意见）

---

## 九、五阶段验收总表（每阶段的「可验证证据」）

| 阶段 | 对应标准 | 验证方式 | 关键实测结果 |
| --- | --- | --- | --- |
| P1 工程地基 | ① 完整后端工程体系 | 结构化日志单测 + 路由装配 + 鉴权 | JSON 日志含 trace_id/uid；`/health` 回写 `X-Trace-Id`；未鉴权 401 |
| P2 Agent 能力 | ② 任务拆解/重试/校验/按需多 Agent | 注入坏返回自测 + 群面实跑 | 校验重试生效、耗尽抛 `UpstreamError`；群面 AI 会引用彼此姓名 |
| P3 上下文工程 | ③ 按需管理上下文/记忆/知识片段 | `scripts/verify_context.py` | **22 项断言全过**；全量注入 1779 → 按需 489 tokens，**节省 72.5%** |
| P4 可观测性 | ④ 全链路追踪 + 成功率/耗时/成本/评测 | `scripts/verify_observability.py` + 真实 MySQL 端到端 | **8 组断言全过**；P95 1926.8ms、评分 std 1.901、上下文均值 796 tokens |
| P5 人机协同 | ⑤ 高危操作人工审核卡点 | `scripts/verify_approval.py` + 真实 MySQL 端到端 | **26 项断言全过**；删除→待审→批准生效；重复批准 409；普通用户 403 |

### 如何一键复跑全部验证
```bash
cd backend
venv312/Scripts/python.exe scripts/verify_context.py        # P3
venv312/Scripts/python.exe scripts/verify_observability.py   # P4
venv312/Scripts/python.exe scripts/verify_approval.py        # P5（需 MySQL 可达 + 存在 admin 账号）
venv312/Scripts/python.exe -m app.services.agent             # P2 编排层自测
```

### 已知边界（诚实记录）
- 单人部署下 `APPROVAL_ALLOW_SELF=True`，提交人与复核人可以是同一人 —— 卡点的价值在于**强制一次显式确认 + 留痕**，
  不是双人复核；团队部署应设为 `False`。
- P4 的评测「离线模式」用启发式假 LLM，只验证流水线正确性与稳定性，**不代表真实模型水平**，因此不计落带率。
- 前端 `npm run build` 在 WorkBuddy 沙箱内会卡在清空 `dist/`（OneDrive + safe-delete），
  已改用 `@vue/compiler-sfc` 直接编译 SFC 作为编译结论证据；本机构建不受影响。
