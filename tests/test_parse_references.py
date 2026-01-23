import os
import re
import sys

import pytest

# Ensure project root is on sys.path so tests can import top-level modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from add_hyperlinks import parse_references, ref_pattern, replace_reference


def test_missing_space_after_period_no_match():
    s = "Lk.18:3"
    parsed = parse_references(s)
    assert parsed == []
    assert ref_pattern.search(s) is None


def test_space_after_period_matches():
    s = "Lk. 18:3"
    parsed = parse_references(s)
    assert len(parsed) == 1
    ref = parsed[0]
    assert ref.book == "Luke"
    assert ref.chapter == "18"
    assert ref.verse == "3"


def test_semicolon_between_refs():
    s = "Lk. 14:11; 18:14"
    parsed = parse_references(s)
    # semicolon prevents the second ref from being parsed in the same match
    assert len(parsed) == 1
    assert parsed[0].chapter == "14"
    assert parsed[0].verse == "11"

    # Replacement should produce one anchor and leave the second ref plaintext
    replaced = ref_pattern.sub(replace_reference, s)
    assert replaced.count("<a ") == 1
    assert "18:14" in replaced


def test_in_christ_space_after_comma():
    s_bad = "a., in Christ,1 Cor.15:8|"
    assert parse_references(s_bad) == []

    s_good = "a., in Christ, 1 Cor. 15:8|"
    parsed = parse_references(s_good)
    assert len(parsed) == 1
    ref = parsed[0]
    assert ref.book == "1 Corinthians"
    assert ref.chapter == "15"
    assert ref.verse == "8"


def test_deu_period_vs_colon():
    bad = "Deu. 16.19"
    assert parse_references(bad) == []

    good = "Deu. 16:19"
    parsed = parse_references(good)
    assert len(parsed) == 1
    assert parsed[0].book == "Deuteronomy"
    assert parsed[0].chapter == "16"
    assert parsed[0].verse == "19"


def test_deu_missing_period():
    s = "Deu 32:35"
    assert parse_references(s) == []


def test_phm_single_chapter_and_explicit():
    s_shorthand = "Philem. 9"
    parsed = parse_references(s_shorthand)
    assert len(parsed) == 1
    ref = parsed[0]
    assert ref.book == "Philemon"
    assert ref.chapter == "1"
    assert ref.verse == "9"

    s_explicit = "Philem. 1:9"
    parsed2 = parse_references(s_explicit)
    # Single-chapter books should NOT accept an explicit chapter (e.g., '1:9') — treat as malformed
    assert parsed2 == []


def test_commas_between_refs_same_book():
    s = "Ps. 15:1, 61:4"
    parsed = parse_references(s)
    assert len(parsed) == 2
    assert parsed[0].book == "Psalms"
    assert parsed[0].chapter == "15"
    assert parsed[0].verse == "1"
    assert parsed[1].book == "Psalms"
    assert parsed[1].chapter == "61"
    assert parsed[1].verse == "4"

    replaced = ref_pattern.sub(replace_reference, s)
    assert replaced.count("<a ") == 2


def test_semicolon_separates_books_and_multiple_parts():
    s = "Lev. 7:21, 11:43, 18:30, 19:7, 20:25; Deu. 14:3"
    parsed = parse_references(s)
    assert len(parsed) == 6
    assert all(r.book == "Leviticus" for r in parsed[:5])
    assert parsed[5].book == "Deuteronomy"
    replaced = ref_pattern.sub(replace_reference, s)
    assert replaced.count("<a ") == 6


def test_same_chapter_multiple_verses():
    s = "Job 30:16,21"
    parsed = parse_references(s)
    assert len(parsed) == 2
    assert parsed[0].book == "Job"
    assert parsed[0].chapter == "30"
    assert parsed[0].verse == "16"
    assert parsed[1].chapter == "30"
    assert parsed[1].verse == "21"
    replaced = ref_pattern.sub(replace_reference, s)
    assert replaced.count("<a ") == 2
