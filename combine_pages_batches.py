import os
from PIL import Image
import pdf2image
from pathlib import Path
import zipfile
import tempfile
import shutil
import numpy as np

def extract_zip_to_temp(zip_path):
    """Extract zip file to temporary directory and return the path."""
    temp_dir = tempfile.mkdtemp()
    print(f"Extracting zip to {temp_dir}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
    return temp_dir

def crop_margins(img, threshold=240):
    """
    Detect and remove white/light margins from image.
    Returns cropped image.
    """
    # Convert to grayscale for margin detection
    gray = img.convert('L')
    # Convert to numpy array
    img_array = np.array(gray)
    
    # Find rows and columns that are not mostly white
    rows = np.where(np.min(img_array, axis=1) < threshold)[0]
    cols = np.where(np.min(img_array, axis=0) < threshold)[0]
    
    if len(rows) == 0 or len(cols) == 0:
        return img  # No content detected, return original
    
    # Get bounding box of content
    top = rows[0]
    bottom = rows[-1] + 1
    left = cols[0]
    right = cols[-1] + 1
    
    # Crop the image
    return img.crop((left, top, right, bottom))

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
        # Also match files without extensions (some PDFs may lack .pdf extension)
        medad_dir = Path(temp_dir) / "Medad"
        page_files = sorted(medad_dir.glob(f"{page_num}.*")) + sorted(medad_dir.glob(f"{page_num}"))
        # Filter to only files (not directories)
        page_files = [f for f in page_files if f.is_file()]
        
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
    
    print(f"Processing {len(images)} image(s): cropping margins and normalizing width...")
    
    # Crop margins from all images
    cropped_images = []
    for i, img in enumerate(images):
        cropped = crop_margins(img)
        cropped_images.append(cropped)
    
    # Find the maximum width after cropping
    max_width = max(img.width for img in cropped_images)
    
    print(f"Normalized width: {max_width} pixels")
    print(f"Stacking {len(cropped_images)} image(s) vertically...\n")
    
    # Scale all images to the same width while maintaining aspect ratio
    normalized_images = []
    total_height = 0
    for img in cropped_images:
        if img.width != max_width:
            # Scale to match max width
            scale_factor = max_width / img.width
            new_height = int(img.height * scale_factor)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        normalized_images.append(img)
        total_height += img.height
    
    # Create a new image with the combined dimensions
    combined_image = Image.new('RGB', (max_width, total_height), color='white')
    
    # Paste each image vertically
    y_offset = 0
    for img in normalized_images:
        combined_image.paste(img, (0, y_offset))
        y_offset += img.height
    
    # Save as both JPEG and PNG with balanced quality for OCR and file size
    base_output_name = output_name
    if base_output_name.endswith(('.jpg', '.png')):
        base_output_name = base_output_name.rsplit('.', 1)[0]
    
    # Save as JPEG
    jpg_output = f"{base_output_name}.jpg"
    combined_image.save(jpg_output, 'JPEG', quality=95, optimize=True)
    print(f"✓ Saved to {jpg_output}")
    
    return jpg_output

def combine_all_batches(zip_path, batch_size=4, dpi=150, output_dir="output", start_page=1):
    """
    Extract zip and combine pages in batches.
    
    Args:
        zip_path: Path to the zip file
        batch_size: Number of pages per batch (default 8)
        dpi: Resolution in dots per inch
        output_dir: Directory to save combined images
        start_page: Page number to start from (default 1)
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
        page_num = start_page
        while page_num <= max_page:
            batch_pages = list(range(page_num, min(page_num + batch_size, max_page + 1)))
            output_name = f"{output_dir}/pages_{batch_pages[0]}-{batch_pages[-1]}_combined"
            
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
    combine_all_batches(zip_path, batch_size=2, dpi=300, output_dir="output", start_page=1)
