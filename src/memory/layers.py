from enum import StrEnum


class MemoryLayer(StrEnum):
    CONTEXT = "L1_context"
    EVIDENCE = "L2_evidence"
    LEARNER_MODEL = "L3_learner_model"
    GOVERNANCE = "L4_governance_reflection"


LAYER_LABELS = {
    MemoryLayer.CONTEXT: "L1 Context Memory",
    MemoryLayer.EVIDENCE: "L2 Evidence Memory",
    MemoryLayer.LEARNER_MODEL: "L3 Learner Model Memory",
    MemoryLayer.GOVERNANCE: "L4 Governance & Reflection Memory",
}
