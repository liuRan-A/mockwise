-- =====================================================================
-- Mockwise · 初始化 seed 数据
-- 配合 mock_interview_schema.sql 使用，先建表后插入
-- =====================================================================
USE `mockwise`;

-- 用户（密码: 123456，bcrypt hash 见 app/core/security.py 实时生成，这里仅占位）
INSERT INTO `users` (`phone`, `password_hash`, `nickname`, `avatar_url`, `target_position`, `status`)
VALUES ('13800000000', '$2b$12$placeholder', '李哲', '', 'AI 方案架构师', 'active');
-- 注：demo 登录用 password_hash 字段会被 register 接口重新设置；推荐用 /auth/register 创建账号

-- 月度配额
INSERT INTO `user_quotas` (`user_id`, `month_key`, `simulated_left`, `simulated_total`)
VALUES (1, DATE_FORMAT(NOW(), '%Y-%m'), 3, 3);

-- 连续天数
INSERT INTO `user_streaks` (`user_id`, `current_days`, `best_days`, `last_practice_at`)
VALUES (1, 12, 18, CURRENT_DATE);

-- 历史得分
INSERT INTO `practice_history` (`user_id`, `session_id`, `total_score`, `set_name`, `practiced_at`) VALUES
  (1, 0, 64.0, '产品 sense 入门 6 题', DATE_SUB(NOW(), INTERVAL 26 DAY)),
  (1, 0, 71.0, '互联网产品经理 8 题', DATE_SUB(NOW(), INTERVAL 21 DAY)),
  (1, 0, 74.2, '互联网产品经理 8 题', DATE_SUB(NOW(), INTERVAL 14 DAY)),
  (1, 0, 68.9, '下沉市场增长 6 题', DATE_SUB(NOW(), INTERVAL 7 DAY)),
  (1, 0, 78.0, 'AI 方案架构 10 题', DATE_SUB(NOW(), INTERVAL 1 DAY));

-- 套题
INSERT INTO `question_sets` (`name`, `industry`, `position_type`, `difficulty`, `description`, `question_count`, `est_minutes`, `match_score`) VALUES
  ('互联网产品经理 · 8 题', '互联网', '产品', 'medium', '覆盖产品 sense、数据拆解、跨团队协作等核心能力，按互联网大厂标准设计。', 8, 25, 92.0),
  ('下沉市场增长 · 6 题', '互联网', '增长', 'medium', '聚焦三四五线下沉市场的获客、履约与提频策略，含 1 道真实群面试题。', 6, 22, 85.0),
  ('AI 方案架构 · 10 题', 'AI / SaaS', '研发', 'hard', '面向资深候选人，考察 RAG / Agent / 模型选型 / 线上稳定性等大厂 AI 方案能力。', 10, 32, 88.0);

-- 题目（套题 1 的 8 道题）
INSERT INTO `questions` (`set_id`, `seq`, `form_type`, `difficulty`, `category`, `dimension`, `content`, `ref_answer`, `time_limit_s`) VALUES
  (1, 1, 'structured', 'medium', '自我介绍', '岗位匹配', '请用 2 分钟介绍你自己，并说明你为什么适合 AI 方案架构师这个岗位。', '突出过往 AI 落地项目 + 与岗位能力项的对应。', 180),
  (1, 2, 'structured', 'medium', '专业题', '专业深度', '请拆解一个你负责过的 AI 项目，重点说明数据 / 模型 / 工程三端的取舍。', '数据治理 → 模型选型 → 工程稳定性三段式。', 180),
  (1, 3, 'structured', 'medium', '情景题', '应急应变', '上线前一天，测试环境发现核心下单链路有 5% 的概率超时，但修复方案要改动三天前刚封版的代码。作为负责人，你如何处理？', '先止血 → 评估影响 → 决策回滚/灰度 → 复盘流程。', 180),
  (1, 4, 'structured', 'medium', '情景题', '逻辑结构', '跨团队协作：你的 AI 方案需要算法、工程、产品三方对齐，但三方目标不一致，你如何推进？', '识别共同利益 → 设定里程碑 → 建立同步机制。', 180),
  (1, 5, 'structured', 'hard', '专业题', '专业深度', '请设计一个面向客服的 RAG 方案，覆盖召回、重排、幻觉控制三个关键点。', '召回多样性 + 重排业务过滤 + 幻觉兜底策略。', 200),
  (1, 6, 'structured', 'medium', '情景题', '语言表达', '如果业务方坚持一个你认为不合理的 AI 需求，你如何在 5 分钟内说服他？', '结论先行 + 数据 + 风险预案。', 120),
  (1, 7, 'structured', 'medium', '专业题', '逻辑结构', '如何评估一个 Agent 系统的线上稳定性？给出你的核心指标和告警阈值。', 'SLA + 召回率 + 工具调用成功率 + 成本。', 180),
  (1, 8, 'structured', 'hard', '情景题', '应急应变', '上线后 1 小时发现 AI 回复出现涉政风险内容，你的应急流程是什么？', '立即熔断 → 风控介入 → 回溯样本 → 复盘。', 180);

-- 套题 2 / 3 各加 1 道示范题
INSERT INTO `questions` (`set_id`, `seq`, `form_type`, `difficulty`, `category`, `dimension`, `content`, `ref_answer`, `time_limit_s`) VALUES
  (2, 1, 'group', 'medium', '无领导小组', '逻辑结构', '请围绕「下沉市场增长」讨论：在预算 50 万、3 个月内，你会如何为一款本地生活 App 提升下沉市场日活？', '聚焦获客渠道 + 履约 + 提频的组合策略。', 60),
  (3, 1, 'structured', 'hard', '专业题', '专业深度', '请对比 RAG 与微调两种方案的适用场景、成本与上线难度。', 'RAG 适合知识更新快、微调适合风格固化。', 200);
