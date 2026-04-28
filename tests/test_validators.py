"""Unit tests for self-check validators."""
from __future__ import annotations

from generator.validators import (
    extract_bt_ids,
    extract_fr_ids,
    extract_implements,
    extract_required_bt,
    validate_code,
    validate_fr,
    validate_use_cases,
)


# ---------- extractors ----------

def test_extract_bt_ids_handles_dash_variants():
    text = "**Источник:** БТ-01, БТ‑02, БТ-3"  # mixed dashes, single digit
    assert extract_bt_ids(text) == {"БТ-01", "БТ-02", "БТ-03"}


def test_extract_fr_ids():
    text = "ФТ-01 ссылается на ФТ-02 и ФТ-12."
    assert extract_fr_ids(text) == {"ФТ-01", "ФТ-02", "ФТ-12"}


def test_extract_implements_finds_jsdoc_tags():
    code_files = {
        "src/calc.js": "/** @implements ФТ-01\n * @implements ФТ-04 */\nexport function add() {}",
        "src/history.js": "// @implements ФТ-08",
    }
    assert extract_implements(code_files) == {"ФТ-01", "ФТ-04", "ФТ-08"}


def test_extract_required_bt_from_table():
    bt = """
| ID | Требование | Обязательность |
|----|-----------|---------------|
| БТ-01 | A | Обязательное |
| БТ-02 | B | Опциональное |
| БТ-03 | C | Обязательное |
"""
    assert extract_required_bt(bt) == {"БТ-01", "БТ-03"}


def test_extract_required_bt_falls_back_when_table_missing():
    bt = "Просто список: БТ-05 и БТ-06."
    # No proper markdown table — fallback to all БТ found
    assert extract_required_bt(bt) == {"БТ-05", "БТ-06"}


def test_extract_required_bt_handles_english_obligation():
    bt = """
| ID | Req | Status |
|----|-----|--------|
| БТ-01 | A | Required |
| БТ-02 | B | Optional |
"""
    assert extract_required_bt(bt) == {"БТ-01"}


# ---------- validators ----------

BT_TABLE = """
| ID | Требование | Обязательность |
|----|-----------|---------------|
| БТ-01 | a | Обязательное |
| БТ-02 | b | Обязательное |
| БТ-03 | c | Опциональное |
"""


def test_validate_use_cases_passes_when_all_required_covered():
    uc = """
### UC-01: ...
**Источник:** БТ-01

### UC-02: ...
**Источник:** БТ-02
"""
    report = validate_use_cases(uc, BT_TABLE)
    assert report.ok
    assert report.missing == []


def test_validate_use_cases_fails_when_required_missing():
    uc = """
### UC-01: ...
**Источник:** БТ-01
"""
    report = validate_use_cases(uc, BT_TABLE)
    assert not report.ok
    assert report.missing == ["БТ-02"]
    assert "БТ-02" in report.feedback


def test_validate_fr_lists_all_missing_required_bt():
    fr = """
### ФТ-01: ...
**Источник:** БТ-01
"""
    report = validate_fr(fr, BT_TABLE)
    assert not report.ok
    assert "БТ-02" in report.missing
    # Optional БТ-03 should NOT be flagged
    assert "БТ-03" not in report.missing


def test_validate_code_passes_when_all_fr_implemented():
    fr = """
### ФТ-01: A
### ФТ-02: B
"""
    code = {
        "src/a.js": "/** @implements ФТ-01 */",
        "src/b.js": "/** @implements ФТ-02 */",
    }
    report = validate_code(code, fr)
    assert report.ok


def test_validate_code_lists_unimplemented_fr():
    fr = """
### ФТ-01: A
### ФТ-02: B
### ФТ-03: C
"""
    code = {"src/a.js": "/** @implements ФТ-01 */"}
    report = validate_code(code, fr)
    assert not report.ok
    assert set(report.missing) == {"ФТ-02", "ФТ-03"}


def test_validate_code_sorts_missing_numerically():
    fr = "ФТ-01 ФТ-02 ФТ-10 ФТ-11"
    code: dict[str, str] = {}
    report = validate_code(code, fr)
    # Should sort 01, 02, 10, 11 — not lexicographically (which would put 10 before 02)
    assert report.missing == ["ФТ-01", "ФТ-02", "ФТ-10", "ФТ-11"]


def test_feedback_contains_human_readable_hint():
    fr = "### ФТ-01\n**Источник:** БТ-01"
    report = validate_fr(fr, BT_TABLE)
    assert "БТ-02" in report.feedback
    assert "Не покрыто" in report.feedback
