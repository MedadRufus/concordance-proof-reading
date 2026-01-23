"""Unit tests for reference parsing and replacement from `add_hyperlinks`."""

import os
import sys

# Ensure project root is on sys.path so tests can import top-level modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import after adjusting sys.path
from add_hyperlinks import (  # pylint: disable=wrong-import-position
    parse_references,
    ref_pattern,
    replace_reference,
)


def test_missing_space_after_period_no_match():
    """Missing space after period should not match."""
    s = "Lk.18:3"
    parsed = parse_references(s, {})
    assert not parsed
    assert ref_pattern.search(s) is None


def test_space_after_period_matches():
    """Space after period should match correctly."""
    s = "Lk. 18:3"
    parsed = parse_references(s, {})
    assert len(parsed) == 1
    ref = parsed[0]
    assert ref.book == "Luke"
    assert ref.chapter == "18"
    assert ref.verse == "3"


def test_semicolon_between_refs():
    """Semicolons separate references across matches."""
    s = "Lk. 14:11; 18:14"
    parsed = parse_references(s, {})
    # semicolon prevents the second ref from being parsed in the same match
    assert len(parsed) == 1
    assert parsed[0].chapter == "14"
    assert parsed[0].verse == "11"

    # Replacement should produce one anchor and leave the second ref plaintext
    def replacer(m):
        return replace_reference(m, {})

    replaced = ref_pattern.sub(replacer, s)
    assert replaced.count("<a ") == 1
    assert "18:14" in replaced


def test_in_christ_space_after_comma():
    """Comma spacing can affect parsing near clause punctuation."""
    s_bad = "a., in Christ,1 Cor.15:8|"
    assert not parse_references(s_bad, {})

    s_good = "a., in Christ, 1 Cor. 15:8|"
    parsed = parse_references(s_good, {})
    assert len(parsed) == 1
    ref = parsed[0]
    assert ref.book == "1 Corinthians"
    assert ref.chapter == "15"
    assert ref.verse == "8"


def test_deu_period_vs_colon():
    """Periods vs colons in chapter/verse should behave correctly."""
    bad = "Deu. 16.19"
    assert not parse_references(bad, {})

    good = "Deu. 16:19"
    parsed = parse_references(good, {})
    assert len(parsed) == 1
    assert parsed[0].book == "Deuteronomy"
    assert parsed[0].chapter == "16"
    assert parsed[0].verse == "19"


def test_deu_missing_period():
    """Missing period after book abbreviation must not match."""
    s = "Deu 32:35"
    assert not parse_references(s, {})


def test_phm_single_chapter_and_explicit():
    """Single-chapter books should parse shorthand and reject explicit chapter."""
    s_shorthand = "Philem. 9"
    parsed = parse_references(s_shorthand, {})
    assert len(parsed) == 1
    ref = parsed[0]
    assert ref.book == "Philemon"
    assert ref.chapter == "1"
    assert ref.verse == "9"

    s_explicit = "Philem. 1:9"
    parsed2 = parse_references(s_explicit, {})
    # Single-chapter books should NOT accept an explicit chapter (e.g., '1:9') — treat as malformed
    assert not parsed2


def test_commas_between_refs_same_book():
    """Commas connect multiple refs in the same book across chapters."""
    s = "Ps. 15:1, 61:4"
    parsed = parse_references(s, {})
    assert len(parsed) == 2
    assert parsed[0].book == "Psalms"
    assert parsed[0].chapter == "15"
    assert parsed[0].verse == "1"
    assert parsed[1].book == "Psalms"
    assert parsed[1].chapter == "61"
    assert parsed[1].verse == "4"

    def replacer(m):
        return replace_reference(m, {})

    replaced = ref_pattern.sub(replacer, s)
    assert replaced.count("<a ") == 2


def test_semicolon_separates_books_and_multiple_parts():
    """Semicolon boundaries split references between different books."""
    s = "Lev. 7:21, 11:43, 18:30, 19:7, 20:25; Deu. 14:3"
    parsed = parse_references(s, {})
    assert len(parsed) == 6
    assert all(r.book == "Leviticus" for r in parsed[:5])
    assert parsed[5].book == "Deuteronomy"

    def replacer(m):
        return replace_reference(m, {})

    replaced = ref_pattern.sub(replacer, s)
    assert replaced.count("<a ") == 6


def test_same_chapter_multiple_verses():
    """Multiple verses in the same chapter should be split into separate references."""
    s = "Job 30:16,21"
    parsed = parse_references(s, {})
    assert len(parsed) == 2
    assert parsed[0].book == "Job"
    assert parsed[0].chapter == "30"
    assert parsed[0].verse == "16"
    assert parsed[1].chapter == "30"
    assert parsed[1].verse == "21"

    def replacer(m):
        return replace_reference(m, {})

    replaced = ref_pattern.sub(replacer, s)
    assert replaced.count("<a ") == 2


def test_angel_of_the_lord_case():
    """
    Complex multi-book, multi-verse parsing example from the concordance. This is one hard test
    case. There are multiple chapter:verse pairs for a single book, also multiple verses for single
    chapter in a row.
    """
    s = (
        "ANGEL OF THE LORD Gen. 16:7, 22:11,15; "
        "Num. 22:23, 25:27; Judg. 5:23, 6:11,21, 13:3,20,21; "
        "2 Sam. 24:16; 2 Ki. 19:35; 1 Chr. 21:12,15,30; Ps. 34:7, 35:5,6; Is. 37:36; "
        "Zech. 1:12, 3:5,6, 12:8|"
    )
    parsed = parse_references(s, {})
    # Total number of individual references expected for this case
    assert len(parsed) == 24

    expected = [
        ("Genesis", "16", "7"),
        ("Genesis", "22", "11"),
        ("Genesis", "22", "15"),
        ("Numbers", "22", "23"),
        ("Numbers", "25", "27"),
        ("Judges", "5", "23"),
        ("Judges", "6", "11"),
        ("Judges", "6", "21"),
        ("Judges", "13", "3"),
        ("Judges", "13", "20"),
        ("Judges", "13", "21"),
        ("2 Samuel", "24", "16"),
        ("2 Kings", "19", "35"),
        ("1 Chronicles", "21", "12"),
        ("1 Chronicles", "21", "15"),
        ("1 Chronicles", "21", "30"),
        ("Psalms", "34", "7"),
        ("Psalms", "35", "5"),
        ("Psalms", "35", "6"),
        ("Isaiah", "37", "36"),
        ("Zechariah", "1", "12"),
        ("Zechariah", "3", "5"),
        ("Zechariah", "3", "6"),
        ("Zechariah", "12", "8"),
    ]

    for idx, (exp_book, exp_ch, exp_v) in enumerate(expected):
        r = parsed[idx]
        msg = (
            f"Mismatch at index {idx}: got ({r.book}, {r.chapter}, {r.verse}), "
            f"expected ({exp_book}, {exp_ch}, {exp_v})"
        )
        assert r.book == exp_book and r.chapter == exp_ch and r.verse == exp_v, msg

    # Replacement should produce one anchor per reference (24)
    def replacer(m):
        return replace_reference(m, {})

    replaced = ref_pattern.sub(replacer, s)
    assert replaced.count("<a ") == 24
