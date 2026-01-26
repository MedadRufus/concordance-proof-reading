"""Utilities to convert ODT text references to HTML anchors linking to the KJV.

This module provides helpers to parse Bible references and produce
HTML anchors that link to BibleGateway with KJV verse tooltips,
including validation that the root word (e.g., ABHOR) appears in the verse.
"""

import argparse
import html
import io
import json
import os
import re

from odf import teletype
from odf.opendocument import load
from odf.text import P

KJV_JSON_PATH = "kjv/json/verses-1769.json"

# Bible book abbreviation mapping
BOOK_ABBR_TO_FULL = {
    # Old Testament
    "Gen.": "Genesis",
    "Ex.": "Exodus",
    "Lev.": "Leviticus",
    "Num.": "Numbers",
    "Deu.": "Deuteronomy",
    "Josh.": "Joshua",
    "Judg.": "Judges",
    "Ruth": "Ruth",
    "1 Sam.": "1 Samuel",
    "2 Sam.": "2 Samuel",
    "1 Ki.": "1 Kings",
    "2 Ki.": "2 Kings",
    "1 Chr.": "1 Chronicles",
    "2 Chr.": "2 Chronicles",
    "Ezra": "Ezra",
    "Neh.": "Nehemiah",
    "Esth.": "Esther",
    "Job": "Job",
    "Ps.": "Psalms",
    "Prov.": "Proverbs",
    "Eccl.": "Ecclesiastes",
    # In the https://github.com/farskipper/kjv json,
    # its called Solomon's Song, while most other
    # bibles call it Song of Solomon
    "Song": "Solomon's Song",
    "Is.": "Isaiah",
    "Jer.": "Jeremiah",
    "Lam.": "Lamentations",
    "Eze.": "Ezekiel",
    "Dan.": "Daniel",
    "Hos.": "Hosea",
    "Joel": "Joel",
    "Amos": "Amos",
    "Obad.": "Obadiah",
    "Jonah": "Jonah",
    "Micah": "Micah",
    "Nah.": "Nahum",
    "Hab.": "Habakkuk",
    "Zeph.": "Zephaniah",
    "Hag.": "Haggai",
    "Zech.": "Zechariah",
    "Mal.": "Malachi",
    # New Testament
    "Mt.": "Matthew",
    "Mk.": "Mark",
    "Lk.": "Luke",
    "Jn.": "John",
    "Acts": "Acts",
    "Rom.": "Romans",
    "1 Cor.": "1 Corinthians",
    "2 Cor.": "2 Corinthians",
    "Gal.": "Galatians",
    "Eph.": "Ephesians",
    "Phil.": "Philippians",
    "Col.": "Colossians",
    "1 Thess.": "1 Thessalonians",
    "2 Thess.": "2 Thessalonians",
    "1 Tim.": "1 Timothy",
    "2 Tim.": "2 Timothy",
    "Tit.": "Titus",
    "Philem.": "Philemon",
    "Heb.": "Hebrews",
    "Jas.": "James",
    "1 Pet.": "1 Peter",
    "2 Pet.": "2 Peter",
    "1 Jn.": "1 John",
    "2 Jn.": "2 John",
    "3 Jn.": "3 John",
    "Jude": "Jude",
    "Rev.": "Revelation",
}

# Books with a single chapter where references are commonly written as "Philem. 9"
# rather than "Philem. 1:9"
SINGLE_CHAPTER_ABBR = {"Obad.", "Philem.", "2 Jn.", "3 Jn.", "Jude"}
SINGLE_CHAPTER_BOOKS = {BOOK_ABBR_TO_FULL[a] for a in SINGLE_CHAPTER_ABBR if a in BOOK_ABBR_TO_FULL}

# Build regex patterns. I Medad barely understand the regex. The only thing that I read are the
# unittests which have concrete test cases.
sorted_abbrs = sorted(BOOK_ABBR_TO_FULL, key=lambda x: -len(x))
# For chapter:verse matching we should NOT match single-chapter book abbreviations
non_single = [a for a in sorted_abbrs if a not in SINGLE_CHAPTER_ABBR]
single = [a for a in sorted_abbrs if a in SINGLE_CHAPTER_ABBR]

