#!/usr/bin/env python3
"""Unit tests for the root word matching functionality using pytest."""

import os
import sys

import pytest

from add_hyperlinks import Reference


@pytest.fixture
def sample_reference():
    """Create a sample Reference object for testing."""
    return Reference(
        abbr="Gen.",
        book="Genesis",
        chapter=1,
        verse=1,
        single_chapter=False,
        matched_text="Gen. 1:1",
        part="1:1",
        has_colon=True,
        verses={},
        root_word="GOD",
    )


def test_basic_root_word_match(sample_reference):
    """Test basic root word matching."""
    clean_verse = "In the beginning God created the heavens"
    root_word = "GOD"

    bolded_verse, matched_any = sample_reference.find_root_word_matches(clean_verse, root_word)

    assert matched_any is True
    assert bolded_verse == "In the beginning <strong>God</strong> created the heavens"


def test_no_root_word_match(sample_reference):
    """Test case where no root word is found."""
    clean_verse = "In the beginning the heavens were created"
    root_word = "GOD"

    bolded_verse, matched_any = sample_reference.find_root_word_matches(clean_verse, root_word)

    assert matched_any is False
    assert bolded_verse is None


def test_plural_form_match(sample_reference):
    """Test matching plural forms of root word."""
    clean_verse = "The gods were mentioned in the text"
    root_word = "GOD"

    bolded_verse, matched_any = sample_reference.find_root_word_matches(clean_verse, root_word)

    assert matched_any is True
    assert bolded_verse == "The <strong>gods</strong> were mentioned in the text"


def test_past_tense_match(sample_reference):
    """Test matching past tense forms of root word."""
    clean_verse = "He godded the situation"
    root_word = "GOD"

    bolded_verse, matched_any = sample_reference.find_root_word_matches(clean_verse, root_word)

    assert matched_any is True
    assert bolded_verse == "He <strong>godded</strong> the situation"


def test_ly_variation_match(sample_reference):
    """Test matching with 'ly' variation."""
    clean_verse = "It was godly"
    root_word = "GOD"

    bolded_verse, matched_any = sample_reference.find_root_word_matches(clean_verse, root_word)

    assert matched_any is True
    assert bolded_verse == "It was <strong>godly</strong>"


def test_y_to_ily_variation_match():
    """Test matching with 'y' to 'ily' variation using a different root."""
    ref = Reference(
        abbr="Gen.",
        book="Genesis",
        chapter=1,
        verse=1,
        single_chapter=False,
        matched_text="Gen. 1:1",
        part="1:1",
        has_colon=True,
        verses={},
        root_word="EARTH",
    )

    clean_verse = "It was earthly"
    root_word = "EARTH"

    bolded_verse, matched_any = ref.find_root_word_matches(clean_verse, root_word)

    assert matched_any is True
    assert bolded_verse == "It was <strong>earthly</strong>"


def test_multiple_matches_in_verse(sample_reference):
    """Test matching multiple occurrences of the root word."""
    clean_verse = "God is great and God is good"
    root_word = "GOD"

    bolded_verse, matched_any = sample_reference.find_root_word_matches(clean_verse, root_word)

    assert matched_any is True
    assert bolded_verse == "<strong>God</strong> is great and <strong>God</strong> is good"


def test_case_insensitive_match(sample_reference):
    """Test that matching is case insensitive."""
    clean_verse = "In the beginning GOD created and godliness followed"
    root_word = "GOD"

    bolded_verse, matched_any = sample_reference.find_root_word_matches(clean_verse, root_word)

    assert matched_any is True
    assert "<strong>GOD</strong>" in bolded_verse
    assert "<strong>godliness</strong>" in bolded_verse
