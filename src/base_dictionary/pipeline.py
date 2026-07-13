from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

_WORD_RE = re.compile(r"^[a-z]+(?:['’-][a-z]+)*$")
_TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
_SPACE_RE = re.compile(r"\s+")
_EXCLUDED_TAGS = {
    "archaic",
    "dated",
    "historical",
    "obsolete",
    "rare",
    "reconstruction",
}
_PHRASAL_PARTICLES = {
    "about", "across", "after", "along", "around", "away", "back", "by", "down",
    "for", "forward", "in", "into", "off", "on", "out", "over", "through", "to", "up",
}


@dataclass(frozen=True)
class BuildConfig:
    word_limit: int = 10_000
    phrase_limit: int = 2_000
    min_word_zipf: float = 2.5
    min_phrase_zipf: float = 2.0
    max_senses: int = 3
    examples_per_entry: int = 3


@dataclass
class DictionaryEntry:
    canonical_key: str
    lemma: str
    entry_kind: str
    frequency_zipf: float
    frequency_rank: int = 0
    parts_of_speech: list[str] = field(default_factory=list)
    pronunciations: list[dict[str, Any]] = field(default_factory=list)
    forms: list[str] = field(default_factory=list)
    senses: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, str]] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)
    source_attribution: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SentencePair:
    english_id: str
    english: str
    chinese_id: str | None = None
    chinese: str | None = None


class RelationProvider(Protocol):
    def relations_for(self, lemma: str) -> list[dict[str, str]]: ...


def canonical_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().lower().replace("’", "'")
    return _SPACE_RE.sub(" ", normalized)


def classify_entry(lemma: str, parts_of_speech: Iterable[str]) -> str:
    tokens = lemma.split()
    if len(tokens) == 1:
        return "word"
    pos = set(parts_of_speech)
    if "verb" in pos and tokens[-1] in _PHRASAL_PARTICLES:
        return "phrasal_verb"
    if any(token in {"'s", "n't"} for token in tokens):
        return "fixed_expression"
    return "phrase"


def iter_kaikki(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid Kaikki JSON on line {line_number}") from exc
            if payload.get("lang_code") == "en" or payload.get("lang") == "English":
                yield payload


def _clean_senses(item: dict[str, Any], max_senses: int) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, sense in enumerate(item.get("senses") or []):
        tags = {str(tag).lower() for tag in sense.get("tags") or []}
        if tags & _EXCLUDED_TAGS:
            continue
        glosses = sense.get("glosses") or sense.get("raw_glosses") or []
        definition = next((str(value).strip() for value in glosses if str(value).strip()), "")
        if not definition or definition.casefold() in seen:
            continue
        seen.add(definition.casefold())
        raw_id = str(sense.get("id") or f"{item.get('word', '')}:{item.get('pos', '')}:{index}")
        sense_key = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:20]
        cleaned.append(
            {
                "sense_key": sense_key,
                "part_of_speech": str(item.get("pos") or "unknown"),
                "definition_en": definition,
                "tags": sorted(tags - {"no-gloss"}),
                "source": "kaikki-wiktionary",
            }
        )
        if len(cleaned) >= max_senses:
            break
    return cleaned


def _valid_lemma(key: str) -> bool:
    tokens = key.split()
    return bool(tokens) and len(tokens) <= 7 and all(_WORD_RE.fullmatch(token) for token in tokens)


def collect_kaikki_entries(
    items: Iterable[dict[str, Any]],
    *,
    frequency: Callable[[str], float],
    config: BuildConfig,
) -> list[DictionaryEntry]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    display_forms: dict[str, str] = {}
    for item in items:
        lemma = str(item.get("word") or "").strip()
        key = canonical_key(lemma)
        if not _valid_lemma(key):
            continue
        senses = _clean_senses(item, config.max_senses)
        if not senses:
            continue
        grouped[key].append({**item, "_clean_senses": senses})
        display_forms.setdefault(key, lemma)

    candidates: list[DictionaryEntry] = []
    for key, variants in grouped.items():
        pos = sorted({str(item.get("pos") or "unknown") for item in variants})
        kind = classify_entry(key, pos)
        zipf = float(frequency(key))
        minimum = config.min_word_zipf if kind == "word" else config.min_phrase_zipf
        if zipf < minimum:
            continue
        senses: list[dict[str, Any]] = []
        for variant in variants:
            for sense in variant["_clean_senses"]:
                if len(senses) >= config.max_senses:
                    break
                if sense["definition_en"].casefold() not in {
                    current["definition_en"].casefold() for current in senses
                }:
                    senses.append(sense)
        sounds = [
            {key: value for key, value in sound.items() if key in {"ipa", "audio", "text"}}
            for item in variants
            for sound in (item.get("sounds") or [])
            if any(sound.get(name) for name in ("ipa", "audio", "text"))
        ][:6]
        forms = sorted(
            {
                str(form.get("form"))
                for item in variants
                for form in (item.get("forms") or [])
                if form.get("form") and " " not in str(form.get("form"))
            }
        )[:12]
        candidates.append(
            DictionaryEntry(
                canonical_key=key,
                lemma=display_forms[key],
                entry_kind=kind,
                frequency_zipf=zipf,
                parts_of_speech=pos,
                pronunciations=sounds,
                forms=forms,
                senses=senses,
                source_attribution={
                    "definitions": "Kaikki/Wiktionary",
                    "kaikki_source_urls": sorted(
                        {str(item.get("source")) for item in variants if item.get("source")}
                    )[:6],
                },
            )
        )

    words = sorted(
        (entry for entry in candidates if entry.entry_kind == "word"),
        key=lambda entry: (-entry.frequency_zipf, entry.canonical_key),
    )[: config.word_limit]
    phrases = sorted(
        (entry for entry in candidates if entry.entry_kind != "word"),
        key=lambda entry: (-entry.frequency_zipf, entry.canonical_key),
    )[: config.phrase_limit]
    selected = words + phrases
    selected.sort(key=lambda entry: (-entry.frequency_zipf, entry.canonical_key))
    for rank, entry in enumerate(selected, start=1):
        entry.frequency_rank = rank
    return selected