NON_SINGLE_PATTERN = "|".join(re.escape(a) for a in non_single)
SINGLE_PATTERN = "|".join(re.escape(a) for a in single)

# Pattern supports two branches:
#  - regular (book + chapter:verse[, ...]) for non-single-chapter books
#  - verse-only (book + verse[, ...]) for single-chapter books (e.g., 'Philem. 9')
BRANCH_MULTI_CHP_BOOKS = (
    rf"(?P<abbr1>{NON_SINGLE_PATTERN})\s+(?P<refs1>\d+:\d+(?:,\s*(?:\d+:\d+|\d+))*)"
)
BRANCH_SINGLE_CHP_BOOKS = rf"(?P<abbr2>{SINGLE_PATTERN})\s+(?P<refs2>\d+(?:,\s*\d+)*)"
ref_pattern = re.compile(rf"\b(?:{BRANCH_MULTI_CHP_BOOKS}|{BRANCH_SINGLE_CHP_BOOKS})")


def load_kjv(path):
    """Load KJV verse JSON from `path` and return the parsed mapping."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"KJV Bible data file not found at '{path}'. Ensure the KJV JSON file exists."
        ) from e


class Reference:  # pylint: disable=too-many-instance-attributes
    """Represent a parsed Bible reference and produce HTML anchor/link information."""

    # 10 args are justified here - it’s a data carrier.
    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        abbr,
        book,
        chapter,
        verse,
        single_chapter,
        matched_text,
        part,
        has_colon,
        verses,
        root_word,
    ):
        """Initialize a Reference."""
        self.abbr = abbr
        self.book = book
        self.chapter = chapter
        self.verse = verse
        self.single_chapter = single_chapter
        self.matched_text = matched_text
        self.part = part
        self.has_colon = has_colon
        self.verses = verses
        self.root_word = root_word

    def visible(self, index):
        """Return the visible text for the reference at the given position."""
        if self.single_chapter:
            if index == 0:
                return f"{self.abbr} {self.verse}"
            return self.verse if not self.has_colon else self.part.split(":", 1)[1]
        if index == 0:
            return f"{self.abbr} {self.chapter}:{self.verse}"
        return self.part if self.has_colon else self.verse

    def clean_kjv_text(self, text):
        """Remove KJV markup: # and [...]"""
        text = re.sub(r"\[.*?\]", "", text)
        text = text.replace("#", " ")
        return re.sub(r"\s+", " ", text).strip()

    def get_verse_text(self):
        """Return (tooltip_html, ref_exists, root_found)."""
        first_verse = self.verse.split("-")[0]
        key = f"{self.book} {self.chapter}:{first_verse}"
        raw_verse = self.verses.get(key, "")
        if not raw_verse:
            return (
                f"{self.book} {self.chapter}:{first_verse} (KJV) - Reference not found",
                False,
                False,
            )

        clean_text = self.clean_kjv_text(raw_verse)
        root_lower = self.root_word.lower()
        verse_lower = clean_text.lower()
        root_found = root_lower in verse_lower

        tooltip = (
            f"<strong>{html.escape(self.root_word)}</strong>: "
            f"{self.book} {self.chapter}:{first_verse} (KJV) - {raw_verse}"
        )
        return tooltip, True, root_found

    def resolve(self):
        """Return (verse_text, ref_exists, root_found, url)."""
        first_verse = self.verse.split("-")[0]
        if self.chapter is None:
            url = (
                "https://www.biblegateway.com/passage/?search="
                f"{self.book}+{first_verse}&version=KJV"
            )
            return "", False, False, url

        verse_text, ref_exists, root_found = self.get_verse_text()
        url = (
            "https://www.biblegateway.com/passage/?search="
            f"{self.book}+{self.chapter}%3A{first_verse}&version=KJV"
        )
        return verse_text, ref_exists, root_found, url

    def to_anchor(self, index: int) -> str:
        """Construct the anchor HTML for this reference."""
        verse_text, ref_exists, root_found, url = self.resolve()
        visible = self.visible(index)

        if not ref_exists:
            css_class = "bible-ref-missing"
            ref_text = f"{visible} [REF NOT FOUND]"
        elif not root_found:
            css_class = "bible-ref-no-root"
            ref_text = f"{visible} [ROOT WORD MISSING]"
        else:
            css_class = "bible-ref"
            ref_text = visible

        return (
            f'<a href="{html.escape(url)}" class="{css_class}" '
            f'data-verse="{html.escape(verse_text)}">{html.escape(ref_text)}</a>'
        )


