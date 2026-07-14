from src.adaptive.policy import TeachingPolicyCompiler


def test_low_mastery_policy_is_guided_and_focused() -> None:
    policy = TeachingPolicyCompiler().compile(
        knowledge_point_id="grammar.article_usage",
        mastery=0.25,
        retrievability=0.41,
        production=0.12,
    )
    assert policy.difficulty_band == (0.15, 0.35)
    assert policy.support_level == "guided"
    assert policy.max_new_concepts == 1
    assert policy.evidence_mode == "recall"


def test_mid_mastery_policy_delays_hints_and_uses_near_transfer() -> None:
    policy = TeachingPolicyCompiler().compile(
        knowledge_point_id="grammar.article_usage",
        mastery=0.58,
        retrievability=0.76,
        production=0.43,
    )
    assert policy.support_level == "delayed_hint"
    assert policy.practice_form == "near_transfer"


def test_high_mastery_due_policy_uses_novel_transfer() -> None:
    policy = TeachingPolicyCompiler().compile(
        knowledge_point_id="grammar.article_usage",
        mastery=0.87,
        retrievability=0.69,
        production=0.81,
    )
    assert policy.support_level == "minimal"
    assert policy.evidence_mode == "production"
    assert policy.practice_form == "novel_transfer"
    assert policy.difficulty_band[0] >= 0.7


def test_dkt_only_changes_policy_when_feature_is_enabled() -> None:
    compiler = TeachingPolicyCompiler()
    shadow = compiler.compile(
        knowledge_point_id="grammar.article_usage",
        mastery=0.8,
        retrievability=0.9,
        dkt_prediction=0.2,
        dkt_enabled=False,
    )
    active = compiler.compile(
        knowledge_point_id="grammar.article_usage",
        mastery=0.8,
        retrievability=0.9,
        dkt_prediction=0.2,
        dkt_enabled=True,
    )
    assert shadow.support_level == "minimal"
    assert active.support_level == "guided"
