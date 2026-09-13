from __future__ import annotations
import base64
import json
import logging
from pathlib import Path
from typing import Any

import boto3
from pydantic import BaseModel

log = logging.getLogger(__name__)


def _inject_bearer_token(token: str):
    def _handler(request, **kwargs):
        request.headers["Authorization"] = f"Bearer {token}"
    return _handler


class BedrockClient:
    def __init__(self, region: str, model_id: str, bearer_token: str = ""):
        if bearer_token:
            import botocore
            from botocore.config import Config
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=region,
                config=Config(signature_version=botocore.UNSIGNED),
            )
            self._client.meta.events.register("before-send", _inject_bearer_token(token=bearer_token))
        else:
            self._client = boto3.client("bedrock-runtime", region_name=region)
        self._model_id = model_id

    def converse_with_image(
        self,
        system_prompt: str,
        user_text: str,
        image_bytes: bytes,
        image_format: str,
        tool_schema: dict,
        tool_name: str,
    ) -> dict | None:
        return self._call(
            system_prompt=system_prompt,
            messages=[{
                "role": "user",
                "content": [
                    {"image": {"format": image_format, "source": {"bytes": image_bytes}}},
                    {"text": user_text},
                ],
            }],
            tool_schema=tool_schema,
            tool_name=tool_name,
        )

    def converse_text(
        self,
        system_prompt: str,
        user_text: str,
        tool_schema: dict,
        tool_name: str,
    ) -> dict | None:
        return self._call(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            tool_schema=tool_schema,
            tool_name=tool_name,
        )

    def _call(
        self,
        system_prompt: str,
        messages: list[dict],
        tool_schema: dict,
        tool_name: str,
        max_retries: int = 1,
    ) -> dict | None:
        tool_config = {
            "tools": [{"toolSpec": {"name": tool_name, "description": f"Return {tool_name}", "inputSchema": {"json": tool_schema}}}],
            "toolChoice": {"tool": {"name": tool_name}},
        }

        for attempt in range(1 + max_retries):
            try:
                resp = self._client.converse(
                    modelId=self._model_id,
                    system=[{"text": system_prompt}],
                    messages=messages,
                    toolConfig=tool_config,
                    inferenceConfig={"temperature": 0.0},
                )
                for block in resp.get("output", {}).get("message", {}).get("content", []):
                    if "toolUse" in block and block["toolUse"]["name"] == tool_name:
                        return block["toolUse"]["input"]

                log.warning(f"No tool use in response (attempt {attempt + 1})")
            except Exception as e:
                log.error(f"Bedrock call failed (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    return None
        return None


def parse_tool_output(raw: dict | None, model_cls: type[BaseModel]) -> BaseModel | None:
    if raw is None:
        return None
    try:
        return model_cls.model_validate(raw)
    except Exception as e:
        log.warning(f"Schema validation failed: {e}")
        return None
