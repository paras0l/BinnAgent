from datetime import datetime
from typing import Any, Literal

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
    version: str = "1.0.0"
    source: Literal["internal", "mcp"] = "internal"
    provider_ref: str = "binnagent.core"
    enabled: bool = True
    health_status: Literal["healthy", "degraded", "unavailable", "disabled"] = "healthy"
    spec_hash: str | None = None
    registered_at: datetime | None = None
    last_health_check_at: datetime | None = None
    required_scopes: list[str] = Field(default_factory=list)
    injected_fields: list[str] = Field(default_factory=list)
    idempotency: Literal["safe", "keyed", "unsafe"] = "unsafe"


class ToolExecutionInput(BaseModel):
    tool_name: str
    episode_id: str | None = None
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[str] | None = None
    catalog_revision: str | None = None


class ToolExecutionResult(BaseModel):
    tool_name: str
    status: str
    output: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: int | None = None
    input_hash: str
    output_hash: str | None = None
    error_code: str | None = None
    tool_version: str | None = None
    catalog_revision: str | None = None
    attempt_count: int = 1


class ToolCatalogView(BaseModel):
    revision: str
    generation: int
    created_at: datetime
    refreshed_at: datetime
    tool_count: int
    enabled_count: int
    healthy_count: int
    degraded_count: int
    unavailable_count: int
    disabled_count: int
    refresh_count: int
    failed_refresh_count: int
    last_refresh_error: str | None = None
    tools: list[ToolSpec]


class ToolResolutionRequest(BaseModel):
    allowed_tools: list[str] = Field(default_factory=list)


class ToolResolutionItem(BaseModel):
    name: str
    version: str
    allowed: bool
    reason: str


class ToolResolutionView(BaseModel):
    catalog_revision: str
    items: list[ToolResolutionItem]
