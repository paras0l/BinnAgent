import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.api.deps import get_model_router
from src.providers.base import ChatRequest as ModelChatRequest
from src.providers.router import ModelRouter

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    skill_focus: str | None = Field(default=None, max_length=50)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Message must not be blank")
        return stripped


class ChatResponse(BaseModel):
    reply: str
    response: str
    skill_focus: str | None = None


TUTOR_SYSTEM_PROMPT = """你是BinnAgent，一位专业的英语学习AI助教。你的职责是帮助学员提高英语水平，特别是针对CET-4和CET-6考试。

你的特点：
- 用中文与学员交流，但会穿插英语例句和解释
- 耐心、鼓励、专业
- 能解释词汇、语法、阅读理解、写作技巧
- 会根据学员水平调整难度
- 主动提问检验学员理解程度

请用简洁友好的方式回复学员的问题。如果学员问的是英语学习相关的问题，请用中英文结合的方式回答。"""


@router.post("/send", response_model=ChatResponse)
async def chat_send(
    req: ChatRequest,
    model_router: ModelRouter = Depends(get_model_router),
) -> ChatResponse:
    system_msg = TUTOR_SYSTEM_PROMPT
    if req.skill_focus:
        system_msg += f"\n\n当前重点练习: {req.skill_focus}"

    try:
        model_response = await model_router.chat(
            ModelChatRequest(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": req.message},
                ],
                task_type="learning_chat",
                temperature=0.7,
                max_tokens=1024,
            )
        )
        reply = model_response.content or "抱歉，我暂时无法回复。"
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Ollama service unavailable")

    return ChatResponse(reply=reply, response=reply, skill_focus=req.skill_focus)
