"""AWS and application configuration.

Run `uv run scripts/create_memory.py` once to provision the AgentCore
Memory resource, then paste the returned ID into MEMORY_ID.
"""

AWS_REGION = "us-east-1"

MEMORY_NAME = "ChatbotSessions"
MEMORY_ID = ""  # e.g. "mem-0123456789abcdef0"
MEMORY_DESCRIPTION = "Short-term chat session storage for the FastAPI chatbot"
EVENT_EXPIRY_DAYS = 30

MODEL_ID = "us.anthropic.claude-sonnet-4-6"
MAX_TOKENS = 1024
TEMPERATURE = 0.7
SYSTEM_PROMPT = "You are a helpful, concise assistant."

DEFAULT_ACTOR_ID = "demo-user"
MAX_HISTORY_MESSAGES = 20
MAX_SESSIONS = 50
