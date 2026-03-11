#!/usr/bin/env python3
"""
Script to combine all markdown files in quen_output directory with dividers between them.
"""

import os
import glob
import re
import subprocess

# Allowed book abbreviations from add_hyperlinks.py
BOOK_ABBR_TO_FULL = {
    "Gen.": "Genesis", "Ex.": "Exodus", "Lev.": "Leviticus", "Num.": "Numbers",
    "Deu.": "Deuteronomy", "Josh.": "Joshua", "Judg.": "Judges", "Ruth": "Ruth",
    "1 Sam.": "1 Samuel", "2 Sam.": "2 Samuel", "1 Ki.": "1 Kings", "2 Ki.": "2 Kings",
    "1 Chr.": "1 Chronicles", "2 Chr.": "2 Chronicles", "Ezra": "Ezra", "Neh.": "Nehemiah",
    "Esth.": "Esther", "Job": "Job", "Ps.": "Psalms", "Prov.": "Proverbs",
    "Eccl.": "Ecclesiastes", "Song": "Solomon's Song", "Is.": "Isaiah", "Jer.": "Jeremiah",
    "Lam.": "Lamentations", "Eze.": "Ezekiel", "Dan.": "Daniel", "Hos.": "Hosea",
    "Joel": "Joel", "Amos": "Amos", "Obad.": "Obadiah", "Jonah": "Jonah",
    "Micah": "Micah", "Nah.": "Nahum", "Hab.": "Habakkuk", "Zeph.": "Zephaniah",
    "Hag.": "Haggai", "Zech.": "Zechariah", "Mal.": "Malachi", "Mt.": "Matthew",
    "Mk.": "Mark", "Lk.": "Luke", "Jn.": "John", "Acts": "Acts", "Rom.": "Romans",
    "1 Cor.": "1 Corinthians", "2 Cor.": "2 Corinthians", "Gal.": "Galatians",
    "Eph.": "Ephesians", "Phil.": "Philippians", "Col.": "Colossians",
    "1 Thess.": "1 Thessalonians", "2 Thess.": "2 Thessalonians", "1 Tim.": "1 Timothy",
    "2 Tim.": "2 Timothy", "Tit.": "Titus", "Philem.": "Philemon", "Heb.": "Hebrews",
    "Jas.": "James", "1 Pet.": "1 Peter", "2 Pet.": "2 Peter", "1 Jn.": "1 John",
    "2 Jn.": "2 John", "3 Jn.": "3 John", "Jude": "Jude", "Rev.": "Revelation",
}

# Common non-compliant abbreviations mapping to compliant ones
ABBR_REPLACEMENTS = {
    "Matt.": "Mt.", "Mark": "Mk.", "Luke": "Lk.", "John": "Jn.",
    "Deut.": "Deu.", "De.": "Deu.", "Esther":"Esth.",
    "1 Kings": "1 Ki.", "2 Kings": "2 Ki.", "1 Kin.": "1 Ki.", "2 Kin.": "2 Ki.",
    "1 Chron.": "1 Chr.", "2 Chron.": "2 Chr.",
    "Isa.": "Is.", "Ezek.": "Eze.", "Ez.": "Eze.",
    "Ho.": "Hos.",
    "Cant.": "Song", "Mic.": "Micah",
    "Lu.": "Lk.", "Luk.":"Lk.","Nu.":"Num.",
    "Pr.": "Prov.", "Ec.": "Eccl.",
    "John.": "Jn.",
    "Ju.": "Judg.",
    "Jud.": "Judg.",
    "1 Sa.": "1 Sam.",
    "2 Sa.": "2 Sam.",
    "Am.": "Amos",
    "Mat.": "Mt.",
    "Ro.": "Rom.",
    "Titus": "Tit.",
    "Ru.": "Ruth",
    "Pro.": "Prov.",
}


def normalize_book_abbreviations(content):
    """
    Replace non-compliant book abbreviations with compliant ones.
    """
    for old_abbr, new_abbr in ABBR_REPLACEMENTS.items():
        # Match abbreviation followed by space and number (to avoid false matches)
        content = re.sub(rf'\b{re.escape(old_abbr)}\s+(?=\d)', f'{new_abbr} ', content)
    return content


