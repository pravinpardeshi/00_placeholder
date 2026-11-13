from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from app.chat import ChatError, generate_reply
from app.memory import MemoryNotConfigured, store
from app.models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    Message,
    NewSessionResponse,
    SessionSummary,
)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="AgentCore Chat", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _aws_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MemoryNotConfigured):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, (ClientError, BotoCoreError, ChatError)):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    status, error = store.memory_status()
    return HealthResponse(
        ready=status == "ACTIVE",
        memory_id=config.MEMORY_ID,
        memory_status=status,
        region=config.AWS_REGION,
        model_id=config.MODEL_ID,
        detail=error,
    )


@app.get("/api/sessions", response_model=list[SessionSummary])
def list_sessions(
    actor_id: str = Query(default=config.DEFAULT_ACTOR_ID, min_length=1),
) -> list[SessionSummary]:
    try:
        sessions = store.list_sessions(actor_id)
    except Exception as exc:
        raise _aws_error(exc) from exc
    return [
        SessionSummary(
            session_id=session["sessionId"],
            created_at=(
                session["createdAt"].isoformat()
                if session.get("createdAt")
                else None
            ),
        )
        for session in sessions
    ]


@app.post("/api/sessions", response_model=NewSessionResponse)
def new_session() -> NewSessionResponse:
    return NewSessionResponse(session_id=uuid4().hex)


@app.get(
    "/api/sessions/{session_id}/messages", response_model=list[Message]
)
def get_messages(
    session_id: str,
    actor_id: str = Query(default=config.DEFAULT_ACTOR_ID, min_length=1),
) -> list[Message]:
    try:
        history = store.get_history(actor_id, session_id)
    except Exception as exc:
        raise _aws_error(exc) from exc
    return [Message(**message) for message in history]


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    actor_id = request.actor_id or config.DEFAULT_ACTOR_ID
    session_id = request.session_id.strip()
    user_text = request.message.strip()
    if not user_text:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    try:
        store.append_message(actor_id, session_id, "USER", user_text)
        history = store.get_history(actor_id, session_id)
        reply = generate_reply(history)
        store.append_message(actor_id, session_id, "ASSISTANT", reply)
    except Exception as exc:
        raise _aws_error(exc) from exc

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
