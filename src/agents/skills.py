from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.agents.vocabulary_agent import VOCABULARY_AGENT_NAME


VOCABULARY_DEPOSIT_SKILL_ID = "vocabulary_deposit"


@dataclass(frozen=True)
class AgentSkill:
    id: str
    name: str
    description: str
    trigger_phrases: tuple[str, ...]
    activation_mode: str
    system_prompt_patch: str
    agent_name: str
    status_messages: dict[str, str]


VOCABULARY_DEPOSIT_SKILL = AgentSkill(
    id=VOCABULARY_DEPOSIT_SKILL_ID,
    name="词汇 Skill",
    description="持续提炼英语学习对话中的高质量词卡，并沉淀到词汇本。",
    trigger_phrases=(
        "ai 词汇讲解沉淀",
        "cet 词汇教练",
        "提炼值得记忆的重点词",
        "加入词汇本",
        "讲解单词",
        "提炼词汇",
        "词汇本",
    ),
    activation_mode="thread",
    system_prompt_patch=(
        "当前已启用词汇 Skill。请优先围绕词汇释义、音标、搭配、例句、"
        "四六级使用场景进行讲解；如果用户给出句子或段落，请自然指出值得掌握的重点词。"
    ),
    agent_name=VOCABULARY_AGENT_NAME,
    status_messages={
        "enabled": "已启用词汇 Skill，本会话会持续沉淀词卡。",
        "started": "词汇 Agent 正在后台整理词卡...",
        "completed": "已沉淀 {saved_count} 个词到词汇本",
        "skipped": "本轮没有发现符合标准的可沉淀词汇",
        "failed": "词汇沉淀暂时失败，对话内容已保留",
    },
)

SKILL_REGISTRY: dict[str, AgentSkill] = {
    VOCABULARY_DEPOSIT_SKILL.id: VOCABULARY_DEPOSIT_SKILL,
}


def skill_for_id(skill_id: str | None) -> AgentSkill | None:
    if not isinstance(skill_id, str):
        return None
    return SKILL_REGISTRY.get(skill_id.strip().lower())


def skill_from_legacy_focus(skill_focus: str | None) -> AgentSkill | None:
    if not isinstance(skill_focus, str):
        return None
    if skill_focus.strip().lower() == "vocabulary":
        return VOCABULARY_DEPOSIT_SKILL
    return None


def suggested_skill_for_message(user_message: str) -> AgentSkill | None:
    lower = user_message.lower()
    for skill in SKILL_REGISTRY.values():
        if any(phrase.lower() in lower for phrase in skill.trigger_phrases):
            return skill
    return None


def skill_from_thread_metadata(metadata: dict[str, Any] | None) -> AgentSkill | None:
    if not isinstance(metadata, dict):
        return None
    return skill_for_id(metadata.get("skill_id"))


def resolve_effective_skill(
    *,
    explicit_skill_id: str | None,
    legacy_skill_focus: str | None,
    thread_metadata: dict[str, Any] | None,
    user_message: str,
) -> AgentSkill | None:
    return (
        skill_for_id(explicit_skill_id)
        or skill_from_legacy_focus(legacy_skill_focus)
        or skill_from_thread_metadata(thread_metadata)
        or suggested_skill_for_message(user_message)
    )


def apply_skill_to_metadata(metadata: dict[str, Any] | None, skill: AgentSkill | None) -> dict[str, Any]:
    next_metadata = dict(metadata or {})
    if skill is None:
        return next_metadata
    next_metadata["skill_id"] = skill.id
    next_metadata["skill_name"] = skill.name
    return next_metadata


def clear_skill_from_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    next_metadata = dict(metadata or {})
    next_metadata.pop("skill_id", None)
    next_metadata.pop("skill_name", None)
    return next_metadata
