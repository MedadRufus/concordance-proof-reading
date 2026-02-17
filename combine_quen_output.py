#!/usr/bin/env python3
"""
Script to combine all markdown files in quen_output directory with dividers between them.
"""

import os
import glob
import re
import subprocess


def replace_bible_references(file_path):
    """
    Replace all instances of "X.Y" with "X:Y" in the specified file.

    Args:
        file_path (str): Path to the file to modify
    """
    # Read the file
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

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
    # Get all markdown files and sort them alphabetically
    markdown_files = sorted(glob.glob(os.path.join(output_dir, "*.md")))

    # Remove any files we don't want to include (like the output file itself)
    # We'll exclude files that might be temporary or metadata files
    exclude_patterns = []

    markdown_files = [
        f for f in markdown_files if not any(pattern in f for pattern in exclude_patterns)
    ]

    with open(output_file, "w", encoding="utf-8") as outfile:
        for i, md_file in enumerate(markdown_files):
            # Add a divider before each file (except the first one)
            if i > 0:
                outfile.write("\n---\n\n")

            # Add a header indicating which file this content came from
            filename = os.path.basename(md_file)
            outfile.write(f"# Content from: {filename}\n\n")

            # Read and append the content of the markdown file
            with open(md_file, "r", encoding="utf-8") as infile:
                outfile.write(infile.read())
                outfile.write("\n\n")  # Add extra spacing between files

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

    # Convert **text** to \textbf{text} BEFORE escaping braces
    content = re.sub(r"\*\*([^*]+)\*\*", r"BOLDSTART\1BOLDEND", content)

    # Escape LaTeX special characters (but NOT braces yet)
    content = (
        content.replace("&", "\\&")
        .replace("%", "\\%")
        .replace("$", "\\$")
        .replace("#", "\\#")
        .replace("_", "\\_")
    )

    # Now add braces for bold
    content = content.replace("BOLDSTART", "\\textbf{").replace("BOLDEND", "}")

    # Convert double newlines to \par, but preserve single newlines with trailing spaces
    # In markdown, two trailing spaces + newline = line break
    content = re.sub(r"  \n", r"\\\\\n", content)  # Two spaces + newline -> \\ (line break)
    content = content.replace("\n\n", "\n\\par\n")  # Double newline -> \par

    latex = r"""\documentclass[10pt,letterpaper]{article}
\usepackage[margin=0.5in]{geometry}
\usepackage{multicol}
\usepackage{microtype}
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
    output_directory = "quen_output"
    combined_output = "combined_quen_output.md"

    combine_markdown_files(output_directory, combined_output)
    tex_file = combined_output.replace(".md", ".tex")
    md_to_latex(combined_output, tex_file)
    subprocess.run(["pdflatex", "-interaction=nonstopmode", tex_file])
    print(f"Generated PDF: {tex_file.replace('.tex', '.pdf')}")
