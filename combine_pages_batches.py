import os
from PIL import Image
import pdf2image
from pathlib import Path
import zipfile
import tempfile
import shutil

def extract_zip_to_temp(zip_path):
    """Extract zip file to temporary directory and return the path."""
    temp_dir = tempfile.mkdtemp()
    print(f"Extracting zip to {temp_dir}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
    return temp_dir

def combine_page_batch(page_numbers, temp_dir, output_name="combined_pages.jpg", dpi=150):
    """
    Combine a batch of PDF pages vertically and export as high-res JPEG.
    
    Args:
        page_numbers: List of page numbers to combine (e.g., [1, 2, 3, ..., 8])
        temp_dir: Path to temporary directory containing extracted PDFs
        output_name: Name of output JPEG file
        dpi: Resolution in dots per inch (default 600 for high-res)
    """
    images = []
    
    # Collect all PDFs for the specified pages
    for page_num in page_numbers:
        # Find all PDFs matching the page number pattern (e.g., 1.1, 1.2, 1.3, etc.)
        medad_dir = Path(temp_dir) / "Medad"
        page_files = sorted(medad_dir.glob(f"{page_num}.*.pdf")) + sorted(medad_dir.glob(f"{page_num}.pdf"))
        
        if not page_files:
            print(f"  Warning: No PDFs found for page {page_num}")
            continue
        
        print(f"Found {len(page_files)} PDF(s) for page {page_num}")
        
        # Convert each PDF page to image and add to list
        for pdf_file in page_files:
            print(f"  Converting {pdf_file.name}...")
            pdf_images = pdf2image.convert_from_path(str(pdf_file), dpi=dpi)
            images.extend(pdf_images)
    
    if not images:
        print(f"No PDFs found for pages {page_numbers}!")
        return None
    
    print(f"Stacking {len(images)} image(s) vertically...\n")
    
    # Get dimensions
    widths = [img.width for img in images]
    heights = [img.height for img in images]
    
    # Use the maximum width
    max_width = max(widths)
    total_height = sum(heights)
    
    # Create a new image with the combined dimensions
    combined_image = Image.new('RGB', (max_width, total_height), color='white')
    
    # Paste each image vertically, centered horizontally
    y_offset = 0
    for img in images:
        x_offset = (max_width - img.width) // 2
        combined_image.paste(img, (x_offset, y_offset))
        y_offset += img.height
    
    # Save as JPEG with balanced quality for OCR and file size
    if not output_name.endswith('.jpg'):
        output_name = output_name.replace('.png', '.jpg')
    combined_image.save(output_name, 'JPEG', quality=95, optimize=True)
    print(f"✓ Saved to {output_name}")
    print(f"  Dimensions: {combined_image.width} x {combined_image.height} pixels\n")
    return output_name

def combine_all_batches(zip_path, batch_size=4, dpi=150, output_dir="output"):
    """
    Extract zip and combine pages in batches.
    
    Args:
        zip_path: Path to the zip file
        batch_size: Number of pages per batch (default 8)
        dpi: Resolution in dots per inch
        output_dir: Directory to save combined images
    """
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Extract zip to temp directory
    temp_dir = extract_zip_to_temp(zip_path)
    
    try:
        # Create batches and combine
        batch_num = 1
        page_num = 1
        
        # Estimate total pages by scanning the directory
        medad_dir = Path(temp_dir) / "Medad"
        pdf_files = list(medad_dir.glob("*.pdf"))
        page_numbers = set()
        for f in pdf_files:
            # Extract page number from filename
            parts = f.stem.split('.')
            try:
                page_numbers.add(int(parts[0]))
            except ValueError:
                pass
        
        max_page = max(page_numbers) if page_numbers else 0
        print(f"Found pages 1 to {max_page}\n")
        
        # Process batches
        while page_num <= max_page:
            batch_pages = list(range(page_num, min(page_num + batch_size, max_page + 1)))
            output_name = f"{output_dir}/pages_{batch_pages[0]}-{batch_pages[-1]}_combined.jpg"
            
            print(f"Processing batch {batch_num}: pages {batch_pages[0]}-{batch_pages[-1]}")
            combine_page_batch(batch_pages, temp_dir, output_name, dpi)
            
            page_num += batch_size
            batch_num += 1
            
    finally:
        # Clean up temp directory
        print(f"Cleaning up temporary directory...")
        shutil.rmtree(temp_dir)
        print("Done!")

if __name__ == "__main__":
    zip_path = "/media/medad/Data/concordance_digitise/Filemail.com - the files we spoke about, each page split into 3 sectopms.zip"
    combine_all_batches(zip_path, batch_size=4, dpi=300, output_dir="output")
