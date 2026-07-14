import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


EGP_SOURCE_URL = "https://englishprofile.org/?menu=egp-online"
EGP_CITATION = (
    "O’Keeffe, A. and Mark, G. (2017). The English Grammar Profile of learner "
    "competence: Methodology and key findings. International Journal of Corpus "
    "Linguistics, 22(4), 457–489."
)
EGP_ACKNOWLEDGEMENT = (
    "This publication/presentation/research report has made use of the English "
    "Grammar Profile. This resource is "
    "based on extensive research using the Cambridge Learner Corpus and is part "
    "of the English Profile programme, which aims to provide evidence about "
    "language use that helps to produce better language teaching materials. "
    "See https://englishprofile.org/ for more information."
)
CATALOG_VERSION = "egp-1211-v1"
EXPECTED_ENTRY_COUNT = 1211
_CEFR_EXAMPLE_RE = re.compile(r"\b(?:A1|A2|B1|B2|C1|C2)\b")


@dataclass(frozen=True)
class EGPCatalogEntry:
    external_id: int
    super_category: str
    sub_category: str
    cefr_level: str
    lexical_range: str | None
    guideword: str | None
    can_do_statement: str
    examples: list[str]
    construct_type: str


@dataclass(frozen=True)
class EGPCatalog:
    entries: list[EGPCatalogEntry]
    source_sha256: str
    source_row_count: int
    rows_with_examples: int
    exclusion_count: int


def load_egp_catalog(path: Path, *, expected_count: int = EXPECTED_ENTRY_COUNT) -> EGPCatalog:
    raw = path.read_bytes()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "#",
        "SuperCategory",
        "SubCategory",
        "Level",
        "Lexical Range",
        "guideword",
        "Can-do statement",
        "Example",
        "type",
    }
    missing = required.difference(rows[0] if rows else {})
    if missing:
        raise ValueError(f"EGP export is missing columns: {', '.join(sorted(missing))}")

    with_examples = [row for row in rows if row["Example"].strip()]
    selected = [
        row
        for row in with_examples
        if row["Can-do statement"].strip() and _CEFR_EXAMPLE_RE.search(row["Example"])
    ]
    if len(selected) != expected_count:
        raise ValueError(
            f"Expected {expected_count} EGP entries with CEFR learner examples, "
            f"found {len(selected)} from {len(rows)} rows"
        )

    entries = [
        EGPCatalogEntry(
            external_id=int(row["#"]),
            super_category=row["SuperCategory"].strip(),
            sub_category=row["SubCategory"].strip(),
            cefr_level=row["Level"].strip(),
            lexical_range=row["Lexical Range"].strip() or None,
            guideword=row["guideword"].strip() or None,
            can_do_statement=row["Can-do statement"].strip(),
            examples=[part.strip() for part in re.split(r"\n\s*\n", row["Example"]) if part.strip()],
            construct_type=row["type"].strip().replace("FORM & USE", "FORM/USE"),
        )
        for row in selected
    ]
    external_ids = [entry.external_id for entry in entries]
    if len(external_ids) != len(set(external_ids)):
        raise ValueError("EGP export contains duplicate external IDs")
    return EGPCatalog(
        entries=entries,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        source_row_count=len(rows),
        rows_with_examples=len(with_examples),
        exclusion_count=len(rows) - len(selected),
    )
