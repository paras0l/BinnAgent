from src.memory.schemas import RetrievedMemoryItem


class MemoryExplainer:
    def recommendation_reason(self, items: list[RetrievedMemoryItem], fallback: str) -> str:
        if not items:
            return fallback
        primary = items[0]
        evidence = f"；证据：{', '.join(primary.evidence_refs[:2])}" if primary.evidence_refs else ""
        return f"推荐原因：{primary.summary}{evidence}"

    def card_reason(self, item: RetrievedMemoryItem) -> str:
        if item.reason:
            return f"用于 {item.reason} 推荐。"
        return "用于生成更贴合当前学习状态的练习。"
