from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.prompts import prompt_registry

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


class RenderPromptRequest(BaseModel):
    version: str | None = Field(default=None, max_length=50)
    variables: dict[str, Any] = Field(default_factory=dict)


class RenderPromptResponse(BaseModel):
    prompt_id: str
    version: str
    prompt: str
    prompt_hash: str
    input_hash: str
    input_schema: str | None = None
    output_schema: str | None = None
    output_schema_json: dict[str, Any] | None = None
    model_policy: dict[str, Any] = Field(default_factory=dict)


@router.post("/{prompt_id:path}/render", response_model=RenderPromptResponse)
async def render_prompt(prompt_id: str, body: RenderPromptRequest) -> RenderPromptResponse:
    try:
        rendered = prompt_registry.render(
            prompt_id=prompt_id,
            version=body.version,
            variables=body.variables,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RenderPromptResponse(
        prompt_id=rendered.prompt_id,
        version=rendered.version,
        prompt=rendered.prompt,
        prompt_hash=rendered.prompt_hash,
        input_hash=rendered.input_hash,
        input_schema=rendered.input_schema,
        output_schema=rendered.output_schema,
        output_schema_json=rendered.output_schema_json,
        model_policy=rendered.model_policy,
    )
