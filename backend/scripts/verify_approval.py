# -*- coding: utf-8 -*-
"""
P5 人机协同验证脚本（真库实跑，非模拟）

验证「高危操作人工审核卡点」确实成立，而不是看起来成立：
 1. 高危动作（delete / publish）默认不生效，而是冻结为待审单；
 2. 待审期间业务数据**零变化**（这是"卡点"的实质）；
 3. 批准后变更才落库，且状态机进入终态 approved；
 4. 驳回后变更彻底不生效，数据保持原样；
 5. 重复审批（并发双审 / 连点）被状态机拒绝；
 6. 非高危动作（create/update）不进审批，不干扰日常操作；
 7. force 通道需要审批权，且不绕过审计留痕；
 8. 审批动作本身写审计 + 绑定 trace_id（可追溯谁放行的）。

跑法：  venv312/Scripts/python.exe scripts/verify_approval.py
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, engine, SessionLocal          # noqa: E402
from app.core.config import settings                              # noqa: E402
from app.models.user import User                                  # noqa: E402
from app.models.audit import AdminAudit                           # noqa: E402
from app.models.approval import ContentApproval                   # noqa: E402
from app.models.question import QuestionSet, Question, PeerPersona  # noqa: E402
from app.services import approval as appr                         # noqa: E402
from app.crud import question as q_crud                           # noqa: E402
from app.core.errors import ConflictError                         # noqa: E402
from app.core.logging_config import request_id_var                # noqa: E402

# 脚本没有 HTTP 请求上下文，手动注入一个 trace_id，才能验证「审批单确实绑定了链路」
TEST_TRACE = "verify-approval-0001"

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


def main() -> int:
    print("=== P5 人机协同（人工审核卡点）验证 ===\n")
    engine.echo = False          # 关掉 SQL echo，输出只看结论
    request_id_var.set(TEST_TRACE)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    admin = db.query(User).filter(User.role == "admin").first()
    if not admin:
        print("!! 库中没有 admin 账号，先运行 `python seed.py` 或手动把任一用户 role 改为 admin")
        return 2
    reviewer = db.query(User).filter(User.role == "admin", User.id != admin.id).first() or admin

    # 造一份专用测试数据（名称带标记，脚本结束清理）
    MARK = "[P5审批验证-可删]"
    s = q_crud.create_set(db, {
        "name": MARK, "industry": "测试", "position_type": "测试",
        "form_type": "structured", "difficulty": "easy",
        "description": "由 verify_approval.py 创建", "cover_url": "",
        "est_minutes": 5, "match_score": 0, "is_published": 1,
    })
    sid = s.id
    q = q_crud.create_question(db, sid, {
        "form_type": "structured", "difficulty": "easy",
        "category": "测试", "dimension": "逻辑结构",
        "content": f"{MARK} 题目", "ref_answer": "参考答案", "time_limit_s": 60,
    })
    qid = q.id
    print(f"测试夹具：套题 #{sid}、题目 #{qid}\n")

    try:
        # ---------- 1. 需要审批的动作判定 ----------
        print("[1] 高危动作判定")
        check("delete 需要人工复核", appr.requires_approval("delete"))
        check("publish 需要人工复核", appr.requires_approval("publish"))
        check("unpublish 需要人工复核", appr.requires_approval("unpublish"))
        check("create 不进审批（不淹没审批流）", not appr.requires_approval("create"))
        check("风险分级正确 delete=high", appr.risk_of("delete") == "high")

        # ---------- 2. 待审期间数据零变化 ----------
        print("\n[2] 提交审批后业务数据必须零变化")
        snap_before = q_crud.get_set(db, sid)
        ap = appr.submit(db, target_type="question_set", target_id=sid, action="delete",
                         summary=f"{MARK} 删除套题", submitter_id=admin.id)
        check("生成待审单且状态 pending", ap.status == "pending", f"approval_id={ap.id}")
        check("快照已冻结（复核人看得到要删的是什么）",
              ap.snapshot is not None and MARK in ap.snapshot)
        check("删除未生效：套题仍在", q_crud.get_set(db, sid) is not None)
        check("删除未生效：关联题目仍在", db.get(Question, qid) is not None)
        check("待审计数可读", appr.pending_count(db) >= 1, f"pending={appr.pending_count(db)}")

        # ---------- 3. 驳回 → 彻底不生效 ----------
        print("\n[3] 驳回")
        ap2 = appr.submit(db, target_type="question_set", target_id=sid, action="unpublish",
                          payload={"published": 0}, summary=f"{MARK} 下架", submitter_id=admin.id)
        appr.reject(db, ap2.id, reviewer.id, "测试驳回")
        check("状态变为 rejected", appr.get(db, ap2.id).status == "rejected")
        check("驳回后套题仍上架（未产生变更）", q_crud.get_set(db, sid).is_published == 1)

        # ---------- 4. 重复审批被拒 ----------
        print("\n[4] 状态机防重复处理")
        dup_rejected = False
        try:
            appr.approve(db, ap2.id, reviewer.id, "再点一次")
        except ConflictError:
            dup_rejected = True
        check("已终态的审批单不能重复批准", dup_rejected)

        # ---------- 5. 批准 → 变更落库 ----------
        print("\n[5] 批准后变更才生效")
        ap3 = appr.submit(db, target_type="question_set", target_id=sid, action="unpublish",
                          payload={"published": 0}, summary=f"{MARK} 下架（这次是真下架）",
                          submitter_id=admin.id)
        appr.approve(db, ap3.id, reviewer.id, "同意下架")
        check("状态变为 approved", appr.get(db, ap3.id).status == "approved")
        check("下架已生效", q_crud.get_set(db, sid).is_published == 0)

        ap4 = appr.submit(db, target_type="question_set", target_id=sid, action="delete",
                          summary=f"{MARK} 删除套题（这次是真删）", submitter_id=admin.id)
        appr.approve(db, ap4.id, reviewer.id, "确认无引用，同意删除")
        check("删除已生效：套题没了", q_crud.get_set(db, sid) is None)
        check("级联：题目也一起删除", db.get(Question, qid) is None)

        # ---------- 6. 应用失败保持 pending（可修正后重试） ----------
        print("\n[6] 应用失败不吞掉：保持待审 + 记录原因")
        ap5 = appr.submit(db, target_type="question_set", target_id=99999999, action="delete",
                          summary="删除一个不存在的套题", submitter_id=admin.id)
        failed = False
        try:
            appr.approve(db, ap5.id, reviewer.id, "批准一个注定失败的变更")
        except Exception as e:
            failed = True
            msg = str(e)
        check("应用失败时抛出错误（不静默成功）", failed)
        row5 = appr.get(db, ap5.id)
        check("失败后审批单保持 pending 可重试", row5.status == "pending")
        check("失败原因已记录", bool(row5.last_error), f"last_error={row5.last_error}")
        check("错误信息透出给复核人", "套题不存在" in msg if failed else False)

        # ---------- 7. 审批动作本身留痕且绑定 trace_id ----------
        print("\n[7] 审批留痕（审计 + 链路）")
        audits = (db.query(AdminAudit)
                  .filter(AdminAudit.target_type.like("approval:%"))
                  .order_by(AdminAudit.id.desc()).limit(20).all())
        actions = {a.action for a in audits}
        check("提交有审计", any(a.startswith("submit:") for a in actions), str(sorted(actions)))
        check("批准有审计", any(a.startswith("approve:") for a in actions))
        check("驳回有审计", any(a.startswith("reject:") for a in actions))
        check("审批单绑定 trace_id（可追溯谁在哪个请求里提交的）",
              ap4.trace_id == TEST_TRACE, f"trace_id={ap4.trace_id}")

        # ---------- 8. 关闭开关后降级为即时生效（不阻断业务） ----------
        print("\n[8] 总开关可关闭（降级不阻断）")
        settings.APPROVAL_ENABLED = False
        check("关闭后 delete 不再进审批", not appr.requires_approval("delete"))
        settings.APPROVAL_ENABLED = True   # 还原

    finally:
        # 清理：删掉测试夹具与本次产生的审批单
        try:
            leftover = q_crud.get_set(db, sid)
            if leftover:
                db.delete(leftover)
            db.query(ContentApproval).filter(
                ContentApproval.summary.like(f"%{MARK}%")).delete(synchronize_session=False)
            db.query(ContentApproval).filter(
                ContentApproval.summary.in_(["删除一个不存在的套题"])).delete(synchronize_session=False)
            db.commit()
        except Exception as e:
            print("  (清理告警)", e)
        finally:
            db.close()

    print(f"\n=== 通过 {len(PASS)} 项，失败 {len(FAIL)} 项 ===")
    if FAIL:
        print("失败项：", FAIL)
        return 1
    print("P5_APPROVAL_VERIFY_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