def parse_references_with_root(text, verses, root_word):
    """Parse references in `text` and attach `root_word` to each."""
    results = []
    for match in ref_pattern.finditer(text):
        abbr = match.group("abbr1") or match.group("abbr2")
        refs_part = match.group("refs1") or match.group("refs2")
        full_book = BOOK_ABBR_TO_FULL.get(abbr, abbr)
        single_chapter = full_book in SINGLE_CHAPTER_BOOKS

        parts = [p.strip() for p in refs_part.split(",")]
        current_chapter = None

        for part in parts:
            if has_colon := ":" in part:
                chapter, verse = part.split(":", 1)
                current_chapter = chapter
            else:
                chapter = "1" if single_chapter else current_chapter
                verse = part

            if chapter is None:
                continue  # skip malformed

            results.append(
                Reference(
                    abbr=abbr,
                    book=full_book,
                    chapter=chapter,
                    verse=verse,
                    single_chapter=single_chapter,
                    matched_text=match.group(0),
                    part=part,
                    has_colon=has_colon,
                    verses=verses,
                    root_word=root_word,
                )
            )
    return results


def extract_paragraphs(doc, verses):
    paragraphs = []
    for elem in doc.getElementsByType(P):
        raw_txt = teletype.extractText(elem)
        if not raw_txt.strip():
            continue
        txt = re.sub(r"\s+", " ", raw_txt).strip()

        # Try to extract root word more carefully
        root_word = None
        words = re.split(r"(\s+)", txt)  # keep whitespace for position tracking
        i = 0
        while i < len(words):
            w = words[i].strip()
            if not w:
                i += 1
                continue

            # Candidate: all caps, length ≥ 2, no punctuation inside (ignore trailing .,;)
            clean_w = re.sub(r"[.,;:!?\)]*$", "", w)
            if clean_w.isalpha() and clean_w.isupper() and len(clean_w) >= 2:
                # Look ahead: next non-whitespace token should NOT be all-caps (unless multi-word root — rare)
                j = i + 1
                while j < len(words) and words[j].isspace():
                    j += 1
                if j < len(words):
                    next_token = re.sub(r"[.,;:!?\)]*$", "", words[j])
                    # If next token starts with lowercase OR is a small word (I, a, the, his, etc.), this is likely the end of root
                    if (next_token[0].islower() if next_token else False) or next_token in {
                        "I",
                        "a",
                        "the",
                        "his",
                        "her",
                        "their",
                        "my",
                        "thy",
                        "ye",
                        "you",
                        "we",
                        "it",
                    }:
                        root_word = clean_w
                        break
                # Also accept if next token is punctuation (e.g., comma)
                elif j < len(words) and re.match(r"^[,\.\-\)]", words[j]):
                    root_word = clean_w
                    break
            i += 1

        if root_word is None:
            # Fallback: use first all-caps word ≥2 chars, even if imperfect
            fallback_match = re.search(r"\b([A-Z]{2,})\b", txt)
            if fallback_match:
                root_word = fallback_match.group(1)
            else:
                # No root word found → treat as plain text
                paragraphs.append(html.escape(txt))
                continue

        # Now split by |, but only after root word
        # Remove root word from txt for segment parsing
        # Find where root_word appears (first occurrence)
        root_pos = txt.find(root_word)
        if root_pos == -1:
            paragraphs.append(html.escape(txt))
            continue

        remainder = txt[root_pos + len(root_word) :].lstrip()
        segments = [s.strip() for s in remainder.split("|") if s.strip()]

        rendered_segments = []
        for seg in segments:
            new_seg = ref_pattern.sub(
                lambda m: ", ".join(
                    r.to_anchor(i)
                    for i, r in enumerate(parse_references_with_root(m.group(0), verses, root_word))
                )
                or html.escape(m.group(0)),
                seg,
            )
            rendered_segments.append(new_seg)

        final_line = f"<strong>{html.escape(root_word)}</strong> " + " | ".join(rendered_segments)
        paragraphs.append(final_line)

    return paragraphs


