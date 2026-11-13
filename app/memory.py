from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

import config


class MemoryNotConfigured(RuntimeError):
    pass


def _iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class MemoryStore:
    def __init__(self, region: str | None = None):
        self.region = region or config.AWS_REGION
        self._data_client = None
        self._control_client = None

    @property
    def data_client(self):
        if self._data_client is None:
            self._data_client = boto3.client(
                "bedrock-agentcore", region_name=self.region
            )
        return self._data_client

    @property
    def control_client(self):
        if self._control_client is None:
            self._control_client = boto3.client(
                "bedrock-agentcore-control", region_name=self.region
            )
        return self._control_client

    def memory_id(self) -> str:
        if not config.MEMORY_ID:
            raise MemoryNotConfigured(
                "MEMORY_ID is not set. Run `uv run scripts/create_memory.py` "
                "and set the result in config.py."
            )
        return config.MEMORY_ID

    def memory_status(self) -> tuple[str | None, str | None]:
        try:
            response = self.control_client.get_memory(memoryId=self.memory_id())
        except (MemoryNotConfigured, ClientError) as exc:
            return None, str(exc)
        memory = response.get("memory", {})
        return memory.get("status"), memory.get("failureReason")

    def list_sessions(self, actor_id: str) -> list[dict]:
        memory_id = self.memory_id()
        sessions: list[dict] = []
        next_token = None
        while True:
            kwargs = {
                "memoryId": memory_id,
                "actorId": actor_id,
                "maxResults": 50,
                "filter": {"eventFilter": "HAS_EVENTS"},
            }
            if next_token:
                kwargs["nextToken"] = next_token
            response = self.data_client.list_sessions(**kwargs)
            sessions.extend(response.get("sessionSummaries", []))
            next_token = response.get("nextToken")
            if not next_token or len(sessions) >= config.MAX_SESSIONS:
                break

        sessions.sort(key=lambda s: _iso(s.get("createdAt")) or "", reverse=True)
        return sessions[: config.MAX_SESSIONS]

    def get_history(self, actor_id: str, session_id: str) -> list[dict]:
        memory_id = self.memory_id()
        events: list[dict] = []
        next_token = None
        while True:
            kwargs = {
                "memoryId": memory_id,
                "actorId": actor_id,
                "sessionId": session_id,
                "includePayloads": True,
                "maxResults": 100,
            }
            if next_token:
                kwargs["nextToken"] = next_token
            response = self.data_client.list_events(**kwargs)
            events.extend(response.get("events", []))
            next_token = response.get("nextToken")
            if not next_token:
                break

        events.sort(key=lambda e: _iso(e.get("eventTimestamp")) or "")
        return [m for m in (self._to_message(event) for event in events) if m]

    def append_message(self, actor_id: str, session_id: str, role: str, text: str) -> dict:
        response = self.data_client.create_event(
            memoryId=self.memory_id(),
            actorId=actor_id,
            sessionId=session_id,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[
                {
                    "conversational": {
                        "content": {"text": text},
                        "role": role.upper(),
                    }
                }
            ],
        )
        return response.get("event", {})

    @staticmethod
    def _to_message(event: dict) -> dict | None:
        texts = []
        role = "USER"
        for payload in event.get("payload", []):
            conversational = payload.get("conversational")
            if not conversational:
                continue
            role = conversational.get("role", role)
            text = (conversational.get("content") or {}).get("text")
            if text:
                texts.append(text)
        if not texts:
            return None
        return {
            "role": role.lower(),
            "text": "\n".join(texts),
            "timestamp": _iso(event.get("eventTimestamp")),
            "event_id": event.get("eventId"),
        }


store = MemoryStore()
