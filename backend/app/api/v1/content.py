# -*- coding: utf-8 -*-
"""内容配置后台路由：套题 / 题目 / 群面虚拟候选人人设 的增删改查（仅管理员）"""
from fastapi import APIRouter, Depends, HTTPException, status, Query

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import (require_permission, record_audit, PERM_MANAGE_CONTENT,
                           PERM_APPROVE, ROLE_PERMS)
from app.core.logging_config import get_logger
from app.services import approval as appr
from app.models.user import User
from app.models.question import QuestionSet, Question, PeerPersona
from app.crud import question as q_crud
from app.crud import peer as p_crud
from app.schemas.common import R
from app.schemas.content import (
    SetCreate, SetUpdate, QuestionCreate, QuestionUpdate, PersonaCreate, PersonaUpdate,
)

router = APIRouter(prefix="/admin/content", tags=["content-admin"])
log = get_logger("content.admin")


def _ensure_can_bypass(admin: User) -> None:
    """force=1 直执行属于「自己放行自己的变更」，要求具备审批权，否则通道会被滥用。"""
    if PERM_APPROVE not in ROLE_PERMS.get(admin.role, set()):
        from app.core.errors import ForbiddenError
        raise ForbiddenError("无审批权限，不能跳过人工复核")


def _gate(db, admin: User, *, target_type: str, target_id, action: str,
          summary: str, payload: dict | None = None, force: int = 0) -> dict | None:
    """高危操作人工卡点。

    返回 None → 无需审批，调用方继续即时执行；
    返回 dict → 已冻结为待审单，调用方原样返回给前端（业务数据未发生任何变化）。
    """
    if not appr.requires_approval(action):
        return None
    if force:
        _ensure_can_bypass(admin)
        return None
    ap = appr.submit(db, target_type=target_type, target_id=target_id, action=action,
                     payload=payload, summary=summary, submitter_id=admin.id)
    return {"need_approval": True, "approval_id": ap.id, "status": ap.status,
            "risk": ap.risk, "summary": summary}


def _set_out(s: QuestionSet) -> dict:
    return {
        "id": s.id, "name": s.name, "industry": s.industry, "position_type": s.position_type,
        "form_type": s.form_type, "difficulty": s.difficulty, "description": s.description,
        "cover_url": s.cover_url, "question_count": s.question_count, "est_minutes": s.est_minutes,
        "match_score": float(s.match_score or 0), "is_published": s.is_published,
        "created_at": s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else "",
    }


def _q_out(q: Question) -> dict:
    return {
        "id": q.id, "set_id": q.set_id, "seq": q.seq, "form_type": q.form_type,
        "difficulty": q.difficulty, "category": q.category, "dimension": q.dimension,
        "content": q.content, "ref_answer": q.ref_answer, "time_limit_s": q.time_limit_s,
    }


def _persona_out(p: PeerPersona) -> dict:
    def as_list(d):
        if not d:
            return []
        # 兼容 {"list":[...]} 或 直接 list
        if isinstance(d, dict):
            return (d.get("list") or []) + (d.get("on_user") or []) + (d.get("on_peer") or [])
        return d
    return {
        "id": p.id, "name": p.name, "style": p.style, "color": p.color, "bio": p.bio,
        "aggressiveness": p.aggressiveness, "set_id": p.set_id,
        "openings": as_list(p.openings),
        "rebuttals": as_list(p.rebuttals),
        "summaries": as_list(p.summaries),
    }


