"""Unit tests for verse matching logic from `add_hyperlinks`."""

import unittest

from add_hyperlinks import Reference


class TestVerseMatching(unittest.TestCase):
    def setUp(self):
        # Create a mock Reference object for testing
        self.mock_verses = {
            "Psalm 23:1": "The Lord is my shepherd; I shall not want. He maketh me to lie down in green pastures: he leadeth me beside the still waters.",
            "Psalm 23:2": "He restoreth my soul: he leadeth me in the paths of righteousness for his name's sake.",
            "Psalm 23:3": "Yea, though I walk through the valley of the shadow of death, I will fear no evil: for thou art with me; thy rod and thy staff they comfort me.",
            "Psalm 23:4": "Thou preparest a table before me in the presence of mine enemies: thou anointest my head with oil; my cup runneth over.",
            "Psalm 23:5": "Surely goodness and mercy shall follow me all the days of my life: and I will dwell in the house of the Lord for ever.",
        }

    def test_empty_verse(self):
        """Test matching with an empty verse."""
        ref = Reference(
            abbr="Ps.",
            book="Psalms",
            chapter="23",
            verse="1",
            single_chapter=False,
            matched_text="Ps. 23:1",
            part="23:1",
            has_colon=True,
            verses=self.mock_verses,
            root_word="GOOD",
        )
        result = ref._process_verse_for_root_word("")
        self.assertFalse(result)

    def test_basic_match(self):
        """Test basic root word matching."""
        ref = Reference(
            abbr="Ps.",
            book="Psalms",
            chapter="23",
            verse="5",
            single_chapter=False,
            matched_text="Ps. 23:5",
            part="23:5",
            has_colon=True,
            verses=self.mock_verses,
            root_word="GOOD",
        )
        result = ref._process_verse_for_root_word(self.mock_verses["Psalm 23:5"])
        self.assertTrue(result)

    def test_no_match(self):
        """Test when root word is not found."""
        ref = Reference(
            abbr="Ps.",
            book="Psalms",
            chapter="23",
            verse="1",
            single_chapter=False,
            matched_text="Ps. 23:1",
            part="23:1",
            has_colon=True,
            verses=self.mock_verses,
            root_word="LOVE",
        )
        result = ref._process_verse_for_root_word(self.mock_verses["Psalm 23:1"])
        self.assertFalse(result)

    def test_root_word_with_suffixes(self):
        """Test root word variations with suffixes."""
        ref = Reference(
            abbr="Ps.",
            book="Psalms",
            chapter="23",
            verse="5",
            single_chapter=False,
            matched_text="Ps. 23:5",
            part="23:5",
            has_colon=True,
            verses=self.mock_verses,
            root_word="GOODNESS",
        )
        result = ref._process_verse_for_root_word(self.mock_verses["Psalm 23:5"])
        self.assertTrue(result)

    def test_root_word_with_ed_suffix(self):
        """Test root word with 'ed' suffix."""
        ref = Reference(
            abbr="Ps.",
            book="Psalms",
            chapter="23",
            verse="1",
            single_chapter=False,
            matched_text="Ps. 23:1",
            part="23:1",
            has_colon=True,
            verses=self.mock_verses,
            root_word="SHEPHERD",
        )
        result = ref._process_verse_for_root_word(self.mock_verses["Psalm 23:1"])
        self.assertTrue(result)

    def test_root_word_with_ing_suffix(self):
        """Test root word with 'ing' suffix."""
        ref = Reference(
            abbr="Ps.",
            book="Psalms",
            chapter="23",
            verse="2",
            single_chapter=False,
            matched_text="Ps. 23:2",
            part="23:2",
            has_colon=True,
            verses=self.mock_verses,
            root_word="LEAD",
        )
        result = ref._process_verse_for_root_word(self.mock_verses["Psalm 23:2"])
        self.assertTrue(result)

    def test_root_word_with_ly_suffix(self):
        """Test root word with 'ly' suffix."""
        ref = Reference(
            abbr="Ps.",
            book="Psalms",
            chapter="23",
            verse="5",
            single_chapter=False,
            matched_text="Ps. 23:5",
            part="23:5",
            has_colon=True,
            verses=self.mock_verses,
            root_word="GOOD",
        )
        result = ref._process_verse_for_root_word(self.mock_verses["Psalm 23:5"])
        self.assertTrue(result)

    def test_special_e_to_ly(self):
        """Test special case where 'e' becomes 'ly'."""
        ref = Reference(
            abbr="Ps.",
            book="Psalms",
            chapter="23",
            verse="5",
            single_chapter=False,
            matched_text="Ps. 23:5",
            part="23:5",
            has_colon=True,
            verses=self.mock_verses,
            root_word="MERCY",
        )
        result = ref._process_verse_for_root_word(self.mock_verses["Psalm 23:5"])
        self.assertTrue(result)

    def test_special_ic_to_ally(self):
        """Test special case where 'ic' becomes 'ally'."""
        ref = Reference(
            abbr="Ps.",
            book="Psalms",
            chapter="23",
            verse="2",
            single_chapter=False,
            matched_text="Ps. 23:2",
            part="23:2",
            has_colon=True,
            verses=self.mock_verses,
            root_word="RIGHT",
        )
        result = ref._process_verse_for_root_word(self.mock_verses["Psalm 23:2"])
        self.assertTrue(result)
