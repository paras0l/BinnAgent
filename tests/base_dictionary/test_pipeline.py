from src.base_dictionary.pipeline import (
    BuildConfig,
    SentencePair,
    build_dictionary,
    canonical_key,
    classify_entry,
)


class FakeRelations:
    def relations_for(self, lemma: str) -> list[dict[str, str]]:
        return [{"type": "hypernym", "target": f"kind of {lemma}", "source": "test"}]


def item(word: str, pos: str, senses: list[dict], **extra) -> dict:
    return {
        "lang_code": "en",
        "word": word,
        "pos": pos,
        "senses": senses,
        **extra,
    }


def test_build_filters_and_ranks_words_and_phrases_independently() -> None:
    source = [
        item(
            "Run",
            "verb",
            [
                {"glosses": ["to move quickly on foot"]},
                {"glosses": ["to manage something"]},
                {"glosses": ["an obsolete meaning"], "tags": ["obsolete"]},
                {"glosses": ["to extend in a direction"]},
                {"glosses": ["a fourth current meaning"]},
            ],
        ),
        item("apple", "noun", [{"glosses": ["a round fruit"]}]),
        item("take off", "verb", [{"glosses": ["to leave the ground"]}]),
        item("by and large", "phrase", [{"glosses": ["on the whole"]}]),
        item("extremely obscure", "phrase", [{"glosses": ["not common"]}]),
    ]
    frequencies = {
        "run": 6.2,
        "apple": 5.0,
        "take off": 4.8,
        "by and large": 3.7,
        "extremely obscure": 1.0,
    }
    entries = build_dictionary(
        source,
        frequency=lambda term: frequencies[term],
        config=BuildConfig(word_limit=1, phrase_limit=2, max_senses=3),
        relation_provider=FakeRelations(),
        sentence_pairs=[
            SentencePair("1", "I run in the park every morning.", "2", "我每天早上在公园跑步。"),
            SentencePair("3", "The plane will take off very soon.", "4", "飞机很快就会起飞。"),
        ],
    )

    assert [entry.canonical_key for entry in entries] == ["run", "take off", "by and large"]
    run = entries[0]
    assert len(run.senses) == 3
    assert all("obsolete" not in sense["definition_en"] for sense in run.senses)
    assert run.relations[0]["type"] == "hypernym"
    assert run.examples[0]["translation_zh"] == "我每天早上在公园跑步。"
    assert entries[1].entry_kind == "phrasal_verb"
    assert [entry.frequency_rank for entry in entries] == [1, 2, 3]


def test_normalization_and_entry_classification() -> None:
    assert canonical_key("  Look   Up  ") == "look up"
    assert canonical_key("Learner’s") == "learner's"
    assert classify_entry("look up", ["verb"]) == "phrasal_verb"
    assert classify_entry("in spite of", ["phrase"]) == "phrase"
    assert classify_entry("learn", ["verb"]) == "word"


def test_build_can_preselect_common_words_before_collecting_entries() -> None:
    source = [
        item("common", "adj", [{"glosses": ["occurring often"]}]),
        item("specialized", "adj", [{"glosses": ["requiring specialist knowledge"]}]),
        item("take off", "verb", [{"glosses": ["to leave the ground"]}]),
    ]
    frequencies = {"common": 5.5, "specialized": 3.5, "take off": 4.8}

    entries = build_dictionary(
        source,
        frequency=lambda term: frequencies[term],
        config=BuildConfig(word_limit=10, phrase_limit=10, min_phrase_zipf=2.0),
        allowed_word_keys={"common"},
    )

    assert [entry.canonical_key for entry in entries] == ["common", "take off"]
