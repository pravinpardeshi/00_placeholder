import boto3
from botocore.exceptions import BotoCoreError, ClientError

import config


class ChatError(RuntimeError):
    pass


_client = None


def client(region: str | None = None):
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime", region_name=region or config.AWS_REGION
        )
    return _client


def _build_messages(history: list[dict]) -> list[dict]:
    recent = history[-config.MAX_HISTORY_MESSAGES :]
    merged: list[dict] = []
    for item in recent:
        role = item.get("role")
        text = (item.get("text") or "").strip()
        if role not in ("user", "assistant") or not text:
            continue
        if merged and merged[-1]["role"] == role:
            merged[-1]["content"].append({"text": text})
        else:
            merged.append({"role": role, "content": [{"text": text}]})

    while merged and merged[0]["role"] != "user":
        merged.pop(0)
    return merged


def generate_reply(history: list[dict]) -> str:
    messages = _build_messages(history)
    if not messages:
        raise ChatError("No conversation history available to send to the model.")

    try:
        response = client().converse(
            modelId=config.MODEL_ID,
            messages=messages,
            system=[{"text": config.SYSTEM_PROMPT}],
            inferenceConfig={
                "maxTokens": config.MAX_TOKENS,
                "temperature": config.TEMPERATURE,
            },
        )
    except (ClientError, BotoCoreError) as exc:
        raise ChatError(str(exc)) from exc

    blocks = response.get("output", {}).get("message", {}).get("content", [])
    reply = "".join(block.get("text", "") for block in blocks).strip()
    if not reply:
        raise ChatError("The model returned an empty response.")
    return reply