def replace_bible_references(file_path):
    """
    Replace all instances of "X.Y" with "X:Y" in the specified file.

    Args:
        file_path (str): Path to the file to modify
    """
    # Read the file
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    # Normalize book abbreviations first
    content = normalize_book_abbreviations(content)

    # Replace all instances of "X.Y" or "X. Y" with "X:Y"
    new_content = re.sub(r"(\d+)\.\s*(\d+)", r"\1:\2", content)

    # Write the modified content back to the file
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(new_content)

    print(f"Successfully updated {file_path}")


def combine_markdown_files(output_dir, output_file):
    """
    Combine all markdown files in the output directory into a single file,
    with dividers between each file.

    Args:
        output_dir (str): Path to the directory containing markdown files
        output_file (str): Path to the output combined file
    """
    # Get all markdown files and sort them numerically by page number
    markdown_files = glob.glob(os.path.join(output_dir, "*.md"))
    markdown_files.sort(key=lambda x: int(re.search(r'\d+', os.path.basename(x)).group()))

    # Remove any files we don't want to include (like the output file itself)
    # We'll exclude files that might be temporary or metadata files
    exclude_patterns = []

    markdown_files = [
        f for f in markdown_files if not any(pattern in f for pattern in exclude_patterns)
    ]

    with open(output_file, "w", encoding="utf-8") as outfile:
        for i, md_file in enumerate(markdown_files):

            # Read and append the content of the markdown file
            with open(md_file, "r", encoding="utf-8") as infile:
                outfile.write(infile.read())
                outfile.write("\n")  # Add extra spacing between files

    print(f"Successfully combined {len(markdown_files)} markdown files into {output_file}")
    # Apply bible reference replacement
    replace_bible_references(output_file)


def md_to_latex(md_file, tex_file):
    """Convert markdown to 3-column LaTeX."""
    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove markdown headers
    content = re.sub(r"^# Content from:.*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"^---$", "", content, flags=re.MULTILINE)

    # Convert **text** to \textbf{text} and _text_ to \textit{text} BEFORE escaping
    content = re.sub(r"\*\*([^*]+)\*\*", r"BOLDSTART\1BOLDEND", content)
    content = re.sub(r"_([^_]+)_", r"ITALICSTART\1ITALICEND", content)

    # Escape LaTeX special characters
    content = (
        content.replace("&", "\\&")
        .replace("%", "\\%")
        .replace("$", "\\$")
        .replace("#", "\\#")
    )

    # Now add braces for bold and italic
    content = content.replace("BOLDSTART", "\\textbf{").replace("BOLDEND", "}")
    content = content.replace("ITALICSTART", "\\textit{").replace("ITALICEND", "}")

    # Convert double newlines to \par
    content = content.replace("\n\n", "\n\\par\n")

    latex = r"""\documentclass[10pt,letterpaper]{article}
\usepackage[margin=0.5in]{geometry}
\usepackage{multicol}
\usepackage{microtype}
\usepackage{tgheros}
\renewcommand{\familydefault}{\sfdefault}
\setlength{\columnsep}{20pt}
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}
\pagestyle{plain}

\begin{document}
\begin{multicols}{3}
\raggedright
\small

"""
    latex += content.strip()
    latex += r"""

\end{multicols}
\end{document}
"""

    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(latex)
    print(f"Converted {md_file} to {tex_file}")


if __name__ == "__main__":
    output_directory = "deepseek_output"
    combined_output_dir = "combined_output"
    combined_output = os.path.join(combined_output_dir, "combined_deepseek_output.md")
    
    # Create output directory if it doesn't exist
    os.makedirs(combined_output_dir, exist_ok=True)

    combine_markdown_files(output_directory, combined_output)
    tex_file = combined_output.replace(".md", ".tex")
    md_to_latex(combined_output, tex_file)
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "-output-directory", combined_output_dir, tex_file])
    print(f"Generated PDF: {tex_file.replace('.tex', '.pdf')}")
