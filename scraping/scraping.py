#!/usr/bin/env python3
"""
KJV Bible scraper - scrapes kingjamesbibleonline.org and outputs JSON
matching the format used by https://github.com/farskipper/kjv
"""

import json
import time
import re
import sys
import os
import hashlib
import requests
from bs4 import BeautifulSoup

BOOKS = [
    ("Genesis", 50), ("Exodus", 40), ("Leviticus", 27), ("Numbers", 36),
    ("Deuteronomy", 34), ("Joshua", 24), ("Judges", 21), ("Ruth", 4),
    ("1 Samuel", 31), ("2 Samuel", 24), ("1 Kings", 22), ("2 Kings", 25),
    ("1 Chronicles", 29), ("2 Chronicles", 36), ("Ezra", 10), ("Nehemiah", 13),
    ("Esther", 10), ("Job", 42), ("Psalms", 150), ("Proverbs", 31),
    ("Ecclesiastes", 12), ("Song of Solomon", 8), ("Isaiah", 66),
    ("Jeremiah", 52), ("Lamentations", 5), ("Ezekiel", 48), ("Daniel", 12),
    ("Hosea", 14), ("Joel", 3), ("Amos", 9), ("Obadiah", 1), ("Jonah", 4),
    ("Micah", 7), ("Nahum", 3), ("Habakkuk", 3), ("Zephaniah", 3),
    ("Haggai", 2), ("Zechariah", 14), ("Malachi", 4),
    ("Matthew", 28), ("Mark", 16), ("Luke", 24), ("John", 21), ("Acts", 28),
    ("Romans", 16), ("1 Corinthians", 16), ("2 Corinthians", 13),
    ("Galatians", 6), ("Ephesians", 6), ("Philippians", 4), ("Colossians", 4),
    ("1 Thessalonians", 5), ("2 Thessalonians", 3), ("1 Timothy", 6),
    ("2 Timothy", 4), ("Titus", 3), ("Philemon", 1), ("Hebrews", 13),
    ("James", 5), ("1 Peter", 5), ("2 Peter", 3), ("1 John", 5),
    ("2 John", 1), ("3 John", 1), ("Jude", 1), ("Revelation", 22),
]

BASE_URL = "https://www.kingjamesbibleonline.org"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.5",
}

session = requests.Session()
session.headers.update(HEADERS)

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)


def book_to_url_name(book_name):
    """Convert book name to URL-safe format (spaces to hyphens)."""
    return book_name.replace(" ", "-")


def get_cache_path(book_name, chapter_num):
    """Get cache file path for a chapter."""
    cache_key = f"{book_name}_{chapter_num}"
    return os.path.join(CACHE_DIR, f"{cache_key}.html")


def scrape_chapter(book_name, chapter_num, retries=3):
    """Scrape all verses from a single chapter. Returns list of (verse_num, text) tuples."""
    url_book = book_to_url_name(book_name)
    url = f"{BASE_URL}/{url_book}-Chapter-{chapter_num}/"
    cache_path = get_cache_path(book_name, chapter_num)

    # Try to load from cache first
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    else:
        # Fetch from network
        for attempt in range(retries):
            try:
                resp = session.get(url, timeout=30)
                resp.raise_for_status()
                html_content = resp.text
                # Save to cache
                with open(cache_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                break
            except Exception as e:
                if attempt == retries - 1:
                    print(f"  ERROR fetching {url}: {e}", file=sys.stderr)
                    return []
                time.sleep(2 ** attempt)

    soup = BeautifulSoup(html_content, "html.parser")

    # Verses are inside <div id="div"> as <p><a href="..."><span id="N">N </span>text</a></p>
    verse_div = soup.find("div", {"id": "div"})
    if not verse_div:
        print(f"  WARNING: no verse div found at {url}", file=sys.stderr)
        return []

    verses = []
    for p in verse_div.find_all("p"):
        a = p.find("a")
        if not a:
            continue

        span = a.find("span", class_="versehover")
        if not span:
            continue

        try:
            verse_num = int(span.get_text(strip=True))
        except ValueError:
            continue

        # Remove the span (verse number) from the anchor text, then get remaining text
        span.decompose()

        # Get text without adding extra spaces
        raw_text = a.get_text()
        # Normalise whitespace - collapse multiple spaces but preserve single spaces
        raw_text = re.sub(r"\s+", " ", raw_text).strip()

        verses.append((verse_num, raw_text))

    return verses


def scrape_bible(output_path, start_book=None, verbose=True):
    """
    Scrape the full KJV Bible and save as JSON.

    Output format (matching farskipper/kjv):
    {
      "Genesis": {
        "1": {
          "1": "In the beginning God created the heaven and the earth.",
          ...
        },
        ...
      },
      ...
    }
    """
    bible = {}

    start_scraping = start_book is None

    total_books = len(BOOKS)
    for book_idx, (book_name, num_chapters) in enumerate(BOOKS, 1):
        if not start_scraping:
            if book_name == start_book:
                start_scraping = True
            else:
                continue

        if verbose:
            print(f"[{book_idx}/{total_books}] {book_name} ({num_chapters} chapters)...")

        bible[book_name] = {}

        for chap in range(1, num_chapters + 1):
            if verbose:
                print(f"  Chapter {chap}/{num_chapters}", end="\r", flush=True)

            verses = scrape_chapter(book_name, chap)

            if not verses:
                print(f"  WARNING: no verses for {book_name} {chap}", file=sys.stderr)

            bible[book_name][str(chap)] = {
                str(v_num): v_text for v_num, v_text in verses
            }

            # Polite delay - ~1 req/sec
            time.sleep(0.1)

        if verbose:
            total_verses = sum(len(c) for c in bible[book_name].values())
            print(f"  Done: {num_chapters} chapters, {total_verses} verses          ")

        # Save incrementally after each book
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(bible, f, ensure_ascii=False, indent=2)

    if verbose:
        total = sum(
            len(v) for book in bible.values() for v in book.values()
        )
        print(f"\nDone! {total} total verses saved to {output_path}")

    return bible


def scrape_single_chapter_test():
    """Quick test: scrape Genesis 1 and print results."""
    print("Test: scraping Genesis chapter 1...")
    verses = scrape_chapter("Genesis", 1)
    print(f"Found {len(verses)} verses")
    for num, text in verses[:5]:
        print(f"  {num}: {text[:80]}...")
    return verses


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape KJV Bible from kingjamesbibleonline.org")
    parser.add_argument("--output", "-o", default="kjv.json", help="Output JSON file path")
    parser.add_argument("--test", action="store_true", help="Test with Genesis 1 only")
    parser.add_argument("--start-book", help="Resume from this book name (e.g. 'Exodus')")
    args = parser.parse_args()

    if args.test:
        verses = scrape_single_chapter_test()
        test_out = {"Genesis": {"1": {str(n): t for n, t in verses}}}
        print(json.dumps(test_out, indent=2)[:1000])
    else:
        scrape_bible(args.output, start_book=args.start_book)
