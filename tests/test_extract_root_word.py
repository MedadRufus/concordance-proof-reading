"""
Unit tests for the extract_root_word function.
"""

from add_hyperlinks import extract_root_word


def test_extract_root_word_basic():
    """Test basic root word extraction."""
    text = "ADVERSITY makes us stronger | Rom. 8:28"
    result = extract_root_word(text)
    assert result == "ADVERSITY"


def test_extract_root_word_with_lowercase_after():
    """Test root word extraction when followed by lowercase."""
    text = "FAITH is important | Heb. 11:1"
    result = extract_root_word(text)
    assert result == "FAITH"


def test_extract_root_word_no_root():
    """Test when no root word is found."""
    text = "This is just regular text without a root word."
    result = extract_root_word(text)
    assert result is None


def test_extract_root_word_fallback():
    """Test fallback behavior for all caps word."""
    text = "GRACE comes from God | Eph. 2:8"
    result = extract_root_word(text)
    assert result == "GRACE"


def test_extract_root_word_with_punctuation():
    """Test root word extraction with punctuation."""
    text = "PEACE, joy, and love | Gal. 5:22"
    result = extract_root_word(text)
    assert result == "PEACE"
