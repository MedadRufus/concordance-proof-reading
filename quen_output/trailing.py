import sys

def add_markdown_breaks(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        new_lines = []
        for line in lines:
            # Strip existing trailing whitespace first to avoid double spaces
            stripped = line.rstrip()
            
            if stripped: 
                # If line is not empty, add two spaces
                new_lines.append(stripped + "  \n")
            else:
                # If line is empty, keep it empty (just the newline)
                new_lines.append("\n")
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
            
        print(f"Successfully updated {filename}")
        
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        add_markdown_breaks(sys.argv[1])
    else:
        # Default filename if none provided
        add_markdown_breaks("pages03-04.md")