#!/usr/bin/env python3
"""Convert combined_quen_output.md to HTML."""

from add_hyperlinks import convert_markdown_to_html

def main():
    md_path = "data/combined_quen_output.md"
    html_path = "output/concordance.html"
    
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()
    
    html_output = convert_markdown_to_html(md_text)
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_output)
    
    print(f"Success: HTML saved to {html_path}")

if __name__ == "__main__":
    main()
