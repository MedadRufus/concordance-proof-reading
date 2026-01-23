import html
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

# Prepare regex pattern
sorted_abbrs = sorted(BOOK_ABBR_TO_FULL.keys(), key=lambda x: -len(x))
ABBR_PATTERN = "|".join(re.escape(abbr) for abbr in sorted_abbrs)

# Books with a single chapter where references are commonly written as "Philem. 9" rather than "Philem. 1:9"
SINGLE_CHAPTER_ABBR = {"Obad.", "Philem.", "2 Jn.", "3 Jn.", "Jude"}
SINGLE_CHAPTER_BOOKS = {
    BOOK_ABBR_TO_FULL[a] for a in SINGLE_CHAPTER_ABBR if a in BOOK_ABBR_TO_FULL
}
single_abbrs_sorted = sorted(SINGLE_CHAPTER_ABBR, key=lambda x: -len(x))
SINGLE_ABBR_PATTERN = "|".join(re.escape(abbr) for abbr in single_abbrs_sorted)

# For chapter:verse matching we should NOT match single-chapter book abbreviations
non_single_abbrs = [abbr for abbr in sorted_abbrs if abbr not in SINGLE_CHAPTER_ABBR]
NON_SINGLE_ABBR_PATTERN = "|".join(re.escape(abbr) for abbr in non_single_abbrs)

# Pattern supports two branches:
#  - regular (book + chapter:verse[, ...]) for non-single-chapter books
#  - verse-only (book + verse[, ...]) for single-chapter books (e.g., 'Philem. 9')
branch1 = rf"(?P<abbr1>{NON_SINGLE_ABBR_PATTERN})\s+(?P<refs1>\d+:\d+(?:,\s*(?:\d+:\d+|\d+))*)"
branch2 = rf"(?P<abbr2>{SINGLE_ABBR_PATTERN})\s+(?P<refs2>\d+(?:,\s*\d+)*)(?!:)"
ref_pattern = re.compile(rf"\b(?:{branch1}|{branch2})")


def parse_references(text):
    """Parse scripture references in text and return a list of reference objects.

    Each object has keys:
      - abbr, book, chapter, verse, single_chapter, matched_text
      - part: the original part string (e.g., '18:14' or '14')
      - has_colon: whether the original part contained ':'
    """
    results = []

    for match in ref_pattern.finditer(text):
        abbr = match.group("abbr1") or match.group("abbr2")
        refs_part = match.group("refs1") or match.group("refs2")
        full_book = BOOK_ABBR_TO_FULL.get(abbr, abbr)
        single_chapter = full_book in SINGLE_CHAPTER_BOOKS

        parts = [p.strip() for p in refs_part.split(",")]
        current_chapter = None
        for part in parts:
            has_colon = ":" in part
            if has_colon:
                chapter, verse = part.split(":", 1)
                current_chapter = chapter
            else:
                if single_chapter:
                    chapter = "1"
                else:
                    chapter = current_chapter
                verse = part

            results.append(
                {
                    "abbr": abbr,
                    "book": full_book,
                    "chapter": chapter,
                    "verse": verse,
                    "single_chapter": single_chapter,
                    "matched_text": match.group(0),
                    "part": part,
                    "has_colon": has_colon,
                }
            )

    return results


try:
    with open(KJV_JSON_PATH, "r", encoding="utf-8") as f:
        kjv_verses = json.load(f)
except FileNotFoundError as e:
    raise FileNotFoundError(
        f"KJV Bible data file not found at '{KJV_JSON_PATH}'. "
        "Please ensure the KJV JSON file is present in the expected directory."
    ) from e


def get_verse_text(book, chapter, verse):
    """Get verse text from local KJV data"""
    key = f"{book} {chapter}:{verse}"
    verse_text = kjv_verses.get(key, "")
    if verse_text:
        return f"{book} {chapter}:{verse} (KJV) - {verse_text}", True
    return f"{book} {chapter}:{verse} (KJV) - Reference not found", False


def replace_reference(match):
    """Build replacement HTML for a regex match using parse_references."""
    matched_text = match.group(0)
    refs = parse_references(matched_text)
    # If parse_references for some reason returns nothing, fall back to leaving text unchanged
    if not refs:
        return matched_text

    full_book = refs[0]["book"]
    single_chapter = refs[0]["single_chapter"]
    abbr = refs[0]["abbr"]

    linked_parts = []

    for i, ref in enumerate(refs):
        chapter = ref["chapter"]
        verse = ref["verse"]
        part = ref["part"]
        has_colon = ref["has_colon"]

        first_verse = verse.split("-")[0]

        # If chapter is still None (e.g., malformed reference like "Gen. 3"), mark as not found
        if chapter is None:
            verse_text, verse_exists = "", False
            search_query = f"{full_book}+{first_verse}"
            url = f"https://www.biblegateway.com/passage/?search={search_query}&version=KJV"
        else:
            verse_text, verse_exists = get_verse_text(full_book, chapter, first_verse)
            search_query = f"{full_book}+{chapter}%3A{first_verse}"
            url = f"https://www.biblegateway.com/passage/?search={search_query}&version=KJV"

        # Build visible reference text
        if single_chapter:
            # For single chapter books, prefer 'Philem. 9' (omit the '1:' chapter)
            if i == 0:
                base_ref = f"{abbr} {verse}"
            else:
                base_ref = verse if not has_colon else part.split(":", 1)[1]
        else:
            if i == 0:
                base_ref = f"{abbr} {chapter}:{verse}"
            else:
                base_ref = part if has_colon else verse

        # Mark missing refs so that they can be found with a word search on the browser
        if not verse_exists:
            ref_text = f"{base_ref} [REF NOT FOUND]"
        else:
            ref_text = base_ref

        css_class = "bible-ref" if verse_exists else "bible-ref-missing"
        linked_parts.append(
            f'<a href="{html.escape(url)}" class="{css_class}" data-verse="{html.escape(verse_text)}">{html.escape(ref_text)}</a>'
        )

    return ", ".join(linked_parts)


def main():
    if len(sys.argv) != 3:
        print("Usage: python odt_bible_links.py <input.odt> <output.html>")
        sys.exit(1)

    odt_path = sys.argv[1]
    html_path = sys.argv[2]

    if not os.path.exists(odt_path):
        print(f"Error: File '{odt_path}' not found.")
        sys.exit(1)

    doc = load(odt_path)
    paragraphs = []
    for elem in doc.getElementsByType(P):
        txt = teletype.extractText(elem)
        if txt.strip():
            txt = re.sub(r"\s+", " ", txt)
            txt_linked = ref_pattern.sub(replace_reference, txt)
            paragraphs.append(txt_linked)

    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Bible Concordance</title>
    <style>
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
        .bible-ref::after {
            content: attr(data-verse);
            position: absolute;
            bottom: 100%;
            left: 0;
            background: #333;
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
            white-space: normal;
            min-width: 300px;
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
            left: 0;
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
        .bible-ref-missing:hover::after {
            opacity: 1;
        }
    </style>
</head>
<body>
"""
    for p in paragraphs:
        html_content += f"<p>{p}</p>\n"
    html_content += "</body>\n</html>"

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Success: HTML saved to {html_path}")


if __name__ == "__main__":
    # Example usage:
    # python3 add_hyperlinks.py input/concordance.odt output/concordance.html
    main()
