from dataclasses import dataclass, field
from typing import Optional

import httpx

from src.config import settings


@dataclass
class DictionaryLookupRequest:
    word: str
    learner_level: str = "cet6"
    context_sentence: Optional[str] = None


@dataclass
class DictionaryLookupResponse:
    word: str
    phonetic: str
    meanings: list[dict]
    contextual_meaning: Optional[str] = None
    collocations: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    confusing_words: list[dict] = field(default_factory=list)
    cet_relevance: str = ""
    provider: str = "local"


LOCAL_DICT: dict[str, dict] = {
    "sustain": {
        "phonetic": "/səˈsteɪn/",
        "meanings": [
            {"part_of_speech": "verb", "definition": "to keep something in existence; to maintain"},
            {
                "part_of_speech": "verb",
                "definition": "to suffer or experience something unpleasant",
            },
            {"part_of_speech": "verb", "definition": "to support or hold up"},
        ],
        "collocations": ["sustain economic growth", "sustain an injury", "sustain life"],
        "examples": [
            "The company managed to sustain its growth despite the recession.",
            "He sustained a serious injury during the match.",
            "The soil is too poor to sustain plant life.",
        ],
        "confusing_words": [
            {
                "word": "maintain",
                "difference": "maintain focuses on keeping at a certain level; sustain focuses on enduring over time",
            },
            {
                "word": "retain",
                "difference": "retain means to keep hold of; sustain means to keep alive or going",
            },
        ],
        "cet_relevance": "high (frequent in reading comprehension)",
    },
    "abandon": {
        "phonetic": "/əˈbændən/",
        "meanings": [
            {
                "part_of_speech": "verb",
                "definition": "to leave a place, thing, or person permanently",
            },
            {
                "part_of_speech": "verb",
                "definition": "to stop doing something before it is complete",
            },
            {"part_of_speech": "noun", "definition": "complete lack of inhibition or restraint"},
        ],
        "collocations": ["abandon a project", "abandon hope", "abandon a plan"],
        "examples": [
            "They had to abandon the project due to lack of funding.",
            "The crew abandoned the sinking ship.",
            "She danced with abandon.",
        ],
        "confusing_words": [
            {
                "word": "give up",
                "difference": "give up is more general; abandon implies leaving something behind",
            },
            {
                "word": "desert",
                "difference": "desert implies leaving in a way that violates a promise or duty",
            },
        ],
        "cet_relevance": "high (common in CET-4 and CET-6)",
    },
    "significant": {
        "phonetic": "/sɪɡˈnɪfɪkənt/",
        "meanings": [
            {
                "part_of_speech": "adjective",
                "definition": "sufficiently great or important to be worthy of attention",
            },
            {
                "part_of_speech": "adjective",
                "definition": "having a particular meaning; indicative",
            },
        ],
        "collocations": ["significant impact", "significant role", "significant amount"],
        "examples": [
            "This is a significant achievement for the company.",
            "The results were statistically significant.",
            "She made a significant contribution to the project.",
        ],
        "confusing_words": [
            {
                "word": "important",
                "difference": "important is more general; significant implies deeper meaning or impact",
            },
            {
                "word": "substantial",
                "difference": "substantial focuses on size/quantity; significant focuses on meaning/importance",
            },
        ],
        "cet_relevance": "high (very common in CET-6 reading)",
    },
    "sustainable": {
        "phonetic": "/səˈsteɪnəbl/",
        "meanings": [
            {
                "part_of_speech": "adjective",
                "definition": "able to be maintained or continued over time",
            },
            {"part_of_speech": "adjective", "definition": "able to be upheld or defended"},
        ],
        "collocations": ["sustainable development", "sustainable energy", "sustainable practices"],
        "examples": [
            "We need to find sustainable solutions to environmental problems.",
            "The company is committed to sustainable business practices.",
            "Renewable energy is essential for a sustainable future.",
        ],
        "confusing_words": [
            {
                "word": "viable",
                "difference": "viable means feasible/possible; sustainable means can continue long-term",
            },
            {
                "word": "feasible",
                "difference": "feasible means can be done; sustainable means can be maintained indefinitely",
            },
        ],
        "cet_relevance": "high (frequent in CET-6 reading on environment)",
    },
    "phenomenon": {
        "phonetic": "/fəˈnɒmɪnən/",
        "meanings": [
            {"part_of_speech": "noun", "definition": "a fact or event that can be observed"},
            {"part_of_speech": "noun", "definition": "a remarkable or unusual person or thing"},
        ],
        "collocations": ["natural phenomenon", "social phenomenon", "rare phenomenon"],
        "examples": [
            "The Northern Lights are a beautiful natural phenomenon.",
            "Social media has become a global phenomenon.",
            "Climate change is a complex phenomenon with many causes.",
        ],
        "confusing_words": [
            {
                "word": "occurrence",
                "difference": "occurrence is something that happens; phenomenon is something remarkable or observable",
            },
            {
                "word": "event",
                "difference": "event is a specific happening; phenomenon is a broader observable fact",
            },
        ],
        "cet_relevance": "high (common in CET-6 reading)",
    },
    "controversy": {
        "phonetic": "/ˈkɒntrəvɜːsi/",
        "meanings": [
            {
                "part_of_speech": "noun",
                "definition": "prolonged public disagreement or heated discussion",
            },
        ],
        "collocations": ["cause controversy", "major controversy", "political controversy"],
        "examples": [
            "The decision sparked a lot of controversy.",
            "There is considerable controversy surrounding this issue.",
            "The movie caused controversy due to its subject matter.",
        ],
        "confusing_words": [
            {
                "word": "debate",
                "difference": "debate is a formal discussion; controversy implies public disagreement",
            },
            {
                "word": "dispute",
                "difference": "dispute is a specific argument; controversy is broader public disagreement",
            },
        ],
        "cet_relevance": "high (common in CET-6 reading on social issues)",
    },
    "inevitable": {
        "phonetic": "/ɪnˈevɪtl/",
        "meanings": [
            {"part_of_speech": "adjective", "definition": "certain to happen; unavoidable"},
        ],
        "collocations": ["inevitable outcome", "inevitable consequence", "inevitable change"],
        "examples": [
            "Change is inevitable in any organization.",
            "The inevitable happened — the project was cancelled.",
            "With rising costs, price increases were inevitable.",
        ],
        "confusing_words": [
            {
                "word": "unavoidable",
                "difference": "unavoidable means cannot be avoided; inevitable emphasizes certainty",
            },
            {
                "word": "certain",
                "difference": "certain means will definitely happen; inevitable implies unavoidable and often negative",
            },
        ],
        "cet_relevance": "high (frequent in CET-6 reading)",
    },
    "preliminary": {
        "phonetic": "/prɪˈlɪmɪnəri/",
        "meanings": [
            {
                "part_of_speech": "adjective",
                "definition": "happening before a more important action or event",
            },
            {"part_of_speech": "noun", "definition": "an initial or preparatory step"},
        ],
        "collocations": ["preliminary results", "preliminary investigation", "preliminary stage"],
        "examples": [
            "The preliminary results suggest the treatment is effective.",
            "We are still in the preliminary stages of the project.",
            "A preliminary investigation was conducted before the main inquiry.",
        ],
        "confusing_words": [
            {
                "word": "initial",
                "difference": "initial means first; preliminary means preparatory before the main event",
            },
            {
                "word": "introductory",
                "difference": "introductory means serving as an introduction; preliminary means before the main action",
            },
        ],
        "cet_relevance": "high (common in CET-6 academic reading)",
    },
    "advocate": {
        "phonetic": "/ˈædvəkeɪt/",
        "meanings": [
            {"part_of_speech": "verb", "definition": "to publicly recommend or support"},
            {"part_of_speech": "noun", "definition": "a person who publicly supports a cause"},
        ],
        "collocations": ["advocate for change", "advocate policy", "strong advocate"],
        "examples": [
            "She advocates for environmental protection.",
            "He is an advocate of free speech.",
            "Many scientists advocate for immediate action on climate change.",
        ],
        "confusing_words": [
            {
                "word": "support",
                "difference": "support is more general; advocate implies public, active endorsement",
            },
            {
                "word": "recommend",
                "difference": "recommend suggests; advocate actively promotes and defends",
            },
        ],
        "cet_relevance": "high (common in CET-6 reading)",
    },
    "consequence": {
        "phonetic": "/ˈkɒnsɪkwəns/",
        "meanings": [
            {
                "part_of_speech": "noun",
                "definition": "a result or effect of an action or condition",
            },
            {"part_of_speech": "noun", "definition": "importance or significance"},
        ],
        "collocations": ["serious consequence", "consequence of", "face the consequences"],
        "examples": [
            "The consequences of the decision were far-reaching.",
            "You must face the consequences of your actions.",
            "Climate change has serious consequences for future generations.",
        ],
        "confusing_words": [
            {
                "word": "result",
                "difference": "result is neutral; consequence often implies negative outcome",
            },
            {
                "word": "effect",
                "difference": "effect is the change produced; consequence is the resulting situation",
            },
        ],
        "cet_relevance": "high (very common in CET-4 and CET-6)",
    },
    "perspective": {
        "phonetic": "/pəˈspektɪv/",
        "meanings": [
            {
                "part_of_speech": "noun",
                "definition": "a particular attitude or way of regarding something",
            },
            {
                "part_of_speech": "noun",
                "definition": "the art of representing 3D objects on a 2D surface",
            },
        ],
        "collocations": ["from a perspective", "gain perspective", "shift perspective"],
        "examples": [
            "Try to see the problem from a different perspective.",
            "Travel helps you gain a new perspective on life.",
            "The article offers a unique perspective on the issue.",
        ],
        "confusing_words": [
            {
                "word": "viewpoint",
                "difference": "viewpoint is a specific opinion; perspective is a broader way of seeing things",
            },
            {
                "word": "standpoint",
                "difference": "standpoint is based on position/belief; perspective considers multiple angles",
            },
        ],
        "cet_relevance": "high (common in CET-6 reading and writing)",
    },
    "elaborate": {
        "phonetic": "/ɪˈlæbəreɪt/",
        "meanings": [
            {
                "part_of_speech": "adjective",
                "definition": "involving many carefully arranged parts or details",
            },
            {"part_of_speech": "verb", "definition": "to develop or present in detail"},
        ],
        "collocations": ["elaborate plan", "elaborate on", "elaborate design"],
        "examples": [
            "She had prepared an elaborate presentation.",
            "Could you elaborate on your idea?",
            "The architecture was incredibly elaborate.",
        ],
        "confusing_words": [
            {
                "word": "detailed",
                "difference": "detailed means having many details; elaborate implies complexity and careful arrangement",
            },
            {
                "word": "complex",
                "difference": "complex means complicated; elaborate means intricately designed",
            },
        ],
        "cet_relevance": "high (common in CET-6 reading)",
    },
    "comprehensive": {
        "phonetic": "/ˌkɒmprɪˈhensɪv/",
        "meanings": [
            {
                "part_of_speech": "adjective",
                "definition": "including all or nearly all elements or aspects",
            },
        ],
        "collocations": [
            "comprehensive review",
            "comprehensive plan",
            "comprehensive understanding",
        ],
        "examples": [
            "The report provides a comprehensive analysis of the market.",
            "We need a comprehensive approach to solve this problem.",
            "Students received comprehensive feedback on their essays.",
        ],
        "confusing_words": [
            {
                "word": "thorough",
                "difference": "thorough means careful and complete; comprehensive means including everything",
            },
            {
                "word": "extensive",
                "difference": "extensive means large in scope; comprehensive means covering all aspects",
            },
        ],
        "cet_relevance": "high (common in CET-6 academic writing)",
    },
    "substantial": {
        "phonetic": "/səbˈstænʃl/",
        "meanings": [
            {
                "part_of_speech": "adjective",
                "definition": "of considerable importance, size, or worth",
            },
            {"part_of_speech": "adjective", "definition": "strongly built or made; sturdy"},
        ],
        "collocations": ["substantial amount", "substantial progress", "substantial evidence"],
        "examples": [
            "The company made substantial profits last year.",
            "There has been substantial progress in the research.",
            "A substantial amount of evidence was presented.",
        ],
        "confusing_words": [
            {
                "word": "significant",
                "difference": "significant emphasizes importance; substantial emphasizes size/quantity",
            },
            {
                "word": "considerable",
                "difference": "considerable means notably large; substantial means large and solid",
            },
        ],
        "cet_relevance": "high (common in CET-4 and CET-6)",
    },
    "profound": {
        "phonetic": "/prəˈfaʊnd/",
        "meanings": [
            {"part_of_speech": "adjective", "definition": "very great or intense"},
            {"part_of_speech": "adjective", "definition": "having deep insight or knowledge"},
        ],
        "collocations": ["profound impact", "profound effect", "profound knowledge"],
        "examples": [
            "The war had a profound effect on the population.",
            "She has a profound understanding of the subject.",
            "The book made a profound impression on me.",
        ],
        "confusing_words": [
            {
                "word": "deep",
                "difference": "deep is more general; profound implies intensity or depth of understanding",
            },
            {
                "word": "significant",
                "difference": "significant means important; profound means deeply meaningful or intense",
            },
        ],
        "cet_relevance": "high (common in CET-6 reading)",
    },
    "ambiguous": {
        "phonetic": "/æmˈbɪɡjuəs/",
        "meanings": [
            {
                "part_of_speech": "adjective",
                "definition": "open to more than one interpretation; not clear",
            },
        ],
        "collocations": ["ambiguous statement", "ambiguous meaning", "deliberately ambiguous"],
        "examples": [
            "The instructions were ambiguous and confusing.",
            "The ending of the movie was deliberately ambiguous.",
            "His ambiguous response left everyone uncertain.",
        ],
        "confusing_words": [
            {
                "word": "vague",
                "difference": "vague means unclear/lacking detail; ambiguous means having multiple interpretations",
            },
            {
                "word": "unclear",
                "difference": "unclear means not easy to understand; ambiguous means could mean different things",
            },
        ],
        "cet_relevance": "high (common in CET-6 reading)",
    },
    "inevitably": {
        "phonetic": "/ɪnˈevɪtəbli/",
        "meanings": [
            {"part_of_speech": "adverb", "definition": "in a way that cannot be avoided"},
        ],
        "collocations": ["inevitably lead to", "inevitably result in"],
        "examples": [
            "Prices will inevitably rise due to inflation.",
            "The changes will inevitably affect everyone.",
            "Technology will inevitably transform education.",
        ],
        "confusing_words": [
            {
                "word": "unavoidably",
                "difference": "unavoidably means cannot be avoided; inevitably emphasizes certainty",
            },
            {
                "word": "certainly",
                "difference": "certainly means definitely; inevitably implies unavoidable consequence",
            },
        ],
        "cet_relevance": "high (common in CET-6 reading)",
    },
    "deteriorate": {
        "phonetic": "/dɪˈtɪəriəreɪt/",
        "meanings": [
            {"part_of_speech": "verb", "definition": "to become progressively worse"},
        ],
        "collocations": ["deteriorate rapidly", "deteriorate condition", "deteriorate health"],
        "examples": [
            "The patient's condition began to deteriorate.",
            "The building has deteriorated over the years.",
            "Relations between the two countries have deteriorated.",
        ],
        "confusing_words": [
            {
                "word": "worsen",
                "difference": "worsen is more general; deteriorate implies gradual decline",
            },
            {
                "word": "decline",
                "difference": "decline can be gradual or sudden; deteriorate emphasizes getting worse",
            },
        ],
        "cet_relevance": "high (common in CET-6 reading)",
    },
    "compelling": {
        "phonetic": "/kəmˈpelɪŋ/",
        "meanings": [
            {
                "part_of_speech": "adjective",
                "definition": "evoking interest or attention in a powerfully irresistible way",
            },
            {"part_of_speech": "adjective", "definition": "not able to be refuted; convincing"},
        ],
        "collocations": ["compelling evidence", "compelling argument", "compelling story"],
        "examples": [
            "The evidence against him was compelling.",
            "She gave a compelling presentation.",
            "The novel tells a compelling story of survival.",
        ],
        "confusing_words": [
            {
                "word": "convincing",
                "difference": "convincing means able to persuade; compelling means powerfully attractive",
            },
            {
                "word": "persuasive",
                "difference": "persuasive means able to persuade; compelling means irresistibly interesting",
            },
        ],
        "cet_relevance": "high (common in CET-6 reading and writing)",
    },
    "resilient": {
        "phonetic": "/rɪˈzɪliənt/",
        "meanings": [
            {
                "part_of_speech": "adjective",
                "definition": "able to recover quickly from difficult conditions",
            },
        ],
        "collocations": ["resilient economy", "resilient community", "resilient material"],
        "examples": [
            "Children are remarkably resilient.",
            "The economy proved to be resilient despite the crisis.",
            "We need to build more resilient communities.",
        ],
        "confusing_words": [
            {
                "word": "tough",
                "difference": "tough means strong/enduring; resilient emphasizes ability to recover",
            },
            {
                "word": "adaptable",
                "difference": "adaptable means able to adjust; resilient means able to bounce back",
            },
        ],
        "cet_relevance": "high (common in CET-6 reading)",
    },
    "prosperity": {
        "phonetic": "/prɒsˈperɪti/",
        "meanings": [
            {
                "part_of_speech": "noun",
                "definition": "the state of being successful, especially in financial terms",
            },
        ],
        "collocations": ["economic prosperity", "prosperity and peace", "shared prosperity"],
        "examples": [
            "The country enjoyed a period of prosperity.",
            "Education is key to long-term prosperity.",
            "They wished for prosperity and happiness.",
        ],
        "confusing_words": [
            {
                "word": "wealth",
                "difference": "wealth is about riches; prosperity is broader success and well-being",
            },
            {
                "word": "success",
                "difference": "success is achieving goals; prosperity is sustained state of thriving",
            },
        ],
        "cet_relevance": "high (common in CET-6 reading on economics)",
    },
    "unprecedented": {
        "phonetic": "/ʌnˈpresɪdentɪd/",
        "meanings": [
            {"part_of_speech": "adjective", "definition": "never done or known before"},
        ],
        "collocations": ["unprecedented growth", "unprecedented challenge", "unprecedented times"],
        "examples": [
            "The pandemic created unprecedented challenges.",
            "The company experienced unprecedented growth.",
            "We live in unprecedented times.",
        ],
        "confusing_words": [
            {
                "word": "unparalleled",
                "difference": "unparalleled means having no equal; unprecedented means never done before",
            },
            {
                "word": "extraordinary",
                "difference": "extraordinary means remarkable; unprecedented means never existed before",
            },
        ],
        "cet_relevance": "high (very common in CET-6 reading)",
    },
}


