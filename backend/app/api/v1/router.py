"""所有 v1 路由聚合"""
from fastapi import APIRouter
from app.api.v1 import (auth, dashboard, question_sets, sessions, reports, group,
                        resumes, admin, practice, content, observability, approval)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(question_sets.router)
api_router.include_router(sessions.router)
api_router.include_router(reports.router)
api_router.include_router(group.router)
api_router.include_router(resumes.router)
api_router.include_router(admin.router)
api_router.include_router(practice.router)
api_router.include_router(content.router)
api_router.include_router(observability.router)
api_router.include_router(approval.router)
