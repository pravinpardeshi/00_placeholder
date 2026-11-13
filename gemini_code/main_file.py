import os
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError
from fastapi.middleware.cors import CORSMiddleware

# Import AgentCore Session Management SDK
from bedrock_agentcore.memory import MemorySessionManager
REGION_NAME = os.getenv("AWS_REGION", "us-east-1")
MEMORY_ID = os.getenv("AGENTCORE_MEMORY_ID", "your-memory-id-here")

app = FastAPI(title="Bedrock AgentCore Memory Backend", version="1.0.0")

# Configuration (In production, load memory_id from environment variables or database)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your exact frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize the Memory Session Manager
try:
    session_manager = MemorySessionManager(
        memory_id=MEMORY_ID,
        region_name=REGION_NAME
    )
except Exception as e:
    print(f"Warning: Failed to initialize MemorySessionManager: {e}")
    session_manager = None

class ChatRequest(BaseModel):
    actor_id: str = Field(...,  min_length=36, max_length=64, description="Unique non-PII identifier for the user")
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Conversation thread ID")
    message: str = Field(..., description="The user input message")

class ChatResponse(BaseModel):
    actor_id: str
    session_id: str
    response_message: str
    memory_id: str

@app.post("/chat", response_model=ChatResponse)
def handle_chat_turn(payload: ChatRequest):
    if not session_manager:
        raise HTTPException(status_code=500, detail="AgentCore Session Manager is not initialized.")

    try:
        # Bind or retrieve the session context for this specific user (actor) and chat window (session)
        session = session_manager.create_memory_session(
            actor_id=payload.actor_id,
            session_id=payload.session_id
        )

        # In a complete architecture, you would pass the session/memory context
        # to your LLM (e.g., Anthropic Claude via Bedrock Runtime) to generate a reply.
        # Here we simulate the LLM response incorporating conversational tracking:
        simulated_llm_reply = f"Echo response: I received your message: '{payload.message}'."

        # Log the conversational turn into AgentCore memory data plane
        # (Alternatively, use session helper utilities provided by your orchestration framework)
        data_client = boto3.client("bedrock-agentcore", region_name=REGION_NAME)
        data_client.create_event(
            memoryId=MEMORY_ID,
            actorId=payload.actor_id,
            sessionId=payload.session_id,
            eventTimestamp=datetime.utcnow(),
            payload=[
                {
                    "conversational": {
                        "content": {"text": payload.message},
                        "role": "USER"
                    }
                },
                {
                    "conversational": {
                        "content": {"text": simulated_llm_reply},
                        "role": "ASSISTANT"
                    }
                }
            ]
        )

        return ChatResponse(
            actor_id=payload.actor_id,
            session_id=payload.session_id,
            response_message=simulated_llm_reply,
            memory_id=MEMORY_ID
        )

    except ClientError as e:
        raise HTTPException(status_code=400, detail=e.response["Error"]["Message"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "healthy", "memory_id": MEMORY_ID}

@app.get("/chat/history")
def get_chat_history(
    actor_id: str = Query(..., description="The unique actor ID"),
    session_id: str = Query(..., description="The specific session ID to fetch history for"),
    max_results: int = Query(20, ge=1, le=100, description="Max messages to return")
):
    """
    Retrieves historic conversation events for a specific actor and session from AWS Bedrock AgentCore.
    """
    try:
        response = data_client.list_events(
            memoryId=MEMORY_ID,
            actorId=actor_id,
            sessionId=session_id,
            includePayloads=True,
            maxResults=max_results
        )

        # Format events nicely for front-end consumption
        formatted_history = []
        for event in response.get("events", "[]"):
            for p in event.get("payload", []):
                if "conversational" in p:
                    conv = p["conversational"]
                    formatted_history.append({
                        "event_id": event.get("eventId"),
                        "timestamp": event.get("eventTimestamp"),
                        "role": conv.get("content", {}).get("role") or conv.get("role"),
                        "text": conv.get("content", {}).get("text")
                    })

        return {
            "actor_id": actor_id,
            "session_id": session_id,
            "history": formatted_history,
            "next_token": response.get("nextToken")
        }

    except ClientError as e:
        raise HTTPException(status_code=400, detail=e.response["Error"]["Message"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

