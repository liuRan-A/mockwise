"""seed 脚本：在没有 SQL 客户端时，直接用 Python 初始化 demo 数据"""
import sys
from datetime import datetime, timedelta
from app.core.database import SessionLocal, engine, Base
from app.models import user as um, position as pm, question as qm, session as sm, group as gm, report as rm  # noqa
from app.core.security import hash_password


def seed():
    # 先按 ORM 自动建表（包含 ORM 新增的 password_hash 字段）
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 用户
        u = db.query(um.User).filter_by(phone="13800000000").first()
        if not u:
            u = um.User(
                phone="13800000000",
                password_hash=hash_password("123456"),
                nickname="李哲",
                target_position="AI 方案架构师",
            )
            db.add(u)
            db.flush()
            db.add(um.UserQuota(user_id=u.id, month_key=datetime.now().strftime("%Y-%m"),
                                simulated_left=3, simulated_total=3))
            db.add(um.UserStreak(user_id=u.id, current_days=12, best_days=18,
                                 last_practice_at=datetime.now().date()))
            print(f"[seed] created user id={u.id} phone=13800000000 password=123456")
        else:
            u.password_hash = hash_password("123456")
            print(f"[seed] user exists id={u.id}, password reset to 123456")

        # 历史得分
        if not db.query(um.PracticeHistory).filter_by(user_id=u.id).first():
            seeds = [
                (64.0, "产品 sense 入门 6 题", 26), (71.0, "互联网产品经理 8 题", 21),
                (74.2, "互联网产品经理 8 题", 14), (68.9, "下沉市场增长 6 题", 7),
                (78.0, "AI 方案架构 10 题", 1),
            ]
            for score, name, d in seeds:
                db.add(um.PracticeHistory(
                    user_id=u.id, session_id=0, total_score=score, set_name=name,
                    practiced_at=datetime.now() - timedelta(days=d),
                ))

        # 套题
        if not db.query(qm.QuestionSet).first():
            sets = [
                dict(name="互联网产品经理 · 8 题", industry="互联网", position_type="产品",
                     difficulty="medium", description="覆盖产品 sense、数据拆解、跨团队协作等核心能力，按互联网大厂标准设计。",
                     question_count=8, est_minutes=25, match_score=92.0),
                dict(name="下沉市场增长 · 6 题", industry="互联网", position_type="增长",
                     difficulty="medium", description="聚焦三四五线下沉市场的获客、履约与提频策略，含 1 道真实群面试题。",
                     question_count=6, est_minutes=22, match_score=85.0),
                dict(name="AI 方案架构 · 10 题", industry="AI / SaaS", position_type="研发",
                     difficulty="hard", description="面向资深候选人，考察 RAG / Agent / 模型选型 / 线上稳定性等大厂 AI 方案能力。",
                     question_count=10, est_minutes=32, match_score=88.0),
            ]
            for s in sets:
                db.add(qm.QuestionSet(**s))
            db.flush()

            # 套题 1 的 8 道题
            qs1 = [
                (1, "structured", "medium", "自我介绍", "岗位匹配", "请用 2 分钟介绍你自己，并说明你为什么适合 AI 方案架构师这个岗位。", "突出过往 AI 落地项目 + 与岗位能力项的对应。", 180),
                (2, "structured", "medium", "专业题", "专业深度", "请拆解一个你负责过的 AI 项目，重点说明数据 / 模型 / 工程三端的取舍。", "数据治理 → 模型选型 → 工程稳定性三段式。", 180),
                (3, "structured", "medium", "情景题", "应急应变", "上线前一天，测试环境发现核心下单链路有 5% 的概率超时，但修复方案要改动三天前刚封版的代码。作为负责人，你如何处理？", "先止血 → 评估影响 → 决策回滚/灰度 → 复盘流程。", 180),
                (4, "structured", "medium", "情景题", "逻辑结构", "跨团队协作：你的 AI 方案需要算法、工程、产品三方对齐，但三方目标不一致，你如何推进？", "识别共同利益 → 设定里程碑 → 建立同步机制。", 180),
                (5, "structured", "hard", "专业题", "专业深度", "请设计一个面向客服的 RAG 方案，覆盖召回、重排、幻觉控制三个关键点。", "召回多样性 + 重排业务过滤 + 幻觉兜底策略。", 200),
                (6, "structured", "medium", "情景题", "语言表达", "如果业务方坚持一个你认为不合理的 AI 需求，你如何在 5 分钟内说服他？", "结论先行 + 数据 + 风险预案。", 120),
                (7, "structured", "medium", "专业题", "逻辑结构", "如何评估一个 Agent 系统的线上稳定性？给出你的核心指标和告警阈值。", "SLA + 召回率 + 工具调用成功率 + 成本。", 180),
                (8, "structured", "hard", "情景题", "应急应变", "上线后 1 小时发现 AI 回复出现涉政风险内容，你的应急流程是什么？", "立即熔断 → 风控介入 → 回溯样本 → 复盘。", 180),
            ]
            set1 = db.query(qm.QuestionSet).first()
            for seq, ft, df, cat, dim, content, ref, tl in qs1:
                db.add(qm.Question(set_id=set1.id, seq=seq, form_type=ft, difficulty=df,
                                   category=cat, dimension=dim, content=content, ref_answer=ref, time_limit_s=tl))
            # 套题 2 / 3 各补齐完整题库
            set2 = db.query(qm.QuestionSet).filter_by(name="下沉市场增长 · 6 题").first()
            if set2:
                qs2 = [
                    (1, "group", "medium", "无领导小组", "逻辑结构",
                     "请围绕「下沉市场增长」讨论：在预算 50 万、3 个月内，你会如何为一款本地生活 App 提升下沉市场日活？",
                     "聚焦获客渠道 + 履约 + 提频的组合策略，明确优先级与 ROI 估算。", 60),
                    (2, "structured", "medium", "情景题", "应急应变",
                     "某三线城市地推团队反馈：App 安装后次日留存仅 18%，远低于一二线城市的 35%。你会如何排查并优化？",
                     "分渠道归因 + 首次体验路径分析 + 本地化内容适配。", 180),
                    (3, "structured", "medium", "专业题", "专业深度",
                     "请拆解下沉市场用户的「价格敏感度」与「社交裂变意愿」两个核心特征，给出对应的产品策略。",
                     "低价钩子 + 拼团/助力社交裂变 + 履约确定性保障。", 180),
                    (4, "structured", "hard", "情景题", "逻辑结构",
                     "如果你的下沉市场增长方案和现有品牌定位冲突（高端品牌做低价裂变），你如何平衡？",
                     "子品牌隔离 + 用户分层运营 + 流量承接策略。", 180),
                    (5, "structured", "medium", "专业题", "岗位匹配",
                     "你过去做过哪些与下沉市场相关的工作？最大的踩坑是什么？",
                     "突出具体数据 + 复盘能力 + 对下沉用户真实场景的理解。", 180),
                    (6, "structured", "medium", "情景题", "语言表达",
                     "请用 1 分钟向 CEO 汇报你的下沉市场 3 个月增长方案的核心逻辑。",
                     "结论先行（目标+策略+预期）+ 风险预案。", 120),
                ]
                for seq, ft, df, cat, dim, content, ref, tl in qs2:
                    db.add(qm.Question(set_id=set2.id, seq=seq, form_type=ft, difficulty=df,
                                       category=cat, dimension=dim, content=content, ref_answer=ref, time_limit_s=tl))

            set3 = db.query(qm.QuestionSet).filter_by(name="AI 方案架构 · 10 题").first()
            if set3:
                qs3 = [
                    (1, "structured", "hard", "专业题", "专业深度",
                     "请对比 RAG 与微调两种方案的适用场景、成本与上线难度。",
                     "RAG 适合知识更新快、微调适合风格固化；成本上 RAG 工程成本低、微调算力成本高。", 200),
                    (2, "structured", "hard", "专业题", "逻辑结构",
                     "请设计一个面向客服的 RAG 方案，覆盖召回、重排、幻觉控制三个关键点。",
                     "召回多样性 + 重排业务过滤 + 幻觉兜底（引用溯源 + 兜底话术）。", 200),
                    (3, "structured", "hard", "情景题", "应急应变",
                     "上线后 1 小时发现 AI 回复出现涉政风险内容，你的应急流程是什么？",
                     "立即熔断 → 风控介入 → 回溯样本 → 复盘加固。", 180),
                    (4, "structured", "medium", "情景题", "逻辑结构",
                     "跨团队协作：你的 AI 方案需要算法、工程、产品三方对齐，但三方目标不一致，你如何推进？",
                     "识别共同利益 → 设定里程碑 → 建立同步机制。", 180),
                    (5, "structured", "hard", "专业题", "专业深度",
                     "如何评估一个 Agent 系统的线上稳定性？给出你的核心指标和告警阈值。",
                     "SLA 99.9% + 工具调用成功率 >95% + 单次成本阈值 + 召回率监控。", 200),
                    (6, "structured", "medium", "情景题", "语言表达",
                     "如果业务方坚持一个你认为不合理的 AI 需求，你如何在 5 分钟内说服他？",
                     "结论先行 + 数据对比 + 风险预案 + 替代方案。", 120),
                    (7, "structured", "hard", "专业题", "专业深度",
                     "请说明你在模型选型时如何权衡效果、延迟、成本？给一个具体决策案例。",
                     "效果基准 → 延迟约束 → 成本测算 → A/B 验证。", 200),
                    (8, "structured", "medium", "情景题", "应急应变",
                     "上线前一天，测试环境发现核心下单链路有 5% 的概率超时，但修复方案要改动三天前刚封版的代码。作为负责人，你如何处理？",
                     "先止血 → 评估影响 → 决策回滚/灰度 → 复盘流程。", 180),
                    (9, "structured", "hard", "专业题", "逻辑结构",
                     "请拆解你负责过的一个 AI 项目，重点说明数据 / 模型 / 工程三端的取舍。",
                     "数据治理 → 模型选型 → 工程稳定性三段式，突出量化结果。", 200),
                    (10, "structured", "medium", "情景题", "岗位匹配",
                     "请用 2 分钟介绍你自己，并说明你为什么适合 AI 方案架构师这个岗位。",
                     "突出过往 AI 落地项目 + 与岗位能力项的对应。", 180),
                ]
                for seq, ft, df, cat, dim, content, ref, tl in qs3:
                    db.add(qm.Question(set_id=set3.id, seq=seq, form_type=ft, difficulty=df,
                                       category=cat, dimension=dim, content=content, ref_answer=ref, time_limit_s=tl))
            print("[seed] created 3 question sets + 24 questions")

        # —— 专项练习题集（industry="专项练习" 作为标记，position_type=专项分类名）——
        if not db.query(qm.QuestionSet).filter_by(industry="专项练习").first():
            special_sets = [
                dict(cat="人际关系", desc="考察同事协作、向上沟通、冲突化解等职场人际处理能力。", minutes=18,
                     questions=[
                         ("你负责的项目需要另一位同事的数据支持，但他以工作量饱和为由多次拖延，导致你的进度受阻。你会如何处理？",
                          "先私下沟通了解真实困难 → 提供力所能及的帮助或向上反馈协调资源 → 明确时间节点并留书面记录。"),
                         ("你提出了一个自认为更好的方案，但直属领导坚持采用他自己的方案，你怎么办？",
                          "先执行领导决策保交付 → 私下用数据和小范围实验验证两种方案 → 拿结果再沟通，不当场顶撞。"),
                         ("团队里两位核心成员因技术路线产生激烈争执，影响了项目推进，作为协调者你如何化解？",
                          "先分别倾听诉求 → 把争论拉回到共同目标 → 用对比实验/POC 用事实说话 → 明确决策机制。"),
                         ("你发现自己参与的项目成果在汇报中被同事主要归功于自己，你会如何应对？",
                          "不公开争执 → 下次汇报前主动认领自己负责部分的讲解权 → 日常让贡献可见（周报、代码提交记录）。"),
                         ("业务部门抱怨你们技术支持响应慢、态度差，双方关系紧张，你如何改善与业务部门的关系？",
                          "先道歉并建立 SLA 响应机制 → 定期主动上门收集需求 → 用快速见效的小需求重建信任。"),
                         ("你刚加入一个已经磨合很久的团队，老成员对你有些排斥，你会如何快速融入并建立信任？",
                          "先谦逊学习摸清现状 → 主动承担别人不愿做的琐事 → 用一次小胜利证明价值，再逐步输出想法。"),
                     ]),
                dict(cat="应急应变", desc="考察突发状况下的止血、决策与复盘能力。", minutes=12,
                     questions=[
                         ("面试进行到一半，你发现面试官对你的回答明显不满意并开始看手机，你会如何调整？",
                          "主动暂停并邀请反馈 → 确认对方关心的点 → 换角度或举具体案例重新作答。"),
                         ("项目关键路径上的一位核心开发突然提出离职，距离上线只剩两周，你如何应对？",
                          "先诚恳挽留并了解原因 → 立即做知识交接文档 → 重新排期砍范围 → 向上同步风险。"),
                         ("你在给大客户做演示时，产品突然出现严重故障，演示无法继续，你怎么办？",
                          "坦诚说明并切换到备用方案（录屏/备份环境）→ 安排技术人员紧急排查 → 会后主动跟进修复进展。"),
                         ("社交媒体上出现大量关于你们产品的负面评价并快速发酵，作为负责人你的处理流程是什么？",
                          "先分级定性（产品问题/谣言）→ 统一口径官方回应 → 解决实际问题 → 复盘沉淀舆情 SOP。"),
                     ]),
                dict(cat="逻辑结构", desc="考察问题拆解、估算与结构化表达。", minutes=12,
                     questions=[
                         ("请估算你所在城市每天的外卖订单量，并说明你的估算过程。",
                          "供给/需求两条路径：人口×渗透率×人均单量，交叉验证骑手数量×单人日单量。"),
                         ("请用结构化方式分析「为什么某 App 的用户留存率下降」这个问题。",
                          "先分层定位（新客/老客、渠道、版本）→ 内部因素 vs 外部竞品 → 数据验证假设 → 给出归因优先级。"),
                         ("如何为一个新上线的功能制定一个 30 天的增长计划？请分阶段说明。",
                          "第 1 周cold start 验证 PMF → 第 2-3 周放大有效渠道 → 第 4 周留存优化与裂变，每阶段设北极星指标。"),
                         ("请对比分析「自建团队」与「外包开发」的优劣，并给出决策框架。",
                          "从成本、周期、核心程度、知识沉淀四个维度打分：核心业务自建，边缘需求外包。"),
                     ]),
                dict(cat="专业深度", desc="考察领域知识的深度、原理理解与技术决策能力。", minutes=12,
                     questions=[
                         ("请讲清楚你所在领域的一个核心技术的底层原理，以及它解决了什么问题。",
                          "选一个最熟的技术：背景问题 → 核心原理 → 与替代方案对比 → 实际落地效果。"),
                         ("你如何保持专业知识的更新？最近学习了什么新技术，它是如何应用到工作中的？",
                          "固定学习渠道 + 输出习惯 → 举一个新技术从学习到落地的完整例子。"),
                         ("请评价你用过的一个技术方案的优缺点，如果重做你会怎么改进？",
                          "客观说出局限（成本/扩展性/维护性）→ 给出改进后的架构与预期收益。"),
                         ("你简历上的核心项目，其最大的技术难点是什么？你是如何解决的？",
                          "难点要具体（并发/一致性/性能）→ 讲清候选方案对比 → 最终方案的量化效果。"),
                     ]),
                dict(cat="语言表达", desc="考察即兴表达、概念通俗化与 STAR 结构化叙事。", minutes=10,
                     questions=[
                         ("请用 1 分钟介绍一个复杂的技术或业务概念，让完全不懂的外行听明白。",
                          "用类比开场 → 一个生活化例子 → 一句话收尾点题。"),
                         ("请针对「公司要不要取消打卡制度」做一段 1 分钟的即兴陈述。",
                          "结论先行 → 两个论据（效率/公平）→ 风险与折中方案。"),
                         ("请把你的上一段工作经历用 STAR 法则完整讲一遍。",
                          "情境-任务-行动-结果四段式，结果要有量化数据。"),
                         ("假设你要向高管汇报一个失败的项目，请用 2 分钟把这件事讲得清晰且有说服力。",
                          "先说结论和损失 → 归因（不甩锅）→ 学到什么 → 下一步建议。"),
                     ]),
                dict(cat="岗位匹配", desc="考察求职动机、优势自证与职业规划。", minutes=10,
                     questions=[
                         ("你为什么选择我们公司和这个岗位？你的职业规划是什么？",
                          "岗位能力项与自身优势对应 + 公司业务方向的认同 + 3 年规划落在该赛道。"),
                         ("你认为自己最大的三个优势是什么？请分别用一个案例证明。",
                          "每个优势 = 一个标签 + 一个带数据的案例，避免空泛形容词。"),
                         ("你目前能力和岗位要求之间最大的差距是什么？打算如何补齐？",
                          "诚实但可控的差距 → 给出具体的学习/实践计划与时间点。"),
                         ("你为什么想离开上一份工作？你如何看待频繁跳槽？",
                          "归因于成长诉求而非人际矛盾 → 展示稳定性证据 → 强调对新岗位的长期投入意愿。"),
                     ]),
            ]
            for s in special_sets:
                qset = qm.QuestionSet(
                    name=f"{s['cat']}专项 · {len(s['questions'])} 题",
                    industry="专项练习",
                    position_type=s["cat"],
                    difficulty="medium",
                    description=s["desc"],
                    question_count=len(s["questions"]),
                    est_minutes=s["minutes"],
                    match_score=90.0,
                )
                db.add(qset)
                db.flush()
                for seq, (content, ref) in enumerate(s["questions"], 1):
                    db.add(qm.Question(
                        set_id=qset.id, seq=seq, form_type="structured", difficulty="medium",
                        category=s["cat"], dimension=s["cat"],
                        content=content, ref_answer=ref, time_limit_s=180,
                    ))
            print(f"[seed] created {len(special_sets)} special practice sets")

        # —— 无领导小组讨论专属题库（form_type="group"，开放辩题，正反方论点写入 ref_answer）——
        if not db.query(qm.QuestionSet).filter_by(form_type="group").first():
            group_sets = [
                dict(name="无领导讨论 · AI 与就业", desc="围绕 AI 与职场的热点辩题展开 6 人无领导讨论。",
                     topic_data=[
                         ("AI 大规模取代初级岗位，对行业发展利大于弊还是弊大于利？",
                          "利大于弊：淘汰重复劳动倒逼人才升级，人均产出与决策质量提升，历史每次技术革命最终都创造更多新岗位。",
                          "弊大于利：初级岗位是新人成长阶梯，被抽掉后人才断层；转型速度远慢于替代速度，社会成本被低估。"),
                         ("公司应该优先投入 AI 提效，还是优先保障员工就业稳定？",
                          "优先 AI 提效：效率是企业的生死线，先活下来才能谈责任，提效红利可再投入员工转型培训。",
                          "优先就业稳定：员工信任是企业最贵资产，裁员换 AI 短期省成本、长期丢执行力和组织知识。"),
                         ("应届生应该深耕一个专业领域，还是广泛拥抱 AI 工具成为多面手？",
                          "深耕专业：AI 工具门槛会越来越低，稀缺的始终是领域纵深，专业深度才是护城河。",
                          "拥抱工具：单一技能被 AI 平权化最快，善用工具的通才适配力强，未来属于人机协同型选手。"),
                         ("远程办公与坐班制，哪种模式更有利于团队创新？",
                          "远程办公：异步协作倒逼文档化和目标管理，人才池不受地域限制，深度工作不受打扰。",
                          "坐班制：创新的火花来自面对面的碰撞，新人的言传身教无法远程替代，沟通成本低一个量级。"),
                     ]),
                dict(name="无领导讨论 · 产品决策", desc="围绕产品与商业决策的经典两难题展开讨论。",
                     topic_data=[
                         ("一款新产品应该优先做用户增长，还是优先做留存？",
                          "优先增长：没有规模就没有反馈来源，留存可以在增长中迭代验证，先做大的盘子才有意义。",
                          "优先留存：漏水的桶装不满水，留存差说明 PMF 不成立，盲目增长只会烧钱买流失。"),
                         ("需求评审时，业务收益与技术债之间应该如何权衡？",
                          "业务优先：公司靠业务活下来，技术债记录在案定期偿还即可，错过市场窗口才是最大风险。",
                          "技术优先：技术债是复利贷款，拖得越久利息越高；系统不稳业务收益最终归零。"),
                         ("产品上线应该追求快速小步迭代，还是打磨完美再发布？",
                          "快速迭代：真实用户反馈胜过一切内部推演，MVP 快速试错，错了及时止损成本最低。",
                          "打磨发布：第一印象只有一次，口碑崩了再也扶不起；核心体验必须完整才配上线。"),
                         ("产品决策应该数据驱动，还是相信产品直觉？",
                          "数据驱动：直觉会骗人数据不会，A/B 测试让决策可证伪，规模化决策必须可复制。",
                          "产品直觉：数据只能解释过去，突破式创新来自对用户的共情；过度数据让人变成报表的奴隶。"),
                     ]),
            ]
            for gs in group_sets:
                qset = qm.QuestionSet(
                    name=gs["name"], industry="通用能力", position_type="群面讨论",
                    form_type="group", difficulty="medium",
                    description=gs["desc"],
                    question_count=len(gs["topic_data"]),
                    est_minutes=20, match_score=88.0,
                )
                db.add(qset)
                db.flush()
                for seq, (content, pro, con) in enumerate(gs["topic_data"], 1):
                    db.add(qm.Question(
                        set_id=qset.id, seq=seq, form_type="group", difficulty="medium",
                        category="无领导讨论", dimension="逻辑结构",
                        content=content, ref_answer=f"{pro}|||{con}", time_limit_s=600,
                    ))
            print(f"[seed] created {len(group_sets)} group discussion sets")

        # —— 半结构化面试专属题库（form_type="semi"，经历深挖 + 追问引导写入 ref_answer）——
        if not db.query(qm.QuestionSet).filter_by(form_type="semi").first():
            semi_sets = [
                dict(name="半结构化 · 项目经历深挖", desc="基于你的真实项目经历层层追问，验证能力真实性。",
                     qdata=[
                         ("介绍一个你最有成就感的项目：背景是什么？你扮演了什么角色？最终结果如何？",
                          "追问方向：这个项目里最难的技术决策是什么？为什么选它而不是替代方案？",
                          "STAR 法则展开：情境-任务-行动-结果，结果要有量化数据。"),
                         ("讲一次你和团队成员产生严重分歧的经历，你们最终是怎么达成一致的？",
                          "追问方向：如果对方始终坚持己见，你会升级给领导吗？升级的时机怎么判断？",
                          "分歧归因于目标差异而非情绪，展示倾听-求证-说服的过程。"),
                         ("说一个你搞砸了的事情。当时发生了什么？你做了什么补救？学到了什么？",
                          "追问方向：这个教训后来如何落到你的工作习惯里？举个最近的例子。",
                          "诚实承认错误 + 快速止损 + 制度化复盘，避免甩锅。"),
                         ("如果你的方案被直属领导否决，但你手上有充分证据证明它是对的，你会怎么做？",
                          "追问方向：如果二次沟通后领导依然否决，你还会坚持吗？边界在哪里？",
                          "先执行再求证或先对齐目标再呈现证据，展示向上沟通的分寸感。"),
                         ("未来 3 年你的职业规划是什么？这个岗位在你的规划里扮演什么角色？",
                          "追问方向：为了实现这个规划，你最近半年做了哪些具体投入？",
                          "规划与岗位能力项对应，避免假大空，给出可验证的里程碑。"),
                     ]),
                dict(name="半结构化 · 能力与动机验证", desc="围绕能力边界与求职动机的追问式深挖。",
                     qdata=[
                         ("你认为自己最突出的能力是什么？用一个具体案例证明它。",
                          "追问方向：这个能力在工作之外的场景里验证过吗？",
                          "能力标签 + 带数据的案例，避免空泛形容词。"),
                         ("你上一份工作为什么不做了？你是如何看待稳定和成长的？",
                          "追问方向：如果新岗位前三个月远低于预期，你会怎么办？",
                          "归因于成长诉求而非人际矛盾，展示稳定性证据。"),
                         ("说一个你主动学习新技能并落地的例子，你是怎么学的？效果如何量化？",
                          "追问方向：这个技能现在过时了吗？你的持续学习机制是什么？",
                          "学习渠道 + 输出习惯 + 落地效果，体现方法论。"),
                         ("你如何看待加班？什么情况下你会心甘情愿地加班？",
                          "追问方向：如果长期高强度加班影响了生活，你的底线和处理方式是什么？",
                          "以交付和结果为导向谈加班，同时展示边界意识。"),
                         ("如果给你一个完全陌生领域的任务，你如何在最短时间内上手？",
                          "追问方向：举个真实例子，你上次快速上手花了多久？卡点在哪？",
                          "学习路径：找标杆-拆框架-小步验证-请教专家，给出时间量化。"),
                     ]),
            ]
            for ss in semi_sets:
                qset = qm.QuestionSet(
                    name=ss["name"], industry="通用能力", position_type="半结构化",
                    form_type="semi", difficulty="medium",
                    description=ss["desc"],
                    question_count=len(ss["qdata"]),
                    est_minutes=25, match_score=89.0,
                )
                db.add(qset)
                db.flush()
                for seq, (content, followup, ref) in enumerate(ss["qdata"], 1):
                    db.add(qm.Question(
                        set_id=qset.id, seq=seq, form_type="semi", difficulty="medium",
                        category="经历深挖", dimension="岗位匹配",
                        content=content, ref_answer=f"{followup}|||{ref}", time_limit_s=240,
                    ))
            print(f"[seed] created {len(semi_sets)} semi-structured sets")

        # —— 无领导讨论 AI 虚拟候选人人设（通用 5 人，set_id=None）——
        if not db.query(qm.PeerPersona).first():
            personas = [
                dict(name="赵启明", style="激进派", color="#D8504F", aggressiveness=5,
                     bio="互联网大厂运营，语速快观点猛，坚信窗口期不等人",
                     openings=[
                         "我先把观点亮出来：{stance}。理由有三点，接下来逐一展开，欢迎各位直接来辩。",
                         "我的立场很明确——{stance}。与其面面俱到，不如把一个核心论点打透。",
                         "时间宝贵，我直接说结论：{stance}。谁反对，我们现在就可以过两招。",
                     ],
                     rebuttals=[
                         "我不同意{name}说的「{point}」——这太理想化了。现实里第一个倒下的就是这种方案，我的思路是集中资源先打透单点。",
                         "{name}的逻辑有个致命漏洞：只讲收益不讲代价。按这个做法，三个月内一定会反弹。",
                         "各位，我们不要在细枝末节上纠缠。真正的分歧是要不要冒进。我的答案是要，窗口期不等人。",
                         "「{point}」听起来很美，但执行成本被严重低估了。敢问{name}，资源从哪里来？",
                     ],
                     summaries=[
                         "总结一下我的立场：{stance}。时间会证明激进者是对的，我愿意为这个判断负责。",
                         "最后重申：机会属于敢下注的人。{stance}，谢谢大家。",
                     ]),
                dict(name="林晓雯", style="数据派", color="#3E63DD", aggressiveness=3,
                     bio="咨询顾问出身，开口必带数据，讲究可证伪",
                     openings=[
                         "大家好，我习惯用数据说话。关于这道题，我调研了几组数据，结论是：{stance}。",
                         "我先说结论：{stance}。后面我会用数据证明这个判断。",
                         "我的观点是{stance}，为了不空对空，我准备了三组数据支撑。",
                     ],
                     rebuttals=[
                         "我补一组数据：{name}提到「{point}」，但同类案例的成功率只有 30% 左右，我们不能只看幸存者。",
                         "我部分同意{name}，但「{point}」缺数据支撑。我建议先小样本验证，再决定要不要全面铺开。",
                         "从 ROI 角度看，「{point}」的投入产出比并不成立。我粗算过一笔账，成本至少是收益的两倍。",
                         "「{point}」这个判断我保留意见——样本量够吗？对照组有吗？没有数据支撑的结论站不住。",
                     ],
                     summaries=[
                         "我用一句话收尾：{stance}——数据不会说谎，建议大家回去再核一遍我给的数字。",
                         "今天的讨论很充分，我的结论依然是{stance}，欢迎线下用数据找我辩论。",
                     ]),
                dict(name="周明远", style="稳健派", color="#2FA36B", aggressiveness=2,
                     bio="金融行业风控经理，先问最坏情况再谈收益",
                     openings=[
                         "我的观点可能偏保守：{stance}。做决策前，我们更要关注风险和兜底。",
                         "关于这道题，我的看法是{stance}，但我更想先和大家讨论清楚：最坏情况是什么？",
                         "我先表态：{stance}。不过在论证之前，我想先请各位想想退路在哪里。",
                     ],
                     rebuttals=[
                         "我想提醒一下，{name}的「{point}」没有考虑最坏情况。如果极端情况发生，这套方案扛得住吗？",
                         "我理解{name}的乐观，但我的原则是先活下来再谈增长。「{point}」的风险我们根本没有预案。",
                         "各位有没有想过退路？如果「{point}」这条路走不通，我们的 Plan B 是什么？",
                         "「{point}」的隐含假设太强了。假设一破，整个论证就塌了，这个风险我们担不起。",
                     ],
                     summaries=[
                         "我的总结是：无论选哪条路，先准备好退路。{stance}，但请务必带上预案。",
                         "稳妥起见，我坚持{stance}。希望决策层能听到我们对风险的提醒。",
                     ]),
                dict(name="吴婉晴", style="整合派", color="#E8912D", aggressiveness=2,
                     bio="HR 背景管理培训生，擅长求同存异推动共识",
                     openings=[
                         "我认真听了前面几位同学的观点，其实大家的共识比分歧多。关于这道题，我的补充是：{stance}。",
                         "我的立场是{stance}，同时我也想帮大家找找观点之间的最大公约数。",
                         "我可能没那么极端：{stance}。我更关心我们怎么把分歧变成可执行的路线图。",
                     ],
                     rebuttals=[
                         "其实{name}的「{point}」和我的想法共同点比看起来多，我们可以把它整合成一条中间路线。",
                         "我建议把{name}的「{point}」加上时间维度：短期用它止血，长期再切换到更稳的方案。",
                         "大家观点都有道理，不如求同存异：把「{point}」作为选项之一，我们用统一的评估标准来打分。",
                         "我看{name}和{other}其实说的不是同一个层面的事——一个讲战略一个讲执行，我们可以分层达成共识。",
                     ],
                     summaries=[
                         "综合大家意见，我们的共识其实是：{stance}，同时吸收了稳健派的风险意识。我的总结就到这里。",
                         "今天很有收获，我们求同存异，把{stance}作为基础共识往下推。",
                     ]),
                dict(name="郑天宇", style="质疑派", color="#7C6BD6", aggressiveness=4,
                     bio="哲学系转产品，专挑论证漏洞，让人又爱又怕",
                     openings=[
                         "在大家表态之前，我先问一个不太合群的问题：这道题的前提本身成立吗？我的答案是：{stance}。",
                         "我持保留意见：{stance}。我专挑大家论证里的漏洞，请多包涵。",
                         "我的观点是{stance}——但在展开之前，我想先检验一下我们讨论的定义是否一致。",
                     ],
                     rebuttals=[
                         "等等，「{point}」这个结论本身就是幸存者偏差。失败的案例都不会被写进复盘里。",
                         "我泼个冷水：「{point}」成立的前提是我们有无限资源，但我们有吗？",
                         "刚才{name}偷换了概念——题目问的核心是定义之争，你说的却是程度之争。我们回到题目本身。",
                         "「{point}」是个典型的假两难。真正的答案往往在第三选项，我们为什么急着二选一？",
                     ],
                     summaries=[
                         "我的保留意见记录在案：{stance}。如果将来走不通，请记得我今天说过的话。",
                         "总结就一句：{stance}。别怪我泼冷水，冷水能让人清醒。",
                     ]),
            ]
            for p in personas:
                db.add(qm.PeerPersona(
                    name=p["name"], style=p["style"], color=p["color"], bio=p["bio"],
                    aggressiveness=p["aggressiveness"],
                    openings={"list": p["openings"]},
                    rebuttals={"list": p["rebuttals"]},
                    summaries={"list": p["summaries"]},
                    set_id=None,
                ))
            print(f"[seed] created {len(personas)} peer personas")

        db.commit()
        print("[seed] done")
    finally:
        db.close()


if __name__ == "__main__":
    sys.path.insert(0, ".")
    seed()