def write_html(paragraphs, style):
    """Write `paragraphs` to an HTML string wrapped in a simple HTML document using `style`."""
    html_content = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '    <meta charset="UTF-8">\n'
        "    <title>Bible Concordance</title>\n"
        f"    <style>{style}</style>\n"
        "</head>\n"
        "<body>\n"
    )
    for p in paragraphs:
        html_content += f"<p>{p}</p>\n"
    html_content += "</body>\n</html>"
    return html_content


def convert_odt_bytes_to_html(odt_bytes):
    """Convert ODT bytes to an HTML string (keeps everything in memory)."""
    kjv_verses = load_kjv(KJV_JSON_PATH)
    bio = io.BytesIO(odt_bytes)
    doc = load(bio)
    paragraphs = extract_paragraphs(doc, kjv_verses)

    style = """
        body { font-family: Arial, sans-serif; line-height: 1.6; margin: 10em; }
        p { margin: 0 0 1em 0; }
        .bible-ref { 
            color: #0066cc; 
            cursor: help; 
            border-bottom: 1px dotted #0066cc;
            text-decoration: none;
            position: relative;
        }
        .bible-ref:hover { 
            background-color: #f0f8ff;
            text-decoration: underline;
        }
        .bible-ref::after {
            content: attr(data-verse);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
            white-space: normal;
            min-width: 200px;
            word-wrap: break-word;
        }
        .bible-ref:hover::after {
            opacity: 1;
        }
        .bible-ref-missing { 
            color: #cc0000; 
            cursor: help; 
            border-bottom: 2px solid #cc0000;
            text-decoration: none;
            position: relative;
            background-color: #ffe6e6;
        }
        .bible-ref-missing:hover { 
            background-color: #ffcccc;
            text-decoration: underline;
        }
        .bible-ref-missing::after {
            content: attr(data-verse);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #cc0000;
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
            max-width: 400px;
            white-space: normal;
            word-wrap: break-word;
        }

        .bible-ref-missing:hover::after { opacity: 1; }

        .bible-ref-no-root { 
            color: #cc6600; 
            cursor: help; 
            border-bottom: 2px dashed #cc6600;
            text-decoration: none;
            position: relative;
            background-color: #fff9e6;
        }
        .bible-ref-no-root:hover { 
            background-color: #ffebcc;
            text-decoration: underline;
        }
        .bible-ref-no-root::after {
            content: attr(data-verse);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #cc6600;
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
            max-width: 400px;
            white-space: normal;
            word-wrap: break-word;
        }
        .bible-ref-no-root:hover::after {
            opacity: 1;
        }
    """
    return write_html(paragraphs, style)


def convert_odt_to_html(odt_path, html_path):
    """Compatibility wrapper: read file and save to disk."""
    if not os.path.exists(odt_path):
        raise FileNotFoundError(f"File '{odt_path}' not found.")

    with open(odt_path, "rb") as f:
        odt_bytes = f.read()

    html_content = convert_odt_bytes_to_html(odt_bytes)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return html_path


def main():
    """Convert an ODT file with Bible references to an HTML file with hyperlinks."""
    parser = argparse.ArgumentParser(
        description="Convert an ODT file with Bible references to an HTML file with hyperlinks."
    )
    parser.add_argument("input_odt", help="The path to the input ODT file.")
    parser.add_argument("output_html", help="The path to the output HTML file.")
    args = parser.parse_args()

    out = convert_odt_to_html(args.input_odt, args.output_html)
    print(f"Success: HTML saved to {out}")


if __name__ == "__main__":
    # Example usage:
    # python3 add_hyperlinks.py input/concordance.odt output/concordance.html
    main()
