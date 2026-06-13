import re

_VALID_WORD_RE = re.compile(r"^[a-z]+(?:-[a-z]+)?$")

_VOCABULARY_STOPWORDS = {
    "about",
    "above",
    "after",
    "again",
    "also",
    "being",
    "because",
    "before",
    "could",
    "define",
    "definition",
    "english",
    "example",
    "examples",
    "explain",
    "from",
    "grammar",
    "have",
    "hear",
    "into",
    "learn",
    "learning",
    "let",
    "like",
    "mean",
    "meaning",
    "means",
    "ready",
    "sorry",
    "start",
    "started",
    "sentence",
    "should",
    "that",
    "their",
    "there",
    "these",
    "this",
    "those",
    "translate",
    "translation",
    "unable",
    "vocab",
    "vocabulary",
    "will",
    "with",
    "word",
    "words",
    "would",
    "your",
}


def normalize_vocabulary_word(value: str) -> str | None:
    """Return a safe single-word vocabulary key, or None when it should not be stored."""
    word = value.strip().lower().strip(".,;:!?()[]{}\"`*_")
    if word.endswith("'s"):
        word = word[:-2]

    if not 3 <= len(word) <= 30:
        return None
    if word in _VOCABULARY_STOPWORDS:
        return None
    if not _VALID_WORD_RE.fullmatch(word):
        return None
    if len(set(word.replace("-", ""))) <= 1:
        return None
    return word