class DictionaryTool:
    """Dictionary lookup tool with local cache and Ollama fallback."""

    async def lookup(self, request: DictionaryLookupRequest) -> DictionaryLookupResponse:
        word_key = request.word.strip().lower()
        entry = LOCAL_DICT.get(word_key)

        if entry is not None:
            contextual_meaning = None
            if request.context_sentence and entry["meanings"]:
                contextual_meaning = entry["meanings"][0]["definition"]
            return DictionaryLookupResponse(
                word=word_key,
                phonetic=entry["phonetic"],
                meanings=entry["meanings"],
                contextual_meaning=contextual_meaning,
                collocations=entry["collocations"],
                examples=entry["examples"],
                confusing_words=entry["confusing_words"],
                cet_relevance=entry["cet_relevance"],
                provider="local",
            )

        return await self._lookup_via_llm(request)

    async def _lookup_via_llm(self, request: DictionaryLookupRequest) -> DictionaryLookupResponse:
        import json as _json

        prompt = (
            f'请为英语单词 "{request.word}" 提供词典信息，'
            f"难度级别: {request.learner_level}。"
            "请用JSON格式回复，包含以下字段: "
            '{"phonetic": "音标", "meanings": [{"part_of_speech": "词性", "definition": "英文释义"}], '
            '"collocations": ["搭配"], "examples": ["例句"], '
            '"confusing_words": [{"word": "易混词", "difference": "区别"}], '
            '"cet_relevance": "考试相关性"}'
        )

        try:
            async with httpx.AsyncClient(
                base_url=settings.ollama_base_url,
                timeout=httpx.Timeout(60.0),
            ) as client:
                resp = await client.post(
                    "/api/chat",
                    json={
                        "model": settings.ollama_chat_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "你是一位专业的英语词典助手。请用JSON格式回复词典信息。",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 512},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")

            parsed = _json.loads(content)
            return DictionaryLookupResponse(
                word=request.word,
                phonetic=parsed.get("phonetic", ""),
                meanings=parsed.get("meanings", []),
                collocations=parsed.get("collocations", []),
                examples=parsed.get("examples", []),
                confusing_words=parsed.get("confusing_words", []),
                cet_relevance=parsed.get("cet_relevance", ""),
                provider="ollama",
            )
        except Exception:
            return DictionaryLookupResponse(
                word=request.word,
                phonetic="",
                meanings=[],
                provider="ollama_error",
            )


dictionary = DictionaryTool()
