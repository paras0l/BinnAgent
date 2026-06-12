from src.providers.base import ChatRequest
from src.providers.router import router


async def call_llm(
    messages: list[dict[str, str]],
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    all_messages: list[dict[str, str]] = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    response = await router.chat(
        ChatRequest(
            messages=all_messages,
            task_type="graph_node",
            temperature=temperature,
            max_tokens=max_tokens,
        )
    )
    return response.content
