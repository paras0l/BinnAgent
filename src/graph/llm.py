from src.prompts import PromptExecutionContext, PromptExecutor
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

    result = await PromptExecutor(model_router=router).execute_messages(
        prompt_id="graph.node",
        variables={"system_prompt": system_prompt, "messages": messages},
        messages=all_messages,
        context=PromptExecutionContext(
            source_module="graph.llm",
            task_id="graph_node",
        ),
        request_overrides={
            "task_type": "graph_node",
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
    )
    return result.raw_output
