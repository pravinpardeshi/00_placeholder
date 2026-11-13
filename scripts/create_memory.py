import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boto3
from botocore.exceptions import ClientError

import config


def find_by_name(client, name):
    paginator_token = None
    while True:
        kwargs = {"maxResults": 50}
        if paginator_token:
            kwargs["nextToken"] = paginator_token
        response = client.list_memories(**kwargs)
        for memory in response.get("memories", []):
            if memory.get("name") == name:
                return memory
        paginator_token = response.get("nextToken")
        if not paginator_token:
            return None


def wait_for_active(client, memory_id, timeout_seconds=900):
    deadline = time.time() + timeout_seconds
    last_status = None
    while time.time() < deadline:
        memory = client.get_memory(memoryId=memory_id)["memory"]
        status = memory.get("status")
        if status != last_status:
            print(f"  status: {status}")
            last_status = status
        if status == "ACTIVE":
            return memory
        if status == "FAILED":
            raise SystemExit(
                f"Memory creation failed: {memory.get('failureReason', 'unknown reason')}"
            )
        time.sleep(10)
    raise SystemExit("Timed out waiting for the memory to become ACTIVE.")


def main():
    client = boto3.client(
        "bedrock-agentcore-control", region_name=config.AWS_REGION
    )

    if config.MEMORY_ID:
        print(f"config.MEMORY_ID is already set: {config.MEMORY_ID}")
        memory = client.get_memory(memoryId=config.MEMORY_ID)["memory"]
        print(f"  name:   {memory.get('name')}")
        print(f"  status: {memory.get('status')}")
        print(f"  arn:    {memory.get('arn')}")
        return

    existing = find_by_name(client, config.MEMORY_NAME)
    if existing:
        memory_id = existing["id"]
        print(f"Found existing memory '{config.MEMORY_NAME}': {memory_id}")
    else:
        print(
            f"Creating memory '{config.MEMORY_NAME}' in {config.AWS_REGION} "
            f"(events expire after {config.EVENT_EXPIRY_DAYS} days)..."
        )
        try:
            response = client.create_memory(
                name=config.MEMORY_NAME,
                description=config.MEMORY_DESCRIPTION,
                eventExpiryDuration=config.EVENT_EXPIRY_DAYS,
            )
        except ClientError as exc:
            raise SystemExit(f"create_memory failed: {exc}") from exc
        memory = response["memory"]
        memory_id = memory["id"]
        print(f"  memory id:  {memory_id}")
        print(f"  memory arn: {memory.get('arn')}")

    wait_for_active(client, memory_id)

    print("\nMemory is ACTIVE. Set this in config.py:\n")
    print(f'    MEMORY_ID = "{memory_id}"\n')


if __name__ == "__main__":
    main()
