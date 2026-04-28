"""Self-check validators for generated artifacts.

Each validator returns a `ValidationReport` with:
    - ok: bool — passed or not
    - missing: list of items the artifact failed to cover
    - feedback: human-readable hint to feed back to the LLM for a retry

The pipeline calls these after each step and, if `ok=False`, re-prompts the
LLM with the feedback to patch the output. Up to 2 retries by default.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# === Regexes ===

_BT_ID = re.compile(r"\bБТ[-‑]?(\d{1,3})\b", re.UNICODE)
_UC_ID = re.compile(r"\bUC[-‑]?(\d{1,3})\b", re.UNICODE)
_NFR_ID = re.compile(r"\bНФТ[-‑]?(\d{1,3})\b", re.UNICODE)
_FR_ID = re.compile(r"\bФТ[-‑]?(\d{1,3})\b", re.UNICODE)

# Match BT row in markdown table: "| БТ-04 | Текст | Обязательное |"
# Capture id and obligation flag.
_BT_TABLE_ROW = re.compile(
    r"\|\s*БТ[-‑]?(\d{1,3})\s*\|[^|]+\|\s*(Обязательное|Опциональное|Optional|Required|Mandatory)",
    re.IGNORECASE | re.UNICODE,
)

_IMPLEMENTS_TAG = re.compile(r"@implements\s+ФТ[-‑]?(\d{1,3})", re.UNICODE)


# === Reports ===

@dataclass
class ValidationReport:
    ok: bool
    missing: list[str] = field(default_factory=list)
    extra_info: dict = field(default_factory=dict)

    @property
    def feedback(self) -> str:
        """Human-readable hint for the LLM to use as retry context."""
        if self.ok:
            return ""
        items = ", ".join(self.missing)
        return f"Не покрыто: {items}. Добавь их и верни обновлённый файл целиком."


# === Helpers ===

def extract_bt_ids(text: str) -> set[str]:
    return {f"БТ-{m.group(1).zfill(2)}" for m in _BT_ID.finditer(text)}


def extract_uc_ids(text: str) -> set[str]:
    return {f"UC-{m.group(1).zfill(2)}" for m in _UC_ID.finditer(text)}


def extract_fr_ids(text: str) -> set[str]:
    return {f"ФТ-{m.group(1).zfill(2)}" for m in _FR_ID.finditer(text)}


def extract_implements(code_files: dict[str, str]) -> set[str]:
    """Extract all @implements ФТ-XX tags from generated source files."""
    found: set[str] = set()
    for content in code_files.values():
        for m in _IMPLEMENTS_TAG.finditer(content):
            found.add(f"ФТ-{m.group(1).zfill(2)}")
    return found


def extract_required_bt(business_requirements: str) -> set[str]:
    """Extract ID of *required* (Обязательное) БТ from the input table."""
    required: set[str] = set()
    for m in _BT_TABLE_ROW.finditer(business_requirements):
        bt_id, obligation = m.group(1), m.group(2).lower()
        if obligation in ("обязательное", "required", "mandatory"):
            required.add(f"БТ-{bt_id.zfill(2)}")
    # Fallback: if the table couldn't be parsed (e.g. different format),
    # treat every БТ-XX present as required to be permissive.
    if not required:
        return extract_bt_ids(business_requirements)
    return required


# === Validators ===

def validate_use_cases(use_cases_md: str, business_requirements: str) -> ValidationReport:
    """Every required БТ must be referenced from at least one UC source field."""
    required = extract_required_bt(business_requirements)
    referenced = extract_bt_ids(use_cases_md)
    missing = sorted(required - referenced, key=_id_sort_key)
    return ValidationReport(ok=not missing, missing=missing,
                            extra_info={"required": sorted(required), "referenced": sorted(referenced)})


def validate_fr(fr_md: str, business_requirements: str) -> ValidationReport:
    """Every required БТ must be referenced from at least one ФТ source field."""
    required = extract_required_bt(business_requirements)
    referenced = extract_bt_ids(fr_md)
    missing = sorted(required - referenced, key=_id_sort_key)
    return ValidationReport(ok=not missing, missing=missing,
                            extra_info={"required": sorted(required), "referenced": sorted(referenced)})


def validate_code(code_files: dict[str, str], fr_md: str) -> ValidationReport:
    """Every ФТ must appear as @implements somewhere in the source."""
    declared = extract_fr_ids(fr_md)
    implemented = extract_implements(code_files)
    missing = sorted(declared - implemented, key=_id_sort_key)
    return ValidationReport(ok=not missing, missing=missing,
                            extra_info={"declared": sorted(declared), "implemented": sorted(implemented)})


def _id_sort_key(s: str) -> tuple[str, int]:
    """Sort IDs like БТ-02 numerically: ('БТ', 2)."""
    parts = s.split("-", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return (parts[0], int(parts[1]))
    return (s, 0)
