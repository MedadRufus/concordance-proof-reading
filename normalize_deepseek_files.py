#!/usr/bin/env python3
"""
Normalize deepseek_output files to ensure consistent spacing between root word sections.
"""

import os
import re
import glob


def normalize_file(file_path):
    """
    Normalize a single markdown file to ensure consistent spacing.
    Each root word section (starting with **WORD**) should be preceded by exactly one blank line.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split into lines
    lines = content.split('\n')
    normalized_lines = []
    
    for i, line in enumerate(lines):
        # Check if this line starts a new root word section (pattern: **WORD.**—)
        if line.startswith('**') and '.**' in line:
            # This is a root word heading
            # Ensure exactly one blank line before it (unless it's the first line)
            if i > 0:
                # Remove any trailing blank lines from normalized_lines
                while normalized_lines and normalized_lines[-1] == '':
                    normalized_lines.pop()
                # Add exactly one blank line
                normalized_lines.append('')
        
        normalized_lines.append(line)
    
    # Join back and write
    normalized_content = '\n'.join(normalized_lines)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(normalized_content)
    
    print(f"Normalized {os.path.basename(file_path)}")


def normalize_all_files(directory):
    """
    Normalize all markdown files in the specified directory.
    """
    md_files = sorted(glob.glob(os.path.join(directory, "*.md")))
    
    for md_file in md_files:
        normalize_file(md_file)
    
    print(f"\nNormalized {len(md_files)} files in {directory}")


if __name__ == "__main__":
    import sys
    directory = sys.argv[1] if len(sys.argv) > 1 else "deepseek_output"
    normalize_all_files(directory)