# ============ 套题 ============
@router.get("/sets", response_model=R, summary="后台套题列表（含下架）")
def list_sets(admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    rows = q_crud.list_all_sets(db)
    return R.ok([_set_out(s) for s in rows])


@router.get("/sets/{set_id}", response_model=R, summary="套题详情（含题目）")
def get_set(set_id: int, admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    s = db.get(QuestionSet, set_id)
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "套题不存在")
    out = _set_out(s)
    out["questions"] = [_q_out(q) for q in q_crud.list_questions(db, set_id)]
    return R.ok(out)


@router.post("/sets", response_model=R, summary="新建套题")
def create_set(payload: SetCreate, admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    s = q_crud.create_set(db, payload.dict())
    record_audit(db, admin.id, "create", "question_set", s.id, f"name={s.name}")
    return R.ok(_set_out(s))


@router.put("/sets/{set_id}", response_model=R, summary="更新套题")
def update_set(set_id: int, payload: SetUpdate, admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    s = q_crud.update_set(db, set_id, payload.dict(exclude_unset=True))
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "套题不存在")
    record_audit(db, admin.id, "update", "question_set", set_id)
    return R.ok(_set_out(s))


@router.post("/sets/{set_id}/publish", response_model=R, summary="上架/下架切换（高危，默认进审批）")
def toggle_publish(set_id: int, published: int,
                   force: int = Query(0, description="1=持审批权者直接执行，跳过人工卡点"),
                   admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    if not db.get(QuestionSet, set_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "套题不存在")
    action = "publish" if published else "unpublish"
    gated = _gate(db, admin, target_type="question_set", target_id=set_id, action=action,
                  payload={"published": int(published)},
                  summary=f"{'上架' if published else '下架'}套题 #{set_id}", force=force)
    if gated:
        return R.ok(gated, msg="已提交人工复核，等待批准后生效")
    s = q_crud.set_publish(db, set_id, published)
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "套题不存在")
    record_audit(db, admin.id, action, "question_set", set_id,
                 f"is_published={published}{'（force 直执行）' if force else ''}")
    return R.ok({"id": s.id, "is_published": s.is_published})


@router.delete("/sets/{set_id}", response_model=R, summary="删除套题（含题目，高危，默认进审批）")
def delete_set(set_id: int,
               force: int = Query(0, description="1=持审批权者直接执行，跳过人工卡点"),
               admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    s = db.get(QuestionSet, set_id)
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "套题不存在")
    gated = _gate(db, admin, target_type="question_set", target_id=set_id, action="delete",
                  summary=f"删除套题「{s.name}」及其全部题目（不可逆）", force=force)
    if gated:
        return R.ok(gated, msg="已提交人工复核，等待批准后生效")
    ok = q_crud.delete_set(db, set_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "套题不存在")
    record_audit(db, admin.id, "delete", "question_set", set_id, "force 直执行" if force else None)
    return R.ok({"deleted": set_id})


# ============ 题目 ============
@router.get("/sets/{set_id}/questions", response_model=R, summary="题目列表")
def list_questions(set_id: int, admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    if not db.get(QuestionSet, set_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "套题不存在")
    return R.ok([_q_out(q) for q in q_crud.list_questions(db, set_id)])


@router.post("/sets/{set_id}/questions", response_model=R, summary="新增题目")
def create_question(set_id: int, payload: QuestionCreate, admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    if not db.get(QuestionSet, set_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "套题不存在")
    q = q_crud.create_question(db, set_id, payload.dict())
    return R.ok(_q_out(q))


@router.put("/questions/{qid}", response_model=R, summary="更新题目")
def update_question(qid: int, payload: QuestionUpdate, admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    q = q_crud.update_question(db, qid, payload.dict(exclude_unset=True))
    if not q:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    return R.ok(_q_out(q))


@router.delete("/questions/{qid}", response_model=R, summary="删除题目（自动重排，高危，默认进审批）")
def delete_question(qid: int,
                    force: int = Query(0, description="1=持审批权者直接执行，跳过人工卡点"),
                    admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    q = db.get(Question, qid)
    if not q:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    gated = _gate(db, admin, target_type="question", target_id=qid, action="delete",
                  summary=f"删除套题 #{q.set_id} 的题目 #{qid}：{(q.content or '')[:30]}", force=force)
    if gated:
        return R.ok(gated, msg="已提交人工复核，等待批准后生效")
    ok = q_crud.delete_question(db, qid)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    record_audit(db, admin.id, "delete", "question", qid, "force 直执行" if force else None)
    return R.ok({"deleted": qid})


# ============ 群面虚拟候选人人设 ============
@router.get("/personas", response_model=R, summary="人设列表")
def list_personas(admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    return R.ok([_persona_out(p) for p in p_crud.list_personas(db)])


@router.post("/personas", response_model=R, summary="新建人设")
def create_persona(payload: PersonaCreate, admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    data = payload.dict()
    data["openings"] = {"list": data.pop("openings") or []}
    data["rebuttals"] = {"list": data.pop("rebuttals") or []}
    data["summaries"] = {"list": data.pop("summaries") or []}
    p = p_crud.create_persona(db, data)
    record_audit(db, admin.id, "create", "persona", p.id, f"name={p.name}")
    return R.ok(_persona_out(p))


@router.put("/personas/{pid}", response_model=R, summary="更新人设")
def update_persona(pid: int, payload: PersonaUpdate, admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    data = payload.dict(exclude_unset=True)
    # 模板类字段：若传入则重新打包为 {"list": [...]}
    for key in ("openings", "rebuttals", "summaries"):
        if key in data and data[key] is not None:
            data[key] = {"list": data[key]}
    p = p_crud.update_persona(db, pid, data)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "人设不存在")
    return R.ok(_persona_out(p))


@router.delete("/personas/{pid}", response_model=R, summary="删除人设（高危，默认进审批）")
def delete_persona(pid: int,
                   force: int = Query(0, description="1=持审批权者直接执行，跳过人工卡点"),
                   admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)), db: Session = Depends(get_db)):
    p = db.get(PeerPersona, pid)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "人设不存在")
    gated = _gate(db, admin, target_type="persona", target_id=pid, action="delete",
                  summary=f"删除群面虚拟人设「{p.name}」", force=force)
    if gated:
        return R.ok(gated, msg="已提交人工复核，等待批准后生效")
    ok = p_crud.delete_persona(db, pid)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "人设不存在")
    record_audit(db, admin.id, "delete", "persona", pid, "force 直执行" if force else None)
    return R.ok({"deleted": pid})
