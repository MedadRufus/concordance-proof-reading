#!/usr/bin/env python3
"""
Comprehensive script to automate transcription process from step 2 to 6.
This script performs all steps needed to convert deepseek output into a final HTML concordance.
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(command, description):
    """Run a shell command and handle errors."""
    print(f"\n{description}")
    print(f"Running: {command}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print("✓ Success")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    print("Starting transcription automation from step 2 to 6...")
    
    # Step 2: Add trailing spaces to deepseek output files
    if not run_command("python3 fix_trailing_spaces.py", "Step 2: Adding trailing spaces to markdown files"):
        print("Failed at step 2")
        return False
    
    # Step 3: Normalize deepseek files
    if not run_command("python3 normalize_deepseek_files.py", "Step 3: Normalizing deepseek output files"):
        print("Failed at step 3")
        return False
    
    # Step 4: Combine AI output
    if not run_command("python3 combine_ai_output.py", "Step 4: Combining AI output files"):
        print("Failed at step 4")
        return False
    
    # Step 5: Add hyperlinks to create final HTML
    if not run_command("python3 add_hyperlinks_md.py", "Step 5: Adding hyperlinks to create final HTML"):
        print("Failed at step 5")
        return False
    
    print("\n✓ All steps completed successfully!")
    print("Final HTML output is available at output/concordance.html")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)