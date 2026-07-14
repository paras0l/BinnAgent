#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import bz2
import hashlib
import json
import sys
import tarfile
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

    tatoeba = commands.add_parser(
        "prepare-tatoeba",
        help="Join official English/Chinese sentence and link exports into pair TSV.",
    )
    tatoeba.add_argument("--english", type=Path, required=True)
    tatoeba.add_argument("--chinese", type=Path, required=True)
    tatoeba.add_argument("--links", type=Path, required=True)
    tatoeba.add_argument("--output", type=Path, required=True)
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


def _read_tatoeba_sentences(path: Path) -> dict[str, str]:
    sentences: dict[str, str] = {}
    with bz2.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            columns = line.rstrip("\n").split("\t", 2)
            if len(columns) == 3:
                sentences[columns[0]] = columns[2].replace("\t", " ")
    return sentences


def prepare_tatoeba_pairs(args: argparse.Namespace) -> None:
    english = _read_tatoeba_sentences(args.english)
    chinese = _read_tatoeba_sentences(args.chinese)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pair_count = 0
    with (
        tarfile.open(args.links, "r:bz2") as archive,
        args.output.open("w", encoding="utf-8") as output,
    ):
        member = archive.extractfile("links.csv")
        if member is None:
            raise ValueError("Tatoeba links archive does not contain links.csv")
        for raw_line in member:
            columns = raw_line.decode("utf-8").rstrip("\n").split("\t", 1)
            if len(columns) != 2:
                continue
            left, right = columns
            if left in english and right in chinese:
                english_id, chinese_id = left, right
            elif right in english and left in chinese:
                english_id, chinese_id = right, left
            else:
                continue
            output.write(
                f"{english_id}\t{english[english_id]}\t"
                f"{chinese_id}\t{chinese[chinese_id]}\n"
            )
            pair_count += 1
    print(json.dumps({"output": str(args.output), "pairs": pair_count}, ensure_ascii=False))


def run_build(args: argparse.Namespace) -> None:
    try:
        from wordfreq import top_n_list, zipf_frequency
    except ImportError as exc:
        raise RuntimeError("Install build dependencies with `pip install -e '.[dictionary]'`") from exc
    config = BuildConfig(word_limit=args.word_limit, phrase_limit=args.phrase_limit)
    allowed_word_keys = set(
        top_n_list("en", max(args.word_limit * 4, 40_000), wordlist="best")
    )
    relation_provider = None if args.skip_wordnet else NltkWordNetRelations()
    pairs = iter_tatoeba_pairs(args.tatoeba) if args.tatoeba else None
    entries = build_dictionary(
        iter_kaikki(args.kaikki),
        frequency=lambda term: zipf_frequency(term, "en", wordlist="best"),
        config=config,
        relation_provider=relation_provider,
        sentence_pairs=pairs,
        allowed_word_keys=allowed_word_keys,
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
    failed_entries: list[str] = []
    async with async_session_factory() as db:
        entries = await untranslated_entries(db, limit=args.limit)
        executor = PromptExecutor(db=db, model_router=router)
        for start in range(0, len(entries), args.batch_size):
            batch = entries[start : start + args.batch_size]
            try:
                total += await translate_entry_batch(db, entries=batch, executor=executor)
            except RuntimeError:
                await db.commit()
                for entry in batch:
                    try:
                        total += await translate_entry_batch(
                            db,
                            entries=[entry],
                            executor=executor,
                        )
                    except RuntimeError:
                        await db.commit()
                        failed_entries.append(entry.canonical_key)
            print(f"translated {min(start + len(batch), len(entries))}/{len(entries)} entries")
    await router.close()
    print(
        json.dumps(
            {
                "translated_senses": total,
                "failed_entries": failed_entries,
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    args = parse_args()
    if args.command == "prepare-tatoeba":
        prepare_tatoeba_pairs(args)
    elif args.command == "build":
        run_build(args)
    elif args.command == "load":
        asyncio.run(run_load(args))
    else:
        asyncio.run(run_translate(args))


if __name__ == "__main__":
    main()
