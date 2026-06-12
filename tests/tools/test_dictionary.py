from src.tools.dictionary import DictionaryLookupRequest, DictionaryLookupResponse, dictionary


class TestDictionaryLookupKnownWord:
    async def test_lookup_known_word(self):
        request = DictionaryLookupRequest(word="sustain")
        response = await dictionary.lookup(request)

        assert isinstance(response, DictionaryLookupResponse)
        assert response.word == "sustain"
        assert response.phonetic == "/səˈsteɪn/"
        assert len(response.meanings) == 3
        assert response.meanings[0]["definition"] == "to keep something in existence; to maintain"
        assert len(response.collocations) == 3
        assert len(response.examples) == 3
        assert len(response.confusing_words) == 2
        assert response.cet_relevance == "high (frequent in reading comprehension)"
        assert response.provider == "local"


class TestDictionaryLookupUnknownWord:
    async def test_lookup_unknown_word(self):
        request = DictionaryLookupRequest(word="xyz")
        response = await dictionary.lookup(request)

        assert isinstance(response, DictionaryLookupResponse)
        assert response.word == "xyz"
        assert response.provider in ("ollama", "ollama_error")


class TestDictionaryLookupWithContext:
    async def test_lookup_with_context(self):
        request = DictionaryLookupRequest(
            word="abandon",
            context_sentence="They had to abandon the project.",
        )
        response = await dictionary.lookup(request)

        assert response.word == "abandon"
        assert response.contextual_meaning is not None
        assert len(response.meanings) == 3
