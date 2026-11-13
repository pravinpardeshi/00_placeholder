from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=8000)
    actor_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    timestamp: str


class NewSessionResponse(BaseModel):
    session_id: str


class SessionSummary(BaseModel):
    session_id: str
    created_at: str | None = None


class Message(BaseModel):
    role: str
    text: str
    timestamp: str | None = None
    event_id: str | None = None


class HealthResponse(BaseModel):
    ready: bool
    memory_id: str
    memory_status: str | None = None
    region: str
    model_id: str
    detail: str | None = None
