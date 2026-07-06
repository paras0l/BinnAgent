# Textbook Parser Golden Datasets

Golden datasets are small, structured parser regression fixtures. They are not full textbook copies and must not include long page text.

Each profile lives in `books/golden/{profile_id}/`:

```text
manifest.json
units.expected.json
vocabulary.expected.json
grammar.expected.json
phrases.expected.json
exercises.expected.json
```

`manifest.json` fields:

- `profile_id`: stable golden profile id.
- `book_title`: human-readable book name.
- `parser_profile_id`: parser profile from `src/knowledge/parser_profiles.py`.
- `source_fixture`: PDF or JSON fixture path, relative to the repository root or the profile directory.
- `version`: expected data version.
- `notes`: maintenance notes.

Expected file schemas:

- `units.expected.json`: `unit_id`, `title`, `order`, `expected_source_pages`.
- `vocabulary.expected.json`: `text`, `normalized_text`, `unit_id`, `part_of_speech`, `chinese_meaning`, `source_page`, `is_core`.
- `grammar.expected.json`: `topic`, `unit_id`, `source_page`, `keywords`.
- `phrases.expected.json`: `text`, `normalized_text`, `unit_id`, `source_page`.
- `exercises.expected.json`: `question_key`, `unit_id`, `source_page`, `answer_required`, `knowledge_refs`.

Current profiles:

- No checked-in textbook-specific golden profile is active. Add a small profile only after reviewing that it does not reintroduce textbook-specific fallback behavior.

How to add a profile:

1. Create a new directory under `books/golden/`.
2. Add `manifest.json` and the five expected files, even if some are `[]`.
3. Keep samples small and reviewable.
4. Use normalized text that matches parser output after lowercasing, whitespace normalization, and punctuation folding.
5. Run:

```bash
python scripts/evaluate_textbook_parser.py --profile {profile_id} --json
```

Baselines live in `var/parser_eval/baselines/`. Do not update a baseline to hide a regression; update it only after reviewing an intentional parser behavior change.
