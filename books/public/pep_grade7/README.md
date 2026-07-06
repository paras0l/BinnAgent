# PEP Grade 7 Public Textbook Pack v2

This directory is the default maintenance entry for the public Grade 7 textbook seed pack.

- `manifest.v2.json` is the aggregate entry point consumed by the validator and future seed scripts.
- `upper/` and `lower/` keep source, curriculum, and one JSON file per unit.
- `extraction_gaps.json` records source-level gaps that should not enter the default learner flow.

The legacy `books/public/pep_grade7_public_pack.v1.json` is retained as a deprecated monolithic artifact for compatibility. New edits should target this split v2 pack.

The pack intentionally stores short structured facts, short expressions, and generated checking exercises only. It must not contain full page text, long textbook passages, tapescripts, or copied exercise pages.
