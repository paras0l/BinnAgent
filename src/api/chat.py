from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

from src.config import settings

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    skill_focus: str | None = None


class ChatResponse(BaseModel):
    reply: str
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
async def chat_send(req: ChatRequest) -> ChatResponse:
    system_msg = TUTOR_SYSTEM_PROMPT
    if req.skill_focus:
        system_msg += f"\n\n当前重点练习: {req.skill_focus}"

    payload = {
        "model": settings.ollama_chat_model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": req.message},
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 1024,
        },
    }

    try:
        async with httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=httpx.Timeout(120.0),
        ) as client:
            resp = await client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            reply = data.get("message", {}).get("content", "抱歉，我暂时无法回复。")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Ollama service unavailable: {e}")

    return ChatResponse(reply=reply, skill_focus=req.skill_focus)
