from src.knowledge.public_textbook_seed import load_public_textbook_seed


def test_public_textbook_seed_materializes_existing_knowledge_models() -> None:
    seed = load_public_textbook_seed()
    sources = seed["sources"]

    assert len(sources) == 2
    for source in sources:
        assert source["source_seed"]["visibility"] == "public"
        assert source["source_seed"]["owner_learner_id"] is None
        assert len(source["curriculum_nodes"]) == source["source_seed"]["unit_count"]
        assert len(source["knowledge_points"]) == source["source_seed"]["knowledge_count"]
        assert len(source["exercise_questions"]) >= 36
        assert all(point["source_id"] == source["id"] for point in source["knowledge_points"])
        assert all(question["source_id"] == source["id"] for question in source["exercise_questions"])


def test_public_textbook_seed_links_questions_to_seeded_points() -> None:
    seed = load_public_textbook_seed()
    for source in seed["sources"]:
        point_ids = {point["id"] for point in source["knowledge_points"]}
        node_ids = {node["id"] for node in source["curriculum_nodes"]}

        for question in source["exercise_questions"]:
            assert question["curriculum_node_id"] in node_ids
            assert question["knowledge_point_id"] in point_ids
            assert question["metadata"]["origin"] == "curated_public_textbook_seed"
            assert question["metadata"]["stable_key"]


def test_public_textbook_seed_uses_short_structured_content() -> None:
    seed = load_public_textbook_seed()
    forbidden_keys = {"page_text", "raw_page_text", "full_text", "raw_pdf_text", "tapescript", "tapescripts"}

    def walk(value: object) -> None:
        if isinstance(value, dict):
            assert forbidden_keys.isdisjoint({str(key).lower() for key in value})
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str):
            assert len(value) <= 1200

    walk(seed)
