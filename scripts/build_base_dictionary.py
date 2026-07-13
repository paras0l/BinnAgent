#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.base_dictionary.pipeline import (  # noqa: E402
    BuildConfig,
    NltkWordNetRelations,
    build_dictionary,
    iter_kaikki,
    iter_tatoeba_pairs,
    write_jsonl,
)
from src.base_dictionary.store import publish_entries  # noqa: E402
from src.base_dictionary.translation import (  # noqa: E402
    translate_entry_batch,
    untranslated_entries,
)
from src.db import async_session_factory  # noqa: E402
from src.prompts import PromptExecutor  # noqa: E402
from src.providers.router import router  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and publish the shared base dictionary.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Create deterministic staged JSONL.")
    build.add_argument("--kaikki", type=Path, required=True)
    build.add_argument("--tatoeba", type=Path)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--word-limit", type=int, default=10_000)
    build.add_argument("--phrase-limit", type=int, default=2_000)
    build.add_argument("--skip-wordnet", action="store_true")

    load = commands.add_parser("load", help="Publish staged JSONL to PostgreSQL.")
    load.add_argument("--input", type=Path, required=True)
    load.add_argument("--version", required=True)
    load.add_argument("--kaikki-version", required=True)
    load.add_argument("--tatoeba-version")

    translate = commands.add_parser("translate-zh", help="Generate missing Chinese definitions.")
    translate.add_argument("--limit", type=int, default=100, choices=range(1, 1001))
    translate.add_argument("--batch-size", type=int, default=12, choices=range(1, 21))
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def run_build(args: argparse.Namespace) -> None:
    try:
        from wordfreq import zipf_frequency
    except ImportError as exc:
        raise RuntimeError("Install build dependencies with `pip install -e '.[dictionary]'`") from exc
    config = BuildConfig(word_limit=args.word_limit, phrase_limit=args.phrase_limit)
    relation_provider = None if args.skip_wordnet else NltkWordNetRelations()
    pairs = iter_tatoeba_pairs(args.tatoeba) if args.tatoeba else None
    entries = build_dictionary(
        iter_kaikki(args.kaikki),
        frequency=lambda term: zipf_frequency(term, "en", wordlist="best"),
        config=config,
        relation_provider=relation_provider,
        sentence_pairs=pairs,
    )
    write_jsonl(entries, args.output)
    print(json.dumps({"output": str(args.output), "entries": len(entries)}, ensure_ascii=False))


async def run_load(args: argparse.Namespace) -> None:
    entries = _read_jsonl(args.input)
    source_manifest = {
        "kaikki_wiktionary": {"version": args.kaikki_version},
        "wordnet": {"version": "3.0"},
        "wordfreq": {"version": "runtime"},
        "staged_sha256": _sha256(args.input),
    }
    if args.tatoeba_version:
        source_manifest["tatoeba"] = {"version": args.tatoeba_version}
    config = {
        "word_limit": sum(entry["entry_kind"] == "word" for entry in entries),
        "phrase_limit": sum(entry["entry_kind"] != "word" for entry in entries),
        "max_senses": 3,
    }
    async with async_session_factory() as db:
        build = await publish_entries(
            db,
            version=args.version,
            entries=entries,
            source_manifest=source_manifest,
            selection_config=config,
        )
        print(json.dumps(build.statistics, ensure_ascii=False))


async def run_translate(args: argparse.Namespace) -> None:
    total = 0
    async with async_session_factory() as db:
        entries = await untranslated_entries(db, limit=args.limit)
        executor = PromptExecutor(db=db, model_router=router)
        for start in range(0, len(entries), args.batch_size):
            batch = entries[start : start + args.batch_size]
            total += await translate_entry_batch(db, entries=batch, executor=executor)
            print(f"translated {min(start + len(batch), len(entries))}/{len(entries)} entries")
    await router.close()
    print(json.dumps({"translated_senses": total}, ensure_ascii=False))


def main() -> None:
    args = parse_args()
    if args.command == "build":
        run_build(args)
    elif args.command == "load":
        asyncio.run(run_load(args))
    else:
        asyncio.run(run_translate(args))


if __name__ == "__main__":
    main()
