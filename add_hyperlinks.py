import html
import os
import re
import sys
import json

from odf import teletype
from odf.opendocument import load
from odf.text import P

# Bible book abbreviation mapping
BOOK_ABBR_TO_FULL = {
    # Old Testament
    "Gen.": "Genesis",
    "Ex.": "Exodus",
    "Lev.": "Leviticus",
    "Num.": "Numbers",
    "Deu.": "Deuteronomy",
    "Deut.": "Deuteronomy",
    "Josh.": "Joshua",
    "Judg.": "Judges",
    "Ruth": "Ruth",
    "1 Sam.": "1 Samuel",
    "2 Sam.": "2 Samuel",
    "1 Kings": "1 Kings",
    "1 Ki.": "1 Kings",
    "2 Kings": "2 Kings",
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
    "Song": "Solomon's Song",
    "SS.": "Solomon's Song",
    "Isa.": "Isaiah",
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
    "Mic.": "Micah",
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
    "Titus": "Titus",
    "Tit.": "Titus",
    "Philem.": "Philemon",
    "Phm.": "Philemon",
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
ref_pattern = re.compile(rf"\b({ABBR_PATTERN})\s+(\d+:\d+(?:,\s*(?:\d+:\d+|\d+))*)")


# Load KJV Bible data
kjv_verses = {}
try:
    with open("kjv/json/verses-1769.json", "r", encoding="utf-8") as f:
        kjv_verses = json.load(f)
except FileNotFoundError:
    print("Warning: KJV Bible data not found. Verse tooltips will show reference only.")


def get_verse_text(book, chapter, verse):
    """Get verse text from local KJV data"""
    key = f"{book} {chapter}:{verse}"
    verse_text = kjv_verses.get(key, "")
    if verse_text:
        return f"{book} {chapter}:{verse} (KJV) - {verse_text}"
    return f"{book} {chapter}:{verse} (KJV)"


def replace_reference(match):
    abbr = match.group(1)
    refs_part = match.group(2)
    full_book = BOOK_ABBR_TO_FULL.get(abbr, abbr)

    # Split by commas only
    parts = [p.strip() for p in refs_part.split(",")]
    linked_parts = []
    current_chapter = None

    for i, part in enumerate(parts):
        if ":" in part:
            chapter, verse = part.split(":", 1)
            current_chapter = chapter
        else:
            # Just a verse number, use current chapter
            chapter = current_chapter
            verse = part

        first_verse = verse.split("-")[0]

        verse_text = get_verse_text(full_book, chapter, first_verse)
        search_query = f"{full_book}+{chapter}%3A{first_verse}"
        url = f"https://www.biblegateway.com/passage/?search={search_query}&version=KJV"

        if i == 0:
            ref_text = f"{abbr} {chapter}:{verse}"
        else:
            ref_text = verse if ":" not in part else part

        linked_parts.append(
            f'<a href="{html.escape(url)}" class="bible-ref" title="{html.escape(verse_text)}">{html.escape(ref_text)}</a>'
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
        }
        .bible-ref:hover { 
            background-color: #f0f8ff;
            text-decoration: underline;
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
    # python add_hyperlinks.py concordance.odt output.html
    main()
