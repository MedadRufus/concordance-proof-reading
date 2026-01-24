"""Utilities to convert ODT text references to HTML anchors linking to the KJV.

This module provides helpers to parse Bible references and produce
HTML anchors that link to BibleGateway with KJV verse tooltips.
"""

import html
import io
import json
import os
import re
import sys

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
BRANCH_SINGLE_CHP_BOOKS = rf"(?P<abbr2>{SINGLE_PATTERN})\s+(?P<refs2>\d+(?:,\s*\d+)*)(?!:)"
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

    def visible(self, index):
        """Return the visible text for the reference at the given position."""
        if self.single_chapter:
            if index == 0:
                return f"{self.abbr} {self.verse}"
            return self.verse if not self.has_colon else self.part.split(":", 1)[1]
        if index == 0:
            return f"{self.abbr} {self.chapter}:{self.verse}"
        return self.part if self.has_colon else self.verse

    def get_verse_text(self):
        """Return a tuple (verse_text, exists) for the first verse of the reference."""
        first_verse = self.verse.split("-")[0]
        key = f"{self.book} {self.chapter}:{first_verse}"
        if verse_text := self.verses.get(key, ""):
            return f"{self.book} {self.chapter}:{first_verse} (KJV) - {verse_text}", True
        return f"{self.book} {self.chapter}:{first_verse} (KJV) - Reference not found", False

    def resolve(self):
        """Return (verse_text, verse_exists, url) for this reference."""
        first_verse = self.verse.split("-")[0]
        if self.chapter is None:
            url = (
                "https://www.biblegateway.com/passage/?search="
                f"{self.book}+{first_verse}&version=KJV"
            )
            return "", False, url

        verse_text, verse_exists = self.get_verse_text()
        url = (
            "https://www.biblegateway.com/passage/?search="
            f"{self.book}+{self.chapter}%3A{first_verse}&version=KJV"
        )
        return verse_text, verse_exists, url

    def to_anchor(self, index: int) -> str:
        """Construct the anchor HTML for this reference."""
        verse_text, verse_exists, url = self.resolve()
        visible = self.visible(index)
        css_class = "bible-ref" if verse_exists else "bible-ref-missing"
        ref_text = f"{visible} [REF NOT FOUND]" if not verse_exists else visible
        return (
            f'<a href="{html.escape(url)}" class="{css_class}" '
            f'data-verse="{html.escape(verse_text)}">{html.escape(ref_text)}</a>'
        )


def parse_references(text, verses):
    """Parse all Bible references in `text` and return a list of `Reference` objects."""
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
                )
            )
    return results


def replace_reference(match, verses):
    """Replace a matched reference span with HTML anchors for each parsed reference."""
    if not (refs := parse_references(match.group(0), verses)):
        return match.group(0)
    return ", ".join(r.to_anchor(i) for i, r in enumerate(refs))


def convert_odt_bytes_to_html(odt_bytes):
    """Convert ODT bytes to an HTML string (keeps everything in memory)."""
    kjv_verses = load_kjv(KJV_JSON_PATH)
    bio = io.BytesIO(odt_bytes)
    doc = load(bio)
    paragraphs = extract_paragraphs(doc, kjv_verses)

    style = """
        body { font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; }
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
        .bible-ref-tooltip {
            position: absolute;
            background: #333;
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 1000;
            display: none;
            pointer-events: none;
            white-space: normal;
            width: max-content;
            max-width: 400px;
            word-wrap: break-word;
        }
        .bible-ref-tooltip.missing {
            background: #cc0000;
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
    """
    return write_html(paragraphs, None, style)


def extract_paragraphs(doc, verses):
    """Extract visible paragraphs from ODT `doc` and replace references using `verses`."""
    paragraphs = []
    for elem in doc.getElementsByType(P):
        txt = teletype.extractText(elem)
        if not txt.strip():
            continue
        txt = re.sub(r"\s+", " ", txt)
        txt_linked = ref_pattern.sub(lambda m: replace_reference(m, verses), txt)
        paragraphs.append(txt_linked)
    return paragraphs


def write_html(paragraphs, html_path, style):
    """Write `paragraphs` to `html_path` wrapped in a simple HTML document using `style`."""
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
    html_content += """
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const tooltip = document.createElement('div');
            tooltip.className = 'bible-ref-tooltip';
            document.body.appendChild(tooltip);

            const refs = document.querySelectorAll('.bible-ref, .bible-ref-missing');
            refs.forEach(ref => {
                ref.addEventListener('mouseenter', () => {
                    const text = ref.getAttribute('data-verse');
                    if (!text) return;
                    tooltip.textContent = text;
                    if (ref.classList.contains('bible-ref-missing')) {
                        tooltip.classList.add('missing');
                    } else {
                        tooltip.classList.remove('missing');
                    }
                    tooltip.style.display = 'block';
                    
                    const refRect = ref.getBoundingClientRect();
                    const tooltipRect = tooltip.getBoundingClientRect();
                    const scrollY = window.scrollY;
                    
                    let left = refRect.left + (refRect.width / 2) - (tooltipRect.width / 2);
                    let top = refRect.top + scrollY - tooltipRect.height - 10;

                    if (left < 10) left = 10;
                    if (left + tooltipRect.width > window.innerWidth - 10) {
                        left = window.innerWidth - tooltipRect.width - 10;
                    }
                    if (top < scrollY) {
                        top = refRect.bottom + scrollY + 10;
                    }

                    tooltip.style.left = left + 'px';
                    tooltip.style.top = top + 'px';
                });
                ref.addEventListener('mouseleave', () => {
                    tooltip.style.display = 'none';
                });
            });
        });
    </script>
    """
    html_content += "</body>\n</html>"

    return html_content


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
    if len(sys.argv) != 3:
        print("Usage: python odt_bible_links.py <input.odt> <output.html>")
        sys.exit(1)

    odt_path = sys.argv[1]
    html_path = sys.argv[2]

    try:
        out = convert_odt_to_html(odt_path, html_path)
        print(f"Success: HTML saved to {out}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Example usage:
    # python3 add_hyperlinks.py input/concordance.odt output/concordance.html
    main()
