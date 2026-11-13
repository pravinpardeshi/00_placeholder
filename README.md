# AgentCore Chat

A ChatGPT-style chatbot with a FastAPI backend that stores and retrieves chat
sessions using **Amazon Bedrock AgentCore Memory**, and generates replies with
the **Bedrock Converse API**.

## Architecture

```
Browser (vanilla HTML/JS)
   │  /api/chat, /api/sessions
   ▼
FastAPI (app/main.py)
   ├── app/chat.py    → bedrock-runtime.converse
   └── app/memory.py  → bedrock-agentcore (events, sessions)
                        bedrock-agentcore-control (memory resource)
```

AgentCore Memory stores each message as an immutable event under:

```
memoryId → actorId → sessionId → event (USER / ASSISTANT)
```

## Setup

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Make sure AWS credentials are available (environment, profile, or SSO) and
   that the region in `config.py` has AgentCore Memory available.

3. Create the memory resource (one time, takes 2–3 minutes):

   ```bash
   uv run scripts/create_memory.py
   ```

   Copy the printed `MEMORY_ID` into `config.py`.

4. Run the app:

   ```bash
   uv run uvicorn app.main:app --reload
   ```

   Open http://127.0.0.1:8000. API docs at http://127.0.0.1:8000/docs.

## Configuration (`config.py`)

| Setting | Purpose |
| --- | --- |
| `AWS_REGION` | Region for AgentCore and Bedrock |
| `MEMORY_ID` | AgentCore Memory resource ID (from the setup script) |
| `MEMORY_NAME` | Name used when creating the memory |
| `EVENT_EXPIRY_DAYS` | Short-term event retention (1–365 days) |
| `MODEL_ID` | Bedrock model or inference profile used by Converse |
| `MAX_TOKENS` | Maximum output tokens per reply |
| `SYSTEM_PROMPT` | System instruction for the model |
| `DEFAULT_ACTOR_ID` | Actor ID used when the client does not send one |
| `MAX_HISTORY_MESSAGES` | Recent messages sent to the model |

## API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Memory status + active configuration |
| `GET` | `/api/sessions?actor_id=` | List past sessions with events |
| `POST` | `/api/sessions` | Generate a new session ID |
| `GET` | `/api/sessions/{session_id}/messages?actor_id=` | Load a conversation |
| `POST` | `/api/chat` | Save user message → call Bedrock → save reply |

## IAM permissions

The principal running the backend needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:CreateEvent",
        "bedrock-agentcore:ListEvents",
        "bedrock-agentcore:ListSessions",
        "bedrock-agentcore:GetEvent"
      ],
      "Resource": "arn:aws:bedrock-agentcore:<region>:<account>:memory/<memory-id>"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore-control:CreateMemory",
        "bedrock-agentcore-control:GetMemory",
        "bedrock-agentcore-control:ListMemories"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    }
  ]
}
```

Scope the Bedrock and control-plane resources further for production use.

## Notes

- `actorId` isolates users. The demo UI uses `demo-user`; in production derive it
  from your auth layer (e.g., Cognito `sub`) and send it with each request.
- Empty sessions are automatically deleted by AgentCore after one day.
- `eventExpiryDuration` applies at write time; changing it does not extend
  already-stored events.
- A failed model call still leaves the user event stored, so retrying the same
  message will show it twice in the conversation history.
