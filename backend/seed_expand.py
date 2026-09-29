# -*- coding: utf-8 -*-
"""扩充真实题库数据（幂等）：
1) 新增 3 套群面辩题（每套 4 题，正反方参考论点）
2) 新增 2 套半结构化经历深挖题（每套 5 题，含追问方向+参考要点，覆盖 5 个维度）
3) 新增 2 套结构化行业题（互联网运营 8 题、数据分析 8 题，含参考标准答案）
4) positions 表补 5 个真实目标岗位
5) 5 个群面 AI 人设补充 on_user 回应模板（引用候选人原话 {point}）
所有数据写入真实数据表，可直接 SQL 查询验证。
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from app.core.database import SessionLocal
from app.models import user as _um  # noqa: F401  # 确保 users 表注册（Position 外键依赖）
from app.models.question import QuestionSet, Question, PeerPersona
from app.models.position import Position

db = SessionLocal()
added = {"sets": 0, "questions": 0, "positions": 0, "personas": 0}


def get_or_create_set(name, **kw):
    qs = db.query(QuestionSet).filter_by(name=name).first()
    if qs:
        return qs, False
    qs = QuestionSet(name=name, **kw)
    db.add(qs)
    db.flush()
    added["sets"] += 1
    return qs, True


def add_questions(qset, rows):
    """rows: [(seq, form_type, difficulty, category, dimension, content, ref_answer, time_limit_s)]"""
    existing = db.query(Question).filter_by(set_id=qset.id).count()
    if existing:
        return 0
    for seq, ft, df, cat, dim, content, ref, tl in rows:
        db.add(Question(set_id=qset.id, seq=seq, form_type=ft, difficulty=df,
                        category=cat, dimension=dim, content=content,
                        ref_answer=ref, time_limit_s=tl))
        added["questions"] += 1
    qset.question_count = len(rows)
    return len(rows)


# ============ 1) 群面辩题 3 套 × 4 题 ============
GROUP_SETS = [
    dict(name="无领导讨论 · 组织管理", desc="围绕团队管理与组织机制的两难辩题，考察领导力与协作意识。",
         topics=[
             ("末位淘汰制是否能真正提升团队战斗力？",
              "能提升：强制分布打破大锅饭，高绩效者获得资源倾斜，组织保持饥饿感，通用电气等公司验证过其有效性。",
              "不能：末位淘汰摧毁心理安全感，员工拒绝协作和冒险，短期数据导向牺牲长期创新，实际淘汰的往往是不擅表现的人。"),
             ("部门负责人应该从内部提拔，还是外部空降？",
              "内部提拔：熟悉业务与团队，文化认同度高，给员工成长预期；空降兵水土不服的概率远高于内部晋升。",
              "外部空降：带来外部视角和资源，打破近亲繁殖和路径依赖，变革期需要没有历史包袱的人推动重组。"),
             ("两个部门争夺同一笔预算，公司应该怎么分？",
              "按战略权重分配：预算跟随公司级战略，谁的项目对齐 OKR 优先级高谁拿，用统一评估标准避免会哭的孩子有奶吃。",
              "按ROI对赌分配：两边都给启动资源，设 3 个月里程碑，用数据说话再追加，把静态争夺变成动态赛马。"),
             ("绩效考核应该更看重结果，还是更看重过程？",
              "看重结果：商业世界以成败论英雄，结果可量化、可比较，过度强调过程会让表演式工作盛行。",
              "看重过程：结果有运气成分，过程指标（协作、创新尝试、人才培养）决定长期结果，只考结果会催生短视和数据造假。"),
         ]),
    dict(name="无领导讨论 · 商业与社会热点", desc="围绕当下商业与社会热点辩题，考察商业敏感度与思辨能力。",
         topics=[
             ("新能源汽车的价格战，对行业长期发展是好事还是坏事？",
              "好事：价格战加速优胜劣汰，消费者得实惠，供应链被迫降本增效，最终像家电行业一样沉淀出全球竞争力。",
              "坏事：全行业亏损透支研发投入，安全和质量被成本妥协，劣币驱逐良币，行业没有利润就没有未来。"),
             ("AI 生成内容是否应该享有著作权？",
              "应该享有：投入了提示工程、数据整理和审校劳动，完全不保护会扼杀 AI 创作生态，应保护人的编排与选择部分。",
              "不应该：独创性是著作权的前提，AI 生成物的核心贡献不属于自然人，保护会造成版权确权混乱和垄断。"),
             ("直播带货对实体商业是冲击大于带动，还是带动大于冲击？",
              "带动大于冲击：直播重构了流通效率，工厂直连消费者，区域特产和白牌工厂获得新渠道，整体商业盘子在扩大。",
              "冲击大于带动：流量垄断挤压线下就业和地方税收，最低价机制压榨供应商利润，商业多样性被少数主播扼杀。"),
             ("年轻人选择「躺平」是个人选择自由，还是需要干预的社会问题？",
              "个人自由：躺平是对过度内卷和高生活成本的理性回应，多元成功观本身就是社会进步，不应被道德绑架。",
              "社会问题：大面积躺平意味着人力资本闲置和消费萎缩，背后是上升通道堵塞，需要制度层面降低奋斗成本。"),
         ]),
    dict(name="无领导讨论 · 危机决策", desc="模拟企业突发危机场景的紧急决策讨论，考察应变与优先级判断。",
         topics=[
             ("用户数据疑似泄露，公司应该第一时间公开通告，还是先内部排查确认？",
              "先公开：诚信和合规是底线，延迟通告一旦被曝光就是二次灾难，参考 GDPR 精神，告知用户才能止损和自保。",
              "先排查：未确认即公告会引发不必要的恐慌和股价波动，72 小时黄金窗口内边查边备预案，确认后精准通报更负责任。"),
             ("核心技术骨干提出离职并疑似跳槽竞品，公司应该强留还是放人？",
              "强留：核心技术带走即失控，加薪+股权+项目主导权多管齐下，同时启动竞业和权限收敛，争取交接窗口。",
              "放人：心不在了强留无用，立即做知识沉淀和权限切割，把资源投向团队梯队建设，用机制而非个人依赖兜底。"),
             ("年度预算被突然砍半，团队应该砍项目数量保品质，还是全部项目缩水平推？",
              "砍项目：集中资源打透最重要的 1-2 件事，半成品项目全是负债，砍掉的项目明说预期，反而赢得信任。",
              "缩水平推：每个项目都是对业务方的承诺，全砍会失去战略卡位，全员降本 50% 共渡时艰，保留翻盘的期权。"),
             ("线上重大故障发生后，应该先追责还是先复盘流程？",
              "先追责：重大事故必须有人负责，没有代价的复盘会变成走过场，明确问责才能建立敬畏心。",
              "先复盘： blame-free 文化才能听到真相，先定位根因修复系统，责任在流程改进后按制度认定，追责吓出来的只会是隐瞒。"),
         ]),
]
for gs in GROUP_SETS:
    qset, created = get_or_create_set(
        gs["name"], industry="通用能力", position_type="群面讨论",
        form_type="group", difficulty="medium", description=gs["desc"],
        question_count=len(gs["topics"]), est_minutes=20, match_score=87.0,
        is_published=1)
    if created:
        rows = []
        for seq, (content, pro, con) in enumerate(gs["topics"], 1):
            rows.append((seq, "group", "medium", "无领导讨论", "逻辑结构",
                         content, f"{pro}|||{con}", 600))
        add_questions(qset, rows)
        print(f"[expand] 群面套题：{gs['name']}（{len(rows)} 题）")


# ============ 2) 半结构化 2 套 × 5 题（覆盖 5 维度）============
SEMI_SETS = [
    dict(name="半结构化 · 管理潜力深挖", desc="面向带团队/项目负责人的潜力验证，围绕管理场景层层追问。",
         qdata=[
             ("讲一次你带领团队达成一个困难目标的经历：团队多大？目标难在哪里？你做对了什么？",
              "追问方向：如果团队里有一个老员工资历比你深且不配合，你怎么处理？",
              "STAR 展开：目标量化、分工逻辑、激励手段、复盘机制，结果要有数据。",
              "专业深度"),
             ("你如何给团队成员分配任务？请用一次真实排兵布阵说明你的原则。",
              "追问方向：当任务量超过团队承载力时，你砍需求还是要人？依据是什么？",
              "体现因人施用 + 能力发展 + 兜底意识，而非简单平均分配。",
              "逻辑结构"),
             ("项目上线前夜发现一个关键成员情绪崩溃想退出，你怎么处理？",
              "追问方向：如果他负责的模块无人可替代，你的 Plan B 是什么？",
              "先处理情绪再处理事情，评估风险、调配备份、必要时向上申请延期。",
              "应急应变"),
             ("请用 1 分钟向大老板汇报一个失败的项目，争取他继续支持你。",
              "追问方向：如果老板当场说「以后这种项目别再做了」，你怎么接？",
              "结论先行、不甩锅、给出教训和止损方案，展示担当与表达力。",
              "语言表达"),
             ("你为什么认为自己适合走管理路线，而不是继续做资深个人贡献者？",
              "追问方向：管理工作占用了你深耕技术的时间，这个机会成本你怎么看？",
              "用真实带人成果说话，说明管理意愿来自成就感而非头衔，与岗位路径匹配。",
              "岗位匹配"),
         ]),
    dict(name="半结构化 · 职场情景应对", desc="高压职场情景题，考察应变、边界感与职业化程度。",
         qdata=[
             ("你发现同事的方案有明显漏洞，但明天就要向客户汇报，你会怎么做？",
              "追问方向：如果他认为你在抢功而拒绝修改，你还会坚持吗？",
              "私下沟通 + 对事不对人 + 给台阶，以客户利益为最高优先级。",
              "人际关系" if False else "应急应变"),
             ("领导安排你一项职责范围外的紧急任务，而你手头工作已经饱和，你怎么回应？",
              "追问方向：如果领导说「年轻人多担当一点」，你如何第二次表达边界？",
              "不直接拒绝，先对齐优先级，请领导帮你排序，体现协作与边界。",
              "岗位匹配"),
             ("跨部门会议上，别的部门当众把责任推给你，你如何当场回应？",
              "追问方向：会后你发现确实有自己团队的疏漏，你会补充承认吗？",
              "当场用事实和数据冷静澄清，不情绪化，会后再补位闭环。",
              "语言表达"),
             ("你同时推进三个项目，其中两个的负责人都认为自己的项目最重要，你如何排序？",
              "追问方向：排序后被排在最后的项目负责人投诉到你领导那里，你怎么办？",
              "用统一标准（战略对齐度/截止时间/依赖关系）排序，过程透明可解释。",
              "逻辑结构"),
             ("讲一次你在信息严重不足时必须快速决策的经历，事后看决策对吗？",
              "追问方向：如果当时的决策事后被证明错了，你会在哪一步停下来？",
              "说明决策框架（可逆性/止损线/最小验证），接受不确定性并复盘。",
              "专业深度"),
         ]),
]
for ss in SEMI_SETS:
    qset, created = get_or_create_set(
        ss["name"], industry="通用能力", position_type="半结构化",
        form_type="semi", difficulty="medium", description=ss["desc"],
        question_count=len(ss["qdata"]), est_minutes=25, match_score=89.0,
        is_published=1)
    if created:
        rows = []
        for seq, (content, followup, ref, dim) in enumerate(ss["qdata"], 1):
            rows.append((seq, "semi", "medium", "经历深挖", dim,
                         content, f"{followup}|||{ref}", 240))
        add_questions(qset, rows)
        print(f"[expand] 半结构化套题：{ss['name']}（{len(rows)} 题）")


# ============ 3) 结构化行业题 2 套 × 8 题 ============
STRUCTURED_SETS = [
    dict(name="互联网运营实战 · 8 题", industry="互联网", position_type="运营",
         difficulty="medium", est_minutes=26, match_score=90.0,
         desc="覆盖活动运营、用户增长、内容运营、数据复盘等运营核心能力，按大厂面试标准设计。",
         qdata=[
             ("你负责的社区产品 DAU 连续一周下跌 15%，请说说你的排查和应对思路。",
              "先拆维度定位：渠道/版本/人群/内容哪一层在跌；外因看竞品活动和节假日，内因看近期改版与服务稳定性；止血用召回推送+活动，根因用内容供给和留存机制修复。", "逻辑结构", "情景题"),
             ("请设计一个新用户 7 日留存提升方案，核心抓手是什么？",
              "新手期 Aha moment 前置：首日核心动作引导、3 日内容/任务钩子、7 日身份沉淀；每一步设转化漏斗目标，用 A/B 实验验证，关注次留→7 留的衰减节点。", "专业深度", "专业题"),
             ("预算 10 万做一场拉新活动，你会如何分配渠道预算并设定考核指标？",
              "按历史 CAC 和渠道质量分配，预留 20% 测试预算跑小样本；考核以获客成本、次留、单用户 LTV 为主，不只看注册量，活动后做渠道归因复盘。", "专业深度", "专业题"),
             ("活动上线后 2 小时参与人数只有预期的 20%，你怎么办？",
              "先查链路（入口曝光→点击→参与转化哪一步断了），再查规则复杂度和奖励吸引力；能热修复的立即修，同时推 push/资源位加码，实时盯数据做二次调整。", "应急应变", "情景题"),
             ("产品经理想砍掉一个你运营了一年、数据稳定但增长见顶的频道，你同意吗？",
              "先对齐砍频道的战略意图，用留存贡献和用户迁移成本评估；若资源确实要投向新方向，配合做用户迁移路径和内容归档，而非情绪化守成。", "岗位匹配", "情景题"),
             ("请用 1 分钟向我推荐一款你最近觉得运营做得好的产品，并说明好在哪里。",
              "结论先行点出产品，从获客钩子、转化路径、留存机制、传播设计四个层面各给一个具体证据，体现日常拆解习惯。", "语言表达", "情景题"),
             ("你如何判断一次刷屏级传播活动是真成功还是虚假繁荣？",
              "看北极星指标而非虚荣指标：曝光之后的搜索指数、新用户质量（次留/付费）、品牌负评率、渠道自然流量占比；补贴刷出来的量在活动结束后 7 天会打回原形。", "专业深度", "专业题"),
             ("内容社区里出现大量同质化低质内容，优质创作者开始流失，你怎么治理？",
              "分层治理：流量端用推荐权重打压低质、扶持原创；激励端给优质创作者确定性回报（流量/收益/身份）；机制上端内建立举报和快速申诉通道，先止血头部流失。", "应急应变", "情景题"),
         ]),
    dict(name="数据分析专项 · 8 题", industry="互联网", position_type="数据",
         difficulty="hard", est_minutes=28, match_score=88.0,
         desc="考察指标体系、AB 实验、归因分析与商业洞察，面向数据分析师岗位。",
         qdata=[
             ("如果让你为一款电商 App 搭建核心指标体系，你会怎么设计？",
              "按 AARRR 分层：获客（CAC/渠道质量）、激活（首单转化）、留存（复购率/购买频次）、收入（GMV/客单价/毛利）、传播（NPS/分享率），每层配北极星和过程指标。", "专业深度", "专业题"),
             ("转化率下降了 20%，业务方催你下午给结论，你如何在半天内完成分析？",
              "先按维度下钻（渠道/端/版本/人群/商品类目）定位异常切片，再区分是流量结构变化还是链路转化问题，查埋点和技术故障，给出带置信度的初步结论和后续验证计划。", "应急应变", "情景题"),
             ("A/B 实验显示新策略转化率提升 1%，但 p 值 0.08，业务方想全量，你怎么建议？",
              "p=0.08 不显著，先看效应量和样本量是否充足、实验周期是否覆盖周期波动；扩大流量再跑一周，同时检查护栏指标（退款率/客诉），不能拿不显著结果直接全量。", "专业深度", "专业题"),
             ("老板问「这个月 GMV 为什么没达标」，你怎么把分析讲清楚？",
              "GMV=流量×转化率×客单价，先拆公式定位缺口在哪一环，再对每一环做内外因归因（渠道、活动、竞品、季节），最后给可执行动作而非只报数字。", "逻辑结构", "情景题"),
             ("如何识别数据报表里的「虚假增长」？举一个你遇到过的例子。",
              "看增长质量：新用户留存是否同步恶化、是否靠补贴/渠道灌水、指标口径是否被改动；用同期群分析和 LTV/CAC 交叉验证，警惕拆东墙补西墙的透支式增长。", "专业深度", "专业题"),
             ("业务方不懂 SQL 但每天要数，你如何平衡取数效率和数据团队精力？",
              "建指标字典统一口径 + 高频需求做成自助看板，临时需求排期并沉淀成模板，同时做数据素养培训，把重复取数变成产品化能力。", "岗位匹配", "情景题"),
             ("两个渠道的新用户数量相同，如何判断哪个渠道更值得加投？",
              "不能只看量：对比次留、7 留、首单、90 天 LTV/CAC，分人群看质量差异，结合渠道扩容空间和边际成本，用 LTV/CAC>3 作为加投阈值。", "专业深度", "专业题"),
             ("请用 30 秒讲一个你用数据洞察改变业务决策的案例。",
              "结论先行：背景一句话、数据发现一句话（带数字）、决策动作一句话、业务结果一句话（带数字），体现分析师的业务影响力而非只会取数。", "语言表达", "情景题"),
         ]),
]
for st in STRUCTURED_SETS:
    qdata = st.pop("qdata")
    qset, created = get_or_create_set(
        st["name"], industry=st["industry"], position_type=st["position_type"],
        form_type="structured", difficulty=st["difficulty"], description=st["desc"],
        question_count=len(qdata), est_minutes=st["est_minutes"],
        match_score=st["match_score"], is_published=1)
    if created:
        rows = []
        for seq, (content, ref, dim, cat) in enumerate(qdata, 1):
            rows.append((seq, "structured", st["difficulty"], cat, dim, content, ref, 180))
        add_questions(qset, rows)
        print(f"[expand] 结构化套题：{st['name']}（{len(rows)} 题）")


# ============ 4) positions 真实岗位（挂在主账号 user_id=1 下）============
POSITIONS = [
    ("AI 方案架构师", "高级/P7", "AI / SaaS", "头部 AI 独角兽"),
    ("高级产品经理", "高级/P7", "互联网", "一线互联网大厂"),
    ("算法工程师（NLP 方向）", "中级/P6", "AI / SaaS", "上市科技公司"),
    ("数据分析师", "中级/P6", "互联网", "头部电商平台"),
    ("用户运营经理", "中级/P6", "互联网", "高增长内容社区"),
]
uid = 1
for name, level, industry, company in POSITIONS:
    exists = db.query(Position).filter_by(user_id=uid, name=name).first()
    if not exists:
        db.add(Position(user_id=uid, name=name, level=level,
                        industry=industry, target_company=company, is_active=1))
        added["positions"] += 1
print(f"[expand] positions 新增 {added['positions']} 条")


# ============ 5) 人设 on_user 回应模板（引用候选人原话）============
ON_USER_OPENING = {
    "激进派": [
        "{name}说「{point}」，立场我听到了，但这个观点太保守。窗口期不等人，我认为必须 All in 一侧。",
        "{name}的「{point}」我部分同意，但力度不够。讨论要出结论，我建议直接按最激进的方案定调。",
    ],
    "数据派": [
        "{name}提到「{point}」，这个判断有数据支撑吗？我查过类似案例，结论可能正好相反。",
        "我补充一下，{name}的「{point}」方向没错，但缺量化依据，我们应该先定评估指标再下结论。",
    ],
    "稳健派": [
        "{name}的「{point}」有道理，但我想提醒风险：最坏情况发生时，这个方案扛得住吗？",
        "我理解{name}的思路，不过「{point}」之前，我们是不是先把兜底方案讨论清楚？",
    ],
    "整合派": [
        "{name}说的「{point}」和我的想法其实有交集，我们可以把它和前面同学的观点整合成一条折中路线。",
        "我帮大家归一下：{name}的「{point}」解决的是短期问题，再配上长期机制就完整了。",
    ],
    "质疑派": [
        "等等，{name}说「{point}」——这个前提本身成立吗？我们是不是先把定义对齐再讨论？",
        "我追问一句：「{point}」有没有反例？如果只挑有利证据，这个结论是站不住的。",
    ],
}
ON_USER_SUMMARY = {
    "激进派": [
        "最后我坚持我的判断：{name}总结的「{point}」太温和，机会属于敢下注的人，谢谢。",
    ],
    "数据派": [
        "我的收尾：{name}提到的「{point}」方向可以，但请大家回去用数据复核一遍，数据不会说谎。",
    ],
    "稳健派": [
        "我补充一句风险提示：无论选哪条路，{name}说的「{point}」之外，预案和退路必须带上。",
    ],
    "整合派": [
        "我来收个尾：{name}的「{point}」加上大家前面的共识，求同存异后其实已经是一份可执行路线图了。",
    ],
    "质疑派": [
        "我的保留意见记录在案：「{point}」的论证链条还有缺口，未来如果走不通，请记得今天的提醒。",
    ],
}
for p in db.query(PeerPersona).all():
    changed = False
    openings = dict(p.openings or {})
    if not openings.get("on_user") and ON_USER_OPENING.get(p.style):
        openings["on_user"] = ON_USER_OPENING[p.style]
        p.openings = openings
        changed = True
    summaries = dict(p.summaries or {})
    if not summaries.get("on_user") and ON_USER_SUMMARY.get(p.style):
        summaries["on_user"] = ON_USER_SUMMARY[p.style]
        p.summaries = summaries
        changed = True
    if changed:
        added["personas"] += 1
        print(f"[expand] 人设 {p.name}<{p.style}> 补充 on_user 回应模板")

db.commit()
print(f"\n完成：新增套题 {added['sets']} 套、题目 {added['questions']} 道、岗位 {added['positions']} 个、人设模板 {added['personas']} 个")

# 复核
print("\n=== 复核：questions 表分布 ===")
from sqlalchemy import text
for r in db.execute(text(
    "SELECT form_type, COUNT(*) FROM questions GROUP BY form_type")).fetchall():
    print(f"  {r[0]}: {r[1]} 题")
for r in db.execute(text("SELECT COUNT(*) FROM positions")).fetchall():
    print(f"  positions: {r[0]} 条")
db.close()
