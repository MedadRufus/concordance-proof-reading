#!/usr/bin/env python3
"""Add double trailing whitespace to all lines in deepseek_output markdown files."""
import os
from pathlib import Path

def add_trailing_spaces(file_path):
    """Add double trailing whitespace to all lines in a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    modified_lines = []
    for line in lines:
        # Remove existing trailing whitespace, then add double space before newline
        stripped = line.rstrip()
        if stripped:  # Non-empty line
            modified_lines.append(stripped + '  \n')
        else:  # Empty line
            modified_lines.append('\n')
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(modified_lines)

def main():
    deepseek_dir = Path(__file__).parent / 'deepseek_output'
    
    for md_file in sorted(deepseek_dir.glob('pages_*.md')):
        print(f"Processing {md_file.name}...")
        add_trailing_spaces(md_file)
    
    print("Done!")

if __name__ == '__main__':
    main()
