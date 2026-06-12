from unittest.mock import AsyncMock
import importlib

from src.providers.base import ChatResponse
from src.tools.dictionary import DictionaryLookupRequest, DictionaryLookupResponse, dictionary

dictionary_module = importlib.import_module("src.tools.dictionary")


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

    async def test_lookup_unknown_word_uses_model_router(self, monkeypatch):
        mock_router = AsyncMock()
        mock_router.chat = AsyncMock(
            return_value=ChatResponse(
                provider="ollama",
                model="gemma4:e2b",
                content='{"phonetic": "/test/", "meanings": [{"definition": "test"}]}',
            )
        )
        monkeypatch.setattr(dictionary_module, "router", mock_router)

        response = await dictionary.lookup(DictionaryLookupRequest(word="xyz"))

        assert response.provider == "ollama"
        assert response.phonetic == "/test/"
        request = mock_router.chat.await_args.args[0]
        assert request.task_type == "dictionary_lookup"
        assert request.temperature == 0.3
        assert request.max_tokens == 512


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
