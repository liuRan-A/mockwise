"""群面 schemas"""
from typing import Optional
from pydantic import BaseModel


class GroupMemberOut(BaseModel):
    id: int
    role: str
    name: str
    initial: str
    color: str
    talk_count: int
    is_current_speaker: int

    class Config:
        orm_mode = True


class GroupTimelineOut(BaseModel):
    id: int
    member_id: int
    phase: str
    transcript: Optional[str] = None
    audio_url: Optional[str] = None
    started_at_ms: int
    duration_ms: int
    is_interrupted: int
    cited_count: int

    class Config:
        orm_mode = True


class GroupDiscussionOut(BaseModel):
    id: int
    session_id: int
    prompt: str
    material_json: Optional[dict] = None
    total_minutes: int
    statement_sec: int
    free_minutes: int
    summary_sec: int

    class Config:
        orm_mode = True


class GroupDiscussionDetail(GroupDiscussionOut):
    members: list[GroupMemberOut] = []
    timeline: list[GroupTimelineOut] = []


class RaiseHandIn(BaseModel):
    """群面举手发言"""
    member_id: int
    transcript: str = ""
    audio_url: str = ""
    duration_ms: int = 0
