"""Core Pydantic schemas for AgentReplay."""
from __future__ import annotations

import json
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


_MAX_NAME_LEN = 256
_MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


class NodeType(str, Enum):
    CHAIN = "chain"
    LLM = "llm"
    TOOL = "tool"
    AGENT = "agent"


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class Run(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(default="unnamed", max_length=_MAX_NAME_LEN)
    start_time: float
    end_time: float | None = None
    status: RunStatus = RunStatus.RUNNING
    metadata: dict[str, Any] = Field(default_factory=dict)

    def finish(self, *, error: str | None = None) -> None:
        import time

        self.end_time = time.time()
        self.status = RunStatus.ERROR if error else RunStatus.SUCCESS


class TraceNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    parent_id: str | None = None
    node_type: NodeType
    name: str = Field(max_length=_MAX_NAME_LEN)

    start_time: float
    end_time: float | None = None

    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=4096)

    # LLM-specific extras
    token_usage: dict[str, int] | None = None
    model_name: str | None = Field(default=None, max_length=128)

    @field_validator("inputs", "outputs")
    @classmethod
    def _check_payload_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(v)) > _MAX_PAYLOAD_BYTES:
            raise ValueError("Payload exceeds 10 MB limit")
        return v

    def finish(self, outputs: dict[str, Any], *, error: str | None = None) -> None:
        import time

        self.end_time = time.time()
        self.outputs = outputs
        self.error = error[:4096] if error else error
