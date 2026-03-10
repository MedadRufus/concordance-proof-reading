#!/usr/bin/env python3
"""Convert markdown concordance to HTML with hyperlinks and root word validation."""

import argparse
import html
import json
import os
import re

from add_hyperlinks import (
    BOOK_ABBR_TO_FULL,
    SINGLE_CHAPTER_BOOKS,
    load_kjv,
    ref_pattern,
)


def check_root_word_in_verse(root_word, verse_text):
    """Check if root word appears in verse (case-insensitive)."""
    if not root_word or not verse_text:
        return True
    return root_word.lower() in verse_text.lower()


def create_anchor(abbr, chapter, verse, verse_text, verse_exists, root_word_found, index, part, has_colon, single_chapter):
    """Create HTML anchor for a reference."""
    if single_chapter:
        visible = f"{abbr} {verse}" if index == 0 else (verse if not has_colon else part.split(":", 1)[1])
    else:
        visible = f"{abbr} {chapter}:{verse}" if index == 0 else (part if has_colon else verse)
    
    book = BOOK_ABBR_TO_FULL.get(abbr, abbr)
    first_verse = verse.split("-")[0]
    url = f"https://www.biblegateway.com/passage/?search={book}+{chapter}%3A{first_verse}&version=KJV"
    
    if not verse_exists:
        css_class = "bible-ref-missing"
        ref_text = f"{visible} [REF NOT FOUND]"
    elif not root_word_found:
        css_class = "bible-ref-missing"
        ref_text = f"{visible} [ROOT WORD NOT IN VERSE]"
    else:
        css_class = "bible-ref"
        ref_text = visible
    
    return f'<a href="{html.escape(url)}" class="{css_class}" data-verse="{html.escape(verse_text)}">{html.escape(ref_text)}</a>'


def process_line_references(line, verses, root_word):
    """Process all Bible references and highlight transcription errors."""
    replacements = {}

    def replace_ref_for_storing(match):
        """Temporarily replace Bible references with a placeholder."""
        placeholder = f"__REF_{len(replacements)}__"
        
        abbr = match.group("abbr1") or match.group("abbr2")
        refs_part = match.group("refs1") or match.group("refs2")
        full_book = BOOK_ABBR_TO_FULL.get(abbr, abbr)
        single_chapter = full_book in SINGLE_CHAPTER_BOOKS
        
        parts = [p.strip() for p in refs_part.split(",")]
        current_chapter = None
        anchors = []
        
        for i, part in enumerate(parts):
            has_colon = ":" in part
            if has_colon:
                chapter, verse = part.split(":", 1)
                current_chapter = chapter
            else:
                chapter = "1" if single_chapter else current_chapter
                verse = part
            
            if chapter is None:
                continue
            
            first_verse = verse.split("-")[0]
            key = f"{full_book} {chapter}:{first_verse}"
            verse_text = verses.get(key, "")
            verse_exists = bool(verse_text)
            root_word_found = check_root_word_in_verse(root_word, verse_text) if verse_exists else False
            
            full_verse_text = f"{full_book} {chapter}:{first_verse} (KJV) - {verse_text if verse_exists else 'Reference not found'}"
            anchors.append(create_anchor(abbr, chapter, verse, full_verse_text, verse_exists, root_word_found, i, part, has_colon, single_chapter))
        
        replacements[placeholder] = ", ".join(anchors)
        return placeholder

    line_with_placeholders = ref_pattern.sub(replace_ref_for_storing, line)
    
    # Highlight standalone numbers as potential transcription errors
    line_with_highlights = re.sub(
        r'\b\d+\b',
        r'<span class="transcription-error">\g<0> [NUMBER NOT REF]</span>',
        line_with_placeholders
    )
    
    # Restore the Bible references
    final_line = line_with_highlights
    for placeholder, replacement in replacements.items():
        final_line = final_line.replace(placeholder, replacement)
        
    return final_line


def convert_markdown_to_html(md_path, html_path):
    """Convert markdown concordance to HTML with hyperlinks."""
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"File '{md_path}' not found.")
    
    verses = load_kjv("kjv/json/verses-1769.json")
    
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    paragraphs = []
    current_root_word = None
    current_paragraph_content = ""
    transcription_errors = []
    
    for line in md_content.split('\n'):
        original_line = line
        line = line.strip()
        if not line:
            # Skip empty lines but preserve structure
            continue

        # Check for transcription errors before processing
        line_without_refs = ref_pattern.sub("", line)
        if re.search(r'\b\d+\b', line_without_refs):
            transcription_errors.append(original_line)
        
        # Check for root word heading
        if match := re.match(r'\*\*([A-Z][A-Z\-]+)\.\*\*', line):
            # Save previous paragraph if exists
            if current_paragraph_content:
                paragraphs.append(current_paragraph_content)
                current_paragraph_content = ""
            
            current_root_word = match.group(1)
            # Convert markdown formatting
            line = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', line)
            line = re.sub(r'_([^_]+)_', r'<em>\1</em>', line)
            # FIXED: Also process Bible references in heading lines!
            line = process_line_references(line, verses, current_root_word)
            current_paragraph_content = line
        else:
            # Convert markdown formatting
            line = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', line)
            line = re.sub(r'_([^_]+)_', r'<em>\1</em>', line)
            # Process Bible references
            line = process_line_references(line, verses, current_root_word)
            
            # Add to current paragraph content
            if current_paragraph_content:
                current_paragraph_content += "<br>" + line  # Use <br> for line breaks
            else:
                current_paragraph_content = line
    
    # Don't forget the last paragraph
    if current_paragraph_content:
        paragraphs.append(current_paragraph_content)

    # Print transcription errors, if any
    if transcription_errors:
        print("\n--- Potential Transcription Errors ---")
        for err_line in set(transcription_errors):
            print(err_line)
        print("------------------------------------")
        print("You may want to add corrections to ABBR_REPLACEMENTS in combine_ai_output.py")
    
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
        .transcription-error {
            background-color: #ffe6e6;
            color: #cc0000;
            border: 1px solid #cc0000;
            padding: 0 2px;
            border-radius: 2px;
            cursor: help;
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
    """
    
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
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return html_path


def main():
    """Convert markdown concordance to HTML with hyperlinks."""
    parser = argparse.ArgumentParser(
        description="Convert markdown concordance to HTML with hyperlinks."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default="combined_output/combined_deepseek_output.md",
        help="The path to the input markdown file."
    )
    parser.add_argument(
        "output_html",
        nargs="?",
        default="output/concordance.html",
        help="The path to the output HTML file."
    )
    args = parser.parse_args()
    
    out = convert_markdown_to_html(args.input_file, args.output_html)
    print(f"Success: HTML saved to {out}")


if __name__ == "__main__":
    main()
