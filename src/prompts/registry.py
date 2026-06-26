import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.prompts.schemas import SCHEMA_REGISTRY


@dataclass(frozen=True)
class PromptMetadata:
    id: str
    version: str
    owner: str
    purpose: str
    template_path: str
    input_schema: str | None = None
    output_schema: str | None = None
    model_policy: dict[str, Any] | None = None
    eval_set: str | None = None
    status: str = "active"


@dataclass(frozen=True)
class RenderedPrompt:
    prompt_id: str
    version: str
    prompt: str
    prompt_hash: str
    input_hash: str
    input_schema: str | None
    output_schema: str | None
    output_schema_json: dict[str, Any] | None
    model_policy: dict[str, Any]


class PromptRegistry:
    def __init__(self, *, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).parent
        self._items: dict[tuple[str, str], PromptMetadata] = {}

    def register(self, metadata: PromptMetadata) -> None:
        self._items[(metadata.id, metadata.version)] = metadata

    def get(self, prompt_id: str, version: str | None = None) -> PromptMetadata:
        if version is not None:
            item = self._items.get((prompt_id, version))
            if item is None:
                raise KeyError(f"Unknown prompt {prompt_id}@{version}")
            return item
        candidates = [
            item for (item_id, _), item in self._items.items() if item_id == prompt_id
        ]
        active = [item for item in candidates if item.status == "active"]
        if not active:
            raise KeyError(f"Unknown prompt {prompt_id}")
        return sorted(active, key=lambda item: item.version)[-1]

    def render(
        self,
        *,
        prompt_id: str,
        variables: dict[str, Any],
        version: str | None = None,
    ) -> RenderedPrompt:
        metadata = self.get(prompt_id, version)
        template = (self.base_dir / metadata.template_path).read_text(encoding="utf-8")
        rendered = _render_template(template, variables)
        prompt_hash = _sha256_text(rendered)
        input_hash = _sha256_text(json.dumps(variables, ensure_ascii=False, sort_keys=True))
        schema_json = SCHEMA_REGISTRY.get(metadata.output_schema or "")
        return RenderedPrompt(
            prompt_id=metadata.id,
            version=metadata.version,
            prompt=rendered,
            prompt_hash=prompt_hash,
            input_hash=input_hash,
            input_schema=metadata.input_schema,
            output_schema=metadata.output_schema,
            output_schema_json=schema_json,
            model_policy=metadata.model_policy or {},
        )

    def list(self) -> list[PromptMetadata]:
        return sorted(self._items.values(), key=lambda item: (item.id, item.version))


def _render_template(template: str, variables: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        value = variables.get(name, "")
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, indent=2)

    return re.sub(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}", replace, template).strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


prompt_registry = PromptRegistry()

prompt_registry.register(
    PromptMetadata(
        id="tutor.chat",
        version="v1",
        owner="chat",
        purpose="英语学习助教的基础 system prompt",
        template_path="versions/tutor.chat.v1.md",
        model_policy={"default_model": "ollama_chat", "temperature": 0.7},
    )
)
prompt_registry.register(
    PromptMetadata(
        id="vocabulary.agent.extract",
        version="v1",
        owner="vocabulary",
        purpose="从学习对话中提取可沉淀词卡",
        template_path="versions/vocabulary.agent.extract.v1.md",
        output_schema="VocabularyExtractOutput",
        model_policy={"default_model": "ollama_utility", "temperature": 0.1, "max_tokens": 1200},
        eval_set="evals/prompts/vocabulary_agent_extract_v1.jsonl",
    )
)
prompt_registry.register(
    PromptMetadata(
        id="grammar.micro_lesson.structured",
        version="v1",
        owner="grammar",
        purpose="生成单个语法点的结构化微课和展示 HTML",
        template_path="versions/grammar.micro_lesson.structured.v1.md",
        output_schema="GrammarMicroLessonOutput",
        model_policy={"default_model": "external", "temperature": 0.2, "max_tokens": 1800},
        eval_set="evals/prompts/grammar_micro_lesson_v1.jsonl",
    )
)
prompt_registry.register(
    PromptMetadata(
        id="writing_phrase.import",
        version="v1",
        owner="writing",
        purpose="生成或提取可导入的写作好句 JSON 候选",
        template_path="versions/writing_phrase.import.v1.md",
        output_schema="WritingPhraseImportOutput",
        model_policy={"default_model": "external", "temperature": 0.2, "max_tokens": 1800},
        eval_set="evals/prompts/writing_phrase_import_v1.jsonl",
    )
)
