from typing import Any

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: str
    timeout_ms: int = 30000
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionInput(BaseModel):
    tool_name: str
    episode_id: str | None = None
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResult(BaseModel):
    tool_name: str
    status: str
    output: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: int | None = None
    input_hash: str
    output_hash: str | None = None
