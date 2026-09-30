"""无领导小组讨论：AI 虚拟候选人人设与发言生成"""
import random

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.question import PeerPersona


# ===== 后台：人设 CRUD =====
def list_personas(db: Session):
    return db.query(PeerPersona).order_by(PeerPersona.set_id.is_(None).desc(), PeerPersona.id).all()


def create_persona(db: Session, data: dict) -> PeerPersona:
    p = PeerPersona(**data)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def update_persona(db: Session, pid: int, data: dict) -> PeerPersona | None:
    p = db.get(PeerPersona, pid)
    if not p:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


def delete_persona(db: Session, pid: int) -> bool:
    p = db.get(PeerPersona, pid)
    if not p:
        return False
    db.delete(p)
    db.commit()
    return True


def list_personas_for_session(db: Session, set_id: int | None, limit: int = 5):
    """优先取该套题专属人设，不足则用通用人设补齐"""
    dedicated = db.query(PeerPersona).filter(PeerPersona.set_id == set_id).all() if set_id else []
    generic = db.query(PeerPersona).filter(PeerPersona.set_id.is_(None)).all()
    merged = dedicated + generic
    # 按 aggressiveness 降序再随机打散同级，保证每场氛围略有不同
    merged.sort(key=lambda p: (-p.aggressiveness, random.random()))
    return merged[:limit]


def _pick(pool: list[str], fallback: str) -> str:
    return random.choice(pool) if pool else fallback


def _extract_point(user_text: str, max_len: int = 40) -> str:
    """从用户发言中摘一个有信息量的短句作为被反驳的观点"""
    if not user_text:
        return ""
    sents = [s.strip() for s in user_text.replace("\n", "。").split("。") if len(s.strip()) >= 8]
    if not sents:
        return user_text.strip()[:max_len]
    # 优先挑带观点标志词的句子；截断时尽量落在完整词边界
    marked = [s for s in sents if any(kw in s for kw in ["我认为", "我觉得", "应该", "首先", "关键是", "核心", "我支持", "我反对", "总结", "共识"])]
    pick = (marked or sents)[0]
    if len(pick) > max_len:
        cut = pick[:max_len]
        for sep in ("，", ",", "；", " "):
            pos = cut.rfind(sep)
            if pos >= max_len - 8:
                cut = cut[:pos]
                break
        pick = cut
    return pick


def generate_peer_talk(
    stage: str,
    persona: PeerPersona,
    stance: str,
    topic: str,
    target_name: str,
    user_text: str,
    other_name: str = "",
    recent_context: list[dict] | None = None,
    respond_to: str = "me",
) -> str:
    """按阶段 + 人设模板生成一条候选人发言。

    增强点：
    1) 候选人发言后（user_text 非空），优先使用「回应候选人」的模板，
       模板中 {point} 会被替换为候选人原话片段，保证回应紧扣其发言内容；
    2) 接受 recent_context：候选人能引用最近一两条「场上其他发言」（不一定是 user），
       让候选人之间能互相呼应，避免「各说各话」；
    3) respond_to 决定这次主要是回应 user 还是另一位候选人，模板选择会更准。
    """
    point = _extract_point(user_text)

    # 从 recent_context 抽一条最近发言作为「场上的最新观点」（被引用的素材）
    ctx_peer_text = ""
    if recent_context:
        # 倒序找最近的 peer（非 user）发言
        for m in reversed(recent_context):
            if m.get("who") == "peer" and m.get("text"):
                ctx_peer_text = m.get("text", "")
                break

    respond_to_other_peer = respond_to and respond_to not in ("me", "你", "", "user")

    if point and stage in ("opening", "summary"):
        bucket = persona.openings if stage == "opening" else persona.summaries
        src = list((bucket or {}).get("on_user", [])) or list((persona.rebuttals or {}).get("list", []))
    elif point and respond_to_other_peer and (persona.rebuttals or {}).get("on_peer"):
        # 回应另一位候选人：用「on_peer」模板，让对话有真正来回感
        src = list((persona.rebuttals or {}).get("on_peer", [])) or list((persona.rebuttals or {}).get("list", []))
    elif point:
        # 一般回应候选人：on_user / list 模板
        bucket = persona.openings if stage == "opening" else persona.summaries
        src = list((persona.rebuttals or {}).get("list", [])) or list((bucket or {}).get("list", []))
    elif stage == "opening":
        src = (persona.openings or {}).get("list", [])
    elif stage == "summary":
        src = (persona.summaries or {}).get("list", [])
    else:
        src = (persona.rebuttals or {}).get("list", [])

    # 退路：没有任何模板时给一个稳健的兜底
    fallback = "关于这一点，我的看法是：{stance}。"
    tpl = _pick(src, fallback)

    # 决定「被引用人」是谁：如果是回应另一位候选人，用对方姓名；否则用 user_text
    if respond_to_other_peer:
        name = respond_to
        # 优先抽对方最近发言中的观点作为被引用的 {point}
        ref_point = _extract_point(ctx_peer_text) if ctx_peer_text else (point or "刚才的论点")
    else:
        name = target_name or "刚才这位候选人"
        ref_point = point or "刚才的论点"

    text = tpl.format(
        topic=(topic or "这道辩题")[:40],
        stance=stance or "我支持我认为更合理的一方",
        name=name,
        other=other_name or "另一位同学",
        point=ref_point,
    )
    return text
