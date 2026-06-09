from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ============= ENUMS =============
class SessionStatus(str, Enum):
    active = "active"
    completed = "completed"
    interrupted = "interrupted"


# ============= AUTH MODELS =============
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime


# ============= SUBJECT MODELS =============
class SubjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    exam_date: Optional[datetime] = None


class SubjectResponse(BaseModel):
    id: str
    name: str
    exam_date: Optional[datetime] = None
    created_at: datetime
    user_id: str


# ============= DOCUMENT MODELS =============
class DocumentUpload(BaseModel):
    subject_id: Optional[str] = None
    # File will come from multipart form data


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    subject_id: Optional[str] = None
    filename: str
    file_path: str
    source_type: str  # pdf, docx, md, txt
    file_size: int    # bytes
    uploaded_at: datetime
    page_count: Optional[int] = None  # For PDFs


# ============= SESSION MODELS =============
class SessionCreate(BaseModel):
    subject_id: str
    document_ids: List[str]
    topics: List[str] = []


class SessionStartResponse(BaseModel):
    session_id: str
    docs_loaded: int
    chunk_count: int


class SessionResponse(BaseModel):
    id: str
    user_id: str
    subject_id: str
    documents_used: List[str]
    topics: List[str] = []
    status: SessionStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    summary: Optional[str] = None
    transcript: List[dict] = []


class SessionEndResponse(BaseModel):
    session_id: str
    status: str
    started_at: datetime
    ended_at: datetime
    summary: Optional[str] = None


# ============= FLASHCARD MODELS =============
class FlashcardCreate(BaseModel):
    session_id: str
    subject_id: str
    question: str
    answer: str


class FlashcardResponse(BaseModel):
    id: str
    user_id: str
    session_id: str
    subject_id: str
    question: str
    answer: str
    card_type: str = "concept"
    topic: str = ""
    created_at: datetime

    # SM-2 Algorithm fields
    easiness_factor: float = 2.5
    interval: int = 0
    repetitions: int = 0
    next_review: datetime


# ============= DAY 5 — GOOGLE CALENDAR + PLANNING MODELS =============

class GoogleOAuthStatus(BaseModel):
    connected: bool
    google_email: Optional[str] = None
    connected_at: Optional[datetime] = None


class StudyPlanEvent(BaseModel):
    """A single proposed study session in a plan."""
    subject: str
    topic: str
    date: str                   # YYYY-MM-DD
    duration_minutes: int
    coverage_level: str         # well_covered | shallow | missing


class StudyPlanResponse(BaseModel):
    proposed_events: List[StudyPlanEvent]
    gap_analysis: dict
    total_sessions: int
    exam_date: str


class ConfirmPlanRequest(BaseModel):
    action: str = "confirm"     # "confirm" or "reject"


class ConfirmPlanResponse(BaseModel):
    status: str                 # "confirmed" | "rejected"
    events_created: int = 0
    calendar_links: List[str] = []
    message: str = ""
