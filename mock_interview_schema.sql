-- =====================================================================
-- Mockwise · AI 模拟面试助手 — 数据库 Schema (MySQL 8.0+)
-- ---------------------------------------------------------------------
-- 设计原则：
--   1. 数据建模覆盖现有画布原型中的所有可见字段与交互
--      （工作台 / 选形式 / 选套题 / 作答 / 群面 / 报告 / 逐题回放）
--   2. 主键统一 BIGINT AUTO_INCREMENT；时间统一 DATETIME(3) 毫秒精度
--   3. 状态字段用 ENUM 约束取值；扩展字段用 JSON 列兜底
--   4. 关键查询路径加二级索引，热点写路径加唯一索引
--   5. 所有表带 created_at / updated_at，前缀命名避免与 MySQL 关键字冲突
--
-- 表族一览：
--   用户域    users / user_quotas / user_streaks / practice_history
--   招聘域    positions / jd_documents / resumes
--   题库域    question_sets / questions
--   配置域    interview_configs
--   模拟域    interview_sessions / session_questions
--             / session_scores / session_metrics
--             / session_highlights / session_recommendations
--   群面域    group_discussions / group_members / group_timeline
--   报告域    reports / report_highlights / report_recommendations
-- =====================================================================

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------
-- 1. 用户域
-- ---------------------------------------------------------------------

DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id`              BIGINT       NOT NULL AUTO_INCREMENT,
  `phone`           VARCHAR(20)  NOT NULL                COMMENT '手机号（登录用）',
  `nickname`        VARCHAR(64)  NOT NULL DEFAULT ''     COMMENT '昵称 / 显示名',
  `avatar_url`      VARCHAR(255) NOT NULL DEFAULT ''     COMMENT '头像',
  `target_position` VARCHAR(128) NOT NULL DEFAULT ''     COMMENT '目标岗位（冗余展示用）',
  `status`          ENUM('active','paused','churned') NOT NULL DEFAULT 'active',
  `last_login_at`   DATETIME(3)  NULL,
  `created_at`      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_users_phone` (`phone`),
  KEY `ix_users_status_last_login` (`status`, `last_login_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户主表';

DROP TABLE IF EXISTS `user_quotas`;
CREATE TABLE `user_quotas` (
  `id`              BIGINT       NOT NULL AUTO_INCREMENT,
  `user_id`         BIGINT       NOT NULL,
  `month_key`       CHAR(7)      NOT NULL                COMMENT 'YYYY-MM，月度配额',
  `simulated_left`  SMALLINT     NOT NULL DEFAULT 0      COMMENT '本月剩余模拟次数',
  `simulated_total` SMALLINT     NOT NULL DEFAULT 0      COMMENT '本月总额度',
  `updated_at`      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_quotas_user_month` (`user_id`, `month_key`),
  CONSTRAINT `fk_user_quotas_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户月度配额（工作台「本月剩余 N/M 次」）';

DROP TABLE IF EXISTS `user_streaks`;
CREATE TABLE `user_streaks` (
  `user_id`           BIGINT       NOT NULL,
  `current_days`      SMALLINT     NOT NULL DEFAULT 0    COMMENT '当前连续天数',
  `best_days`         SMALLINT     NOT NULL DEFAULT 0    COMMENT '历史最长连续',
  `last_practice_at`  DATE         NULL                  COMMENT '最近一次练习日期',
  `updated_at`        DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`user_id`),
  CONSTRAINT `fk_user_streaks_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户连续练习天数（工作台「连续练习 N 天」）';

DROP TABLE IF EXISTS `practice_history`;
CREATE TABLE `practice_history` (
  `id`             BIGINT       NOT NULL AUTO_INCREMENT,
  `user_id`        BIGINT       NOT NULL,
  `session_id`     BIGINT       NOT NULL                COMMENT '关联模拟场次',
  `total_score`    DECIMAL(5,2) NOT NULL DEFAULT 0      COMMENT '当次综合得分',
  `set_name`       VARCHAR(128) NOT NULL DEFAULT ''     COMMENT '冗余：套题名（避免连表）',
  `practiced_at`   DATETIME(3)  NOT NULL                COMMENT '练习完成时间',
  PRIMARY KEY (`id`),
  KEY `ix_practice_history_user_time` (`user_id`, `practiced_at` DESC),
  CONSTRAINT `fk_practice_history_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='练习历史（工作台推荐练习 / 趋势图取数）';

-- ---------------------------------------------------------------------
-- 2. 招聘域：岗位 / JD / 简历
-- ---------------------------------------------------------------------

DROP TABLE IF EXISTS `positions`;
CREATE TABLE `positions` (
  `id`          BIGINT       NOT NULL AUTO_INCREMENT,
  `user_id`     BIGINT       NOT NULL,
  `name`        VARCHAR(128) NOT NULL                    COMMENT '岗位名，如「AI 方案架构师」',
  `level`       VARCHAR(32)  NOT NULL DEFAULT ''         COMMENT '职级',
  `industry`    VARCHAR(64)  NOT NULL DEFAULT ''         COMMENT '行业',
  `target_company` VARCHAR(128) NOT NULL DEFAULT ''      COMMENT '目标公司（可空）',
  `is_active`   TINYINT(1)   NOT NULL DEFAULT 1         COMMENT '是否当前目标岗位',
  `created_at`  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `ix_positions_user_active` (`user_id`, `is_active`),
  CONSTRAINT `fk_positions_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户目标岗位';

DROP TABLE IF EXISTS `jd_documents`;
CREATE TABLE `jd_documents` (
  `id`           BIGINT       NOT NULL AUTO_INCREMENT,
  `user_id`      BIGINT       NOT NULL,
  `position_id`  BIGINT       NULL,
  `raw_text`     MEDIUMTEXT   NOT NULL                    COMMENT 'JD 原文',
  `parsed_json`  JSON         NULL                        COMMENT 'AI 解析结果：能力项 / 关键词 / 权重',
  `title`        VARCHAR(255) NOT NULL DEFAULT ''         COMMENT 'JD 名称',
  `created_at`   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `ix_jd_user_position` (`user_id`, `position_id`),
  CONSTRAINT `fk_jd_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='JD 文档与 AI 解析';

DROP TABLE IF EXISTS `resumes`;
CREATE TABLE `resumes` (
  `id`           BIGINT       NOT NULL AUTO_INCREMENT,
  `user_id`      BIGINT       NOT NULL,
  `raw_text`     MEDIUMTEXT   NOT NULL                    COMMENT '简历原文',
  `parsed_json`  JSON         NULL                        COMMENT 'AI 解析：教育 / 项目 / 技能 / 工作年限',
  `file_url`     VARCHAR(255) NOT NULL DEFAULT ''         COMMENT '上传文件 URL（可空）',
  `created_at`   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `ix_resumes_user` (`user_id`),
  CONSTRAINT `fk_resumes_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='简历';

-- ---------------------------------------------------------------------
-- 3. 题库域：套题 / 题目
-- ---------------------------------------------------------------------

DROP TABLE IF EXISTS `question_sets`;
CREATE TABLE `question_sets` (
  `id`            BIGINT       NOT NULL AUTO_INCREMENT,
  `name`          VARCHAR(128) NOT NULL                   COMMENT '套题名',
  `industry`      VARCHAR(64)  NOT NULL DEFAULT ''        COMMENT '行业',
  `position_type` VARCHAR(64)  NOT NULL DEFAULT ''        COMMENT '岗位类型：产品 / 研发 / 运营 …',
  `difficulty`    ENUM('easy','medium','hard') NOT NULL DEFAULT 'medium',
  `description`   VARCHAR(512) NOT NULL DEFAULT ''        COMMENT '套题简介',
  `cover_url`     VARCHAR(255) NOT NULL DEFAULT ''        COMMENT '封面图',
  `question_count` SMALLINT    NOT NULL DEFAULT 0         COMMENT '题目数（冗余）',
  `est_minutes`   SMALLINT     NOT NULL DEFAULT 0         COMMENT '预计总时长',
  `match_score`   DECIMAL(5,2) NOT NULL DEFAULT 0         COMMENT '对当前用户目标的适配度',
  `is_published`  TINYINT(1)   NOT NULL DEFAULT 1,
  `created_at`    DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `ix_qs_published_position` (`is_published`, `position_type`, `difficulty`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='套题（选套题页一卡片对应一行）';

DROP TABLE IF EXISTS `questions`;
CREATE TABLE `questions` (
  `id`              BIGINT       NOT NULL AUTO_INCREMENT,
  `set_id`          BIGINT       NOT NULL,
  `seq`             SMALLINT     NOT NULL                 COMMENT '套题内序号',
  `form_type`       ENUM('structured','group','semi') NOT NULL DEFAULT 'structured' COMMENT '适用面试形式',
  `difficulty`      ENUM('easy','medium','hard') NOT NULL DEFAULT 'medium',
  `category`        VARCHAR(32)  NOT NULL DEFAULT ''       COMMENT '题型：自我介绍 / 情景题 / 专业题',
  `dimension`       VARCHAR(32)  NOT NULL DEFAULT ''       COMMENT '考察维度：应急应变 / 逻辑结构 …',
  `content`         TEXT         NOT NULL                 COMMENT '题干',
  `attachments`     JSON         NULL                     COMMENT '题目材料 / 数据 / 图表链接',
  `ref_answer`      TEXT         NULL                     COMMENT '参考答案要点',
  `time_limit_s`    SMALLINT     NOT NULL DEFAULT 120     COMMENT '作答时长（秒）',
  `created_at`      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_questions_set_seq` (`set_id`, `seq`),
  KEY `ix_questions_form_category` (`form_type`, `category`),
  CONSTRAINT `fk_questions_set` FOREIGN KEY (`set_id`) REFERENCES `question_sets`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='题目';

-- ---------------------------------------------------------------------
-- 4. 面试配置
-- ---------------------------------------------------------------------

DROP TABLE IF EXISTS `interview_configs`;
CREATE TABLE `interview_configs` (
  `id`             BIGINT       NOT NULL AUTO_INCREMENT,
  `user_id`        BIGINT       NOT NULL,
  `position_id`    BIGINT       NULL,
  `form_type`      ENUM('structured','group','semi') NOT NULL DEFAULT 'structured',
  `voice_mode`     ENUM('text','voice','mixed') NOT NULL DEFAULT 'voice' COMMENT '作答方式',
  `difficulty`     ENUM('easy','medium','hard') NOT NULL DEFAULT 'medium',
  `language`       VARCHAR(16)  NOT NULL DEFAULT 'zh-CN',
  `enable_followup` TINYINT(1) NOT NULL DEFAULT 1        COMMENT '是否允许 AI 追问',
  `peer_count`     TINYINT      NOT NULL DEFAULT 0        COMMENT '群面候选人数（仅 group）',
  `extra_json`     JSON         NULL                     COMMENT '扩展配置项',
  `created_at`     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `ix_configs_user_created` (`user_id`, `created_at` DESC),
  CONSTRAINT `fk_configs_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='单次模拟的运行配置';

-- ---------------------------------------------------------------------
-- 5. 模拟场次：sessions / 单题快照 / 评分 / 指标 / 高光 / 建议
-- ---------------------------------------------------------------------

DROP TABLE IF EXISTS `interview_sessions`;
CREATE TABLE `interview_sessions` (
  `id`           BIGINT       NOT NULL AUTO_INCREMENT,
  `user_id`      BIGINT       NOT NULL,
  `config_id`    BIGINT       NULL,
  `set_id`       BIGINT       NULL,
  `form_type`    ENUM('structured','group','semi') NOT NULL DEFAULT 'structured',
  `status`       ENUM('idle','preparing','running','paused','done','aborted') NOT NULL DEFAULT 'idle',
  `started_at`   DATETIME(3)  NULL,
  `ended_at`     DATETIME(3)  NULL,
  `total_score`  DECIMAL(5,2) NOT NULL DEFAULT 0        COMMENT '冗余总分（做完回填）',
  `avg_score`    DECIMAL(5,2) NOT NULL DEFAULT 0        COMMENT '冗余平均分',
  `created_at`   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `ix_sessions_user_started` (`user_id`, `started_at` DESC),
  KEY `ix_sessions_status` (`status`),
  CONSTRAINT `fk_sessions_user`  FOREIGN KEY (`user_id`)  REFERENCES `users`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_sessions_set`   FOREIGN KEY (`set_id`)   REFERENCES `question_sets`(`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_sessions_config` FOREIGN KEY (`config_id`) REFERENCES `interview_configs`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟场次（一轮完整面试）';

DROP TABLE IF EXISTS `session_questions`;
CREATE TABLE `session_questions` (
  `id`            BIGINT       NOT NULL AUTO_INCREMENT,
  `session_id`    BIGINT       NOT NULL,
  `question_id`   BIGINT       NOT NULL,
  `seq`           SMALLINT     NOT NULL                  COMMENT '本场序号',
  `phase`         ENUM('statement','group_free','summary','answer') NOT NULL DEFAULT 'answer' COMMENT '群面阶段',
  `status`        ENUM('pending','active','done','skipped') NOT NULL DEFAULT 'pending',
  `transcript`    MEDIUMTEXT   NULL                      COMMENT '实时转写全文',
  `audio_url`     VARCHAR(255) NULL                      COMMENT '作答语音文件',
  `ref_answer`    TEXT         NULL                      COMMENT '作答时定稿的参考答案（快照）',
  `total_score`   DECIMAL(5,2) NULL                      COMMENT '本题得分（冗余）',
  `duration_ms`   INT          NULL                      COMMENT '作答耗时',
  `started_at`    DATETIME(3)  NULL,
  `answered_at`   DATETIME(3)  NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_session_questions` (`session_id`, `seq`),
  KEY `ix_session_questions_q` (`question_id`),
  CONSTRAINT `fk_sq_session` FOREIGN KEY (`session_id`)  REFERENCES `interview_sessions`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_sq_question` FOREIGN KEY (`question_id`) REFERENCES `questions`(`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='一场模拟中每道题的实际作答快照';

DROP TABLE IF EXISTS `session_scores`;
CREATE TABLE `session_scores` (
  `id`                   BIGINT       NOT NULL AUTO_INCREMENT,
  `session_question_id`  BIGINT       NOT NULL,
  `dimension`            VARCHAR(32)  NOT NULL                 COMMENT '评估维度：应急应变 / 逻辑结构 …',
  `score`                DECIMAL(5,2) NOT NULL                 COMMENT '0-100',
  `comment`              VARCHAR(255) NOT NULL DEFAULT ''      COMMENT '一句话点评',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_session_scores_dim` (`session_question_id`, `dimension`),
  CONSTRAINT `fk_session_scores_sq` FOREIGN KEY (`session_question_id`) REFERENCES `session_questions`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='单题的分维度评分（每题 3-5 条）';

DROP TABLE IF EXISTS `session_metrics`;
CREATE TABLE `session_metrics` (
  `session_question_id`  BIGINT       NOT NULL,
  `wpm`                  SMALLINT     NOT NULL DEFAULT 0        COMMENT '语速（字/分钟）',
  `pause_count`          SMALLINT     NOT NULL DEFAULT 0        COMMENT '停顿次数',
  `pause_ms_total`       INT          NOT NULL DEFAULT 0        COMMENT '停顿累计毫秒',
  `filler_count`         SMALLINT     NOT NULL DEFAULT 0        COMMENT '口头禅计数',
  `interrupt_count`      SMALLINT     NOT NULL DEFAULT 0        COMMENT '打断他人（仅群面）',
  `extra_json`           JSON         NULL,
  PRIMARY KEY (`session_question_id`),
  CONSTRAINT `fk_session_metrics_sq` FOREIGN KEY (`session_question_id`) REFERENCES `session_questions`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='作答的客观指标（语速 / 停顿 / 口头禅 / 打断）';

DROP TABLE IF EXISTS `session_highlights`;
CREATE TABLE `session_highlights` (
  `id`                   BIGINT       NOT NULL AUTO_INCREMENT,
  `session_question_id`  BIGINT       NOT NULL,
  `ts_ms`                INT          NOT NULL                 COMMENT '在作答中的时间偏移',
  `category`             ENUM('highlight','filler','followup','risk') NOT NULL DEFAULT 'highlight',
  `snippet`              VARCHAR(255) NOT NULL DEFAULT ''      COMMENT '片段文本',
  PRIMARY KEY (`id`),
  KEY `ix_session_highlights_sq` (`session_question_id`, `ts_ms`),
  CONSTRAINT `fk_session_highlights_sq` FOREIGN KEY (`session_question_id`) REFERENCES `session_questions`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='逐题回放中的高光标记（亮点 / 口头禅 / 追问）';

DROP TABLE IF EXISTS `session_recommendations`;
CREATE TABLE `session_recommendations` (
  `id`                   BIGINT       NOT NULL AUTO_INCREMENT,
  `session_question_id`  BIGINT       NOT NULL,
  `kind`                 ENUM('improve','answer_key') NOT NULL DEFAULT 'improve' COMMENT 'improve=改进建议 / answer_key=参考答案',
  `content`              VARCHAR(512) NOT NULL,
  `sort_index`           SMALLINT     NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `ix_recommendations_sq` (`session_question_id`, `sort_index`),
  CONSTRAINT `fk_recommendations_sq` FOREIGN KEY (`session_question_id`) REFERENCES `session_questions`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='逐题改进建议与参考答案要点';

-- ---------------------------------------------------------------------
-- 6. 群面域
-- ---------------------------------------------------------------------

DROP TABLE IF EXISTS `group_discussions`;
CREATE TABLE `group_discussions` (
  `id`             BIGINT      NOT NULL AUTO_INCREMENT,
  `session_id`     BIGINT      NOT NULL,
  `prompt`         TEXT        NOT NULL                  COMMENT '群面题目',
  `material_json`  JSON        NULL                      COMMENT '讨论材料 / 数据点',
  `total_minutes`  SMALLINT    NOT NULL DEFAULT 18,
  `statement_sec`  SMALLINT    NOT NULL DEFAULT 60       COMMENT '个人陈述阶段秒数',
  `free_minutes`   SMALLINT    NOT NULL DEFAULT 15       COMMENT '自由讨论阶段分钟',
  `summary_sec`    SMALLINT    NOT NULL DEFAULT 120      COMMENT '总结陈词秒数',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_group_discussions_session` (`session_id`),
  CONSTRAINT `fk_group_discussions_session` FOREIGN KEY (`session_id`) REFERENCES `interview_sessions`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='群面试题材料（每场一份）';

DROP TABLE IF EXISTS `group_members`;
CREATE TABLE `group_members` (
  `id`                BIGINT       NOT NULL AUTO_INCREMENT,
  `discussion_id`     BIGINT       NOT NULL,
  `role`              ENUM('me','peer','host') NOT NULL DEFAULT 'peer',
  `name`              VARCHAR(64)  NOT NULL,
  `initial`           VARCHAR(8)   NOT NULL DEFAULT ''   COMMENT '头像字符',
  `color`             VARCHAR(16)  NOT NULL DEFAULT '#3E63DD',
  `talk_count`        SMALLINT     NOT NULL DEFAULT 0,
  `is_current_speaker` TINYINT(1)  NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `ix_group_members_disc` (`discussion_id`),
  CONSTRAINT `fk_group_members_disc` FOREIGN KEY (`discussion_id`) REFERENCES `group_discussions`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='群面小组成员（含 AI 候选人 + 用户）';

DROP TABLE IF EXISTS `group_timeline`;
CREATE TABLE `group_timeline` (
  `id`               BIGINT       NOT NULL AUTO_INCREMENT,
  `discussion_id`    BIGINT       NOT NULL,
  `member_id`        BIGINT       NOT NULL,
  `phase`            ENUM('statement','group_free','summary') NOT NULL DEFAULT 'group_free',
  `transcript`       TEXT         NULL,
  `audio_url`        VARCHAR(255) NULL,
  `started_at_ms`    INT          NOT NULL DEFAULT 0     COMMENT '相对讨论开始的毫秒偏移',
  `duration_ms`      INT          NOT NULL DEFAULT 0,
  `is_interrupted`   TINYINT(1)   NOT NULL DEFAULT 0     COMMENT '是否被打断（发言权违规）',
  `cited_count`      SMALLINT     NOT NULL DEFAULT 0     COMMENT '被他人引用次数',
  PRIMARY KEY (`id`),
  KEY `ix_group_timeline_disc_started` (`discussion_id`, `started_at_ms`),
  KEY `ix_group_timeline_member` (`member_id`),
  CONSTRAINT `fk_group_timeline_disc`   FOREIGN KEY (`discussion_id`) REFERENCES `group_discussions`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_group_timeline_member` FOREIGN KEY (`member_id`)     REFERENCES `group_members`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='群面发言时间线（气泡与语音波形）';

-- ---------------------------------------------------------------------
-- 7. 报告域
-- ---------------------------------------------------------------------

DROP TABLE IF EXISTS `reports`;
CREATE TABLE `reports` (
  `id`             BIGINT       NOT NULL AUTO_INCREMENT,
  `session_id`     BIGINT       NOT NULL,
  `user_id`        BIGINT       NOT NULL                COMMENT '冗余，便于按用户取最近报告',
  `form_type`      ENUM('structured','group','semi') NOT NULL DEFAULT 'structured',
  `total_score`    DECIMAL(5,2) NOT NULL DEFAULT 0,
  `dimensions`     JSON         NULL                    COMMENT '[{name,score,comment},...]',
  `comparison`     JSON         NULL                    COMMENT '跨场对比：较上场 / 同岗位百分位',
  `overview`       VARCHAR(512) NOT NULL DEFAULT '',
  `duration_sec`   INT          NOT NULL DEFAULT 0,
  `created_at`     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_reports_session` (`session_id`),
  KEY `ix_reports_user_created` (`user_id`, `created_at` DESC),
  CONSTRAINT `fk_reports_session` FOREIGN KEY (`session_id`) REFERENCES `interview_sessions`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='综合评分报告（每场一份）';

DROP TABLE IF EXISTS `report_highlights`;
CREATE TABLE `report_highlights` (
  `id`          BIGINT       NOT NULL AUTO_INCREMENT,
  `report_id`   BIGINT       NOT NULL,
  `ts_ms`       INT          NOT NULL,
  `snippet`     VARCHAR(255) NOT NULL DEFAULT '',
  `category`    ENUM('highlight','risk') NOT NULL DEFAULT 'highlight',
  PRIMARY KEY (`id`),
  KEY `ix_report_highlights_report` (`report_id`, `ts_ms`),
  CONSTRAINT `fk_report_highlights_report` FOREIGN KEY (`report_id`) REFERENCES `reports`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='报告中按时间整理的高光片段';

DROP TABLE IF EXISTS `report_recommendations`;
CREATE TABLE `report_recommendations` (
  `id`          BIGINT       NOT NULL AUTO_INCREMENT,
  `report_id`   BIGINT       NOT NULL,
  `kind`        ENUM('improve','practice','review') NOT NULL DEFAULT 'improve',
  `content`     VARCHAR(512) NOT NULL,
  `sort_index`  SMALLINT     NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `ix_report_recommendations` (`report_id`, `sort_index`),
  CONSTRAINT `fk_report_recommendations_report` FOREIGN KEY (`report_id`) REFERENCES `reports`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='报告中的改进建议 / 推荐练习';

-- ---------------------------------------------------------------------
-- 8. 视图：方便前端 / API 一次性取工作台所需聚合数据
-- ---------------------------------------------------------------------

DROP VIEW IF EXISTS `v_user_dashboard`;
CREATE VIEW `v_user_dashboard` AS
SELECT
  u.id                                      AS user_id,
  u.nickname,
  u.target_position,
  COALESCE(q.simulated_left, 0)             AS simulated_left,
  COALESCE(q.simulated_total, 0)            AS simulated_total,
  COALESCE(s.current_days, 0)               AS streak_days,
  COALESCE((SELECT AVG(ph.total_score)
              FROM practice_history ph
             WHERE ph.user_id = u.id
               AND ph.practiced_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)), 0) AS avg_score_30d,
  COALESCE((SELECT MAX(ph.total_score)
              FROM practice_history ph
             WHERE ph.user_id = u.id), 0)  AS best_score,
  COALESCE((SELECT COUNT(*)
              FROM practice_history ph
             WHERE ph.user_id = u.id), 0)   AS total_sessions
FROM users u
LEFT JOIN user_quotas q
       ON q.user_id = u.id AND q.month_key = DATE_FORMAT(NOW(), '%Y-%m')
LEFT JOIN user_streaks s
       ON s.user_id = u.id;

SET FOREIGN_KEY_CHECKS = 1;

-- =====================================================================
-- 初始化建议（按场景 demo 数据）
-- =====================================================================

-- INSERT INTO `users` (`phone`,`nickname`) VALUES ('13800000000','李哲');
-- INSERT INTO `positions` (`user_id`,`name`,`level`,`industry`) VALUES (1,'AI 方案架构师','P6','AI / SaaS');
-- INSERT INTO `user_quotas` (`user_id`,`month_key`,`simulated_left`,`simulated_total`) VALUES (1, DATE_FORMAT(NOW(),'%Y-%m'), 3, 3);
-- INSERT INTO `user_streaks` (`user_id`,`current_days`,`best_days`,`last_practice_at`) VALUES (1, 12, 18, CURRENT_DATE);
-- INSERT INTO `question_sets` (`name`,`position_type`,`difficulty`,`question_count`,`est_minutes`,`match_score`) VALUES ('互联网产品经理 · 8 题','产品','medium',8,25,92.0);
-- INSERT INTO `interview_configs` (`user_id`,`form_type`,`voice_mode`,`difficulty`) VALUES (1,'structured','voice','medium');
-- INSERT INTO `interview_sessions` (`user_id`,`config_id`,`set_id`,`form_type`,`status`,`started_at`,`ended_at`,`total_score`,`avg_score`)
-- VALUES (1,1,1,'structured','done',NOW(),NOW(),78.0,74.2);