class NltkWordNetRelations:
    """Optional adapter; the build command gives an install hint when NLTK data is absent."""

    def __init__(self) -> None:
        try:
            from nltk.corpus import wordnet

            wordnet.ensure_loaded()
        except (ImportError, LookupError) as exc:
            raise RuntimeError(
                "WordNet unavailable; install the dictionary extra and run "
                "`.venv/bin/python -m nltk.downloader wordnet`"
            ) from exc
        self.wordnet = wordnet

    def relations_for(self, lemma: str) -> list[dict[str, str]]:
        relation_terms: dict[str, set[str]] = defaultdict(set)
        synsets = self.wordnet.synsets(lemma.replace(" ", "_"))[:3]
        for synset in synsets:
            relation_terms["synonym"].update(
                name.replace("_", " ") for name in synset.lemma_names()
            )
            for member in synset.lemmas():
                relation_terms["antonym"].update(
                    antonym.name().replace("_", " ") for antonym in member.antonyms()
                )
            for relation, targets in (
                ("hypernym", synset.hypernyms()),
                ("hyponym", synset.hyponyms()),
                ("entailment", synset.entailments()),
            ):
                relation_terms[relation].update(
                    name.replace("_", " ")
                    for target in targets[:4]
                    for name in target.lemma_names()[:2]
                )
        key = canonical_key(lemma)
        return [
            {"type": relation, "target": target, "source": "wordnet-3.0"}
            for relation in sorted(relation_terms)
            for target in sorted(relation_terms[relation], key=str.casefold)[:6]
            if canonical_key(target) != key
        ]


def iter_tatoeba_pairs(path: Path) -> Iterator[SentencePair]:
    """Read Tatoeba custom pair exports: eng id/text followed by target id/text."""
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            columns = raw.rstrip("\n").split("\t")
            if len(columns) < 4:
                raise ValueError(f"invalid Tatoeba pair TSV on line {line_number}")
            yield SentencePair(columns[0], columns[1], columns[2] or None, columns[3] or None)


def attach_relations(entries: list[DictionaryEntry], provider: RelationProvider) -> None:
    for entry in entries:
        entry.relations = provider.relations_for(entry.canonical_key)
        if entry.relations:
            entry.source_attribution["relations"] = "Princeton WordNet 3.0"


def _sentence_score(sentence: str, lemma: str) -> tuple[int, int, str] | None:
    if "http://" in sentence or "https://" in sentence or len(sentence) > 180:
        return None
    tokens = [canonical_key(token) for token in _TOKEN_RE.findall(sentence)]
    if not tokens or f" {' '.join(tokens)} ".find(f" {lemma} ") < 0:
        return None
    length = len(tokens)
    if length < 4 or length > 28:
        return None
    return (abs(length - 12), len(set(tokens)) * -1, sentence.casefold())


def attach_examples(
    entries: list[DictionaryEntry],
    pairs: Iterable[SentencePair],
    *,
    examples_per_entry: int = 3,
) -> None:
    by_token: dict[str, list[DictionaryEntry]] = defaultdict(list)
    for entry in entries:
        for token in set(entry.canonical_key.split()):
            by_token[token].append(entry)
    candidates: dict[str, list[tuple[tuple[int, int, str], SentencePair]]] = defaultdict(list)
    for pair in pairs:
        sentence_tokens = set(canonical_key(token) for token in _TOKEN_RE.findall(pair.english))
        possible = {id(entry): entry for token in sentence_tokens for entry in by_token.get(token, [])}
        for entry in possible.values():
            score = _sentence_score(pair.english, entry.canonical_key)
            if score is not None:
                candidates[entry.canonical_key].append((score, pair))
    for entry in entries:
        seen: set[str] = set()
        examples: list[dict[str, Any]] = []
        for _, pair in sorted(candidates.get(entry.canonical_key, []), key=lambda item: item[0]):
            if pair.english.casefold() in seen:
                continue
            seen.add(pair.english.casefold())
            examples.append(
                {
                    "text": pair.english,
                    "translation_zh": pair.chinese,
                    "source": "tatoeba",
                    "source_id": pair.english_id,
                    "translation_source_id": pair.chinese_id,
                }
            )
            if len(examples) >= examples_per_entry:
                break
        entry.examples = examples
        if examples:
            entry.source_attribution["examples"] = "Tatoeba"


def build_dictionary(
    items: Iterable[dict[str, Any]],
    *,
    frequency: Callable[[str], float],
    config: BuildConfig = BuildConfig(),
    relation_provider: RelationProvider | None = None,
    sentence_pairs: Iterable[SentencePair] | None = None,
) -> list[DictionaryEntry]:
    entries = collect_kaikki_entries(items, frequency=frequency, config=config)
    if relation_provider is not None:
        attach_relations(entries, relation_provider)
    if sentence_pairs is not None:
        attach_examples(entries, sentence_pairs, examples_per_entry=config.examples_per_entry)
    return entries


def write_jsonl(entries: Iterable[DictionaryEntry], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
