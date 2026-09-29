# -*- coding: utf-8 -*-
"""简历路由：上传 / 粘贴文本 → 解析 → DeepSeek 画像 → 用于面试个性化出题"""
import os
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.position import Resume
from app.schemas.common import R
from app.services.resume_parser import parse_resume
from app.services.llm import analyze_resume, rule_analyze_resume

router = APIRouter(prefix="/resumes", tags=["resume"])

UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "uploads", "resumes",
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {".pdf", ".docx", ".doc", ".txt", ".md"}


def _analyze_and_save(db: Session, user: User, raw_text: str, filename: str,
                      file_type: str, file_url: str) -> Resume:
    """解析文本 → AI 画像 → 落库"""
    # 同用户旧简历取消激活
    db.query(Resume).filter(Resume.user_id == user.id).update({Resume.is_active: 0})

    resume = Resume(
        user_id=user.id,
        raw_text=raw_text or "（未解析到文本）",
        file_url=file_url,
        filename=filename,
        file_type=file_type,
        is_active=1,
        status="parsed" if raw_text else "failed",
    )
    db.add(resume)
    db.flush()

    profile = None
    if raw_text and len(raw_text.strip()) >= 20:
        try:
            profile = analyze_resume(raw_text)
        except Exception:
            profile = None
        if not profile:
            profile = rule_analyze_resume(raw_text)
        resume.parsed_json = profile
        resume.status = "analyzed"
    else:
        resume.parsed_json = rule_analyze_resume(raw_text or "")
        resume.status = "failed" if not raw_text else "parsed"

    db.commit()
    db.refresh(resume)
    return resume


@router.post("/upload", response_model=R, summary="上传简历文件（PDF/Word/TXT）并 AI 分析")
async def upload_resume(
    file: UploadFile = File(None),
    text: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw_text = ""
    filename = ""
    file_type = "txt"
    file_url = ""

    if file is not None and file.filename:
        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"不支持的文件格式 {ext}，请上传 PDF/Word/TXT")
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件不能超过 10MB")
        # 保存文件
        safe_name = f"{user.id}_{uuid.uuid4().hex[:8]}{ext}"
        fpath = os.path.join(UPLOAD_DIR, safe_name)
        with open(fpath, "wb") as f:
            f.write(content)
        file_url = f"/uploads/resumes/{safe_name}"
        file_type, raw_text = parse_resume(filename, content)
        if not raw_text:
            # 文件解析失败（如旧版 .doc / 扫描 PDF），退回用粘贴文本
            if not text.strip():
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "未能从文件中解析出文本（旧版 .doc 或扫描件不支持），请改用「粘贴简历文本」或上传 .docx/.txt",
                )
            raw_text = text.strip()
            file_type = "txt"
    elif text.strip():
        raw_text = text.strip()
        filename = "粘贴文本.txt"
        file_type = "txt"
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请上传文件或粘贴简历文本")

    resume = _analyze_and_save(db, user, raw_text[:20000], filename, file_type, file_url)
    return R.ok(_resume_out(resume))


@router.get("", response_model=R, summary="我的简历列表")
def list_resumes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Resume).filter(Resume.user_id == user.id).order_by(
        Resume.created_at.desc()).all()
    return R.ok([_resume_out(r) for r in rows])


@router.get("/active", response_model=R, summary="当前使用的简历画像")
def active_resume(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.query(Resume).filter(
        Resume.user_id == user.id, Resume.is_active == 1
    ).order_by(Resume.created_at.desc()).first()
    return R.ok(_resume_out(r) if r else None)


@router.post("/{resume_id}/activate", response_model=R, summary="设为当前简历")
def activate_resume(resume_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Resume, resume_id)
    if not r or r.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "简历不存在")
    db.query(Resume).filter(Resume.user_id == user.id).update({Resume.is_active: 0})
    r.is_active = 1
    db.commit()
    return R.ok(_resume_out(r))


@router.delete("/{resume_id}", response_model=R, summary="删除简历")
def delete_resume(resume_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Resume, resume_id)
    if not r or r.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "简历不存在")
    db.delete(r)
    db.commit()
    return R.ok({"deleted": resume_id})


def _resume_out(r: Resume | None) -> dict | None:
    if not r:
        return None
    p = r.parsed_json or {}
    return {
        "id": r.id,
        "filename": r.filename,
        "file_url": r.file_url,
        "file_type": r.file_type,
        "status": r.status,
        "is_active": r.is_active,
        "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        "engine": p.get("engine", "rule"),
        "profile": {
            "candidate_name": p.get("candidate_name", ""),
            "target_position": p.get("target_position", ""),
            "years_exp": p.get("years_exp", ""),
            "summary": p.get("summary", ""),
            "skills": p.get("skills", []),
            "projects": p.get("projects", []),
            "highlights": p.get("highlights", []),
            "weaknesses": p.get("weaknesses", []),
            "suggested_questions": p.get("suggested_questions", []),
        },
    }
