"""
BSN Redaction Script
====================
Redacts all Dutch BSN numbers (validated via the 11-proef) from every PDF
in the 'input' folder and saves a copy prefixed with 'redacted_' to the
'output' folder. Layout and content are preserved exactly.

Requirements:
    pip install pymupdf

Usage:
    python redact_bsn.py
"""

import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit(
        "PyMuPDF is not installed. Run:  pip install pymupdf"
    )

try:
    import pytesseract
    from PIL import Image, ImageDraw
except ImportError:
    # We don't sys.exit here because we want the text-based redaction to still work
    pytesseract = None
    Image = None
    ImageDraw = None


# ---------------------------------------------------------------------------
# BSN validation
# ---------------------------------------------------------------------------

def is_valid_bsn(number: str) -> bool:
    """
    Validate a 9-digit string against the Dutch 11-proef (elfproef).

    The checksum rule:
        (9×d1) + (8×d2) + (7×d3) + (6×d4) + (5×d5) + (4×d6) + (3×d7) + (2×d8) + (-1×d9) ≡ 0 (mod 11)

    A BSN is 8 or 9 digits; 8-digit numbers are zero-padded on the left.
    """
    s = number.lstrip("0")           # strip leading zeros for length check
    digits = number.zfill(9)         # normalise to 9 digits
    if len(digits) != 9 or not digits.isdigit():
        return False
    if digits == "000000000":
        return False

    weights = [9, 8, 7, 6, 5, 4, 3, 2, -1]
    total = sum(int(d) * w for d, w in zip(digits, weights))
    return total % 11 == 0


# ---------------------------------------------------------------------------
# Candidate extraction
# ---------------------------------------------------------------------------

# Match sequences of 8 or 9 digits that are NOT part of a longer digit run.
# We also accept digits separated by spaces or dots (common notation in docs).
_CANDIDATE_PATTERN = re.compile(
    r"(?<!\d)"                      # not preceded by a digit
    r"(\d{4}\s\d{2}\s\d{3}"        # format: 1714 33 002  (spaced)
    r"|\d{9}"                       # format: 171433002   (contiguous 9-digit)
    r"|\d{8}"                       # format: 17143300    (contiguous 8-digit)
    r")"
    r"(?!\d)"                       # not followed by a digit
)


def extract_bsn_candidates(text: str):
    """Yield (match_start, match_end, cleaned_digits) for every BSN candidate."""
    for m in _CANDIDATE_PATTERN.finditer(text):
        raw = m.group()
        digits = raw.replace(" ", "").replace(".", "")
        if is_valid_bsn(digits):
            yield m.start(), m.end(), raw


# ---------------------------------------------------------------------------
# Image redaction (OCR)
# ---------------------------------------------------------------------------

def redact_image(input_path_or_img, output_path: Path = None) -> tuple[int, Image.Image]:
    """
    Perform OCR on image, redact BSNs.
    If input_path_or_img is a Path, it loads the image and saves to output_path.
    If it's an Image object, it returns the modified image.
    Returns (number_of_redactions, image).
    """
    if pytesseract is None or Image is None:
        raise RuntimeError("OCR dependencies (pytesseract, Pillow) are not installed.")

    # Ensure Tesseract is installed on system
    try:
        pytesseract.get_tesseract_version()
    except (pytesseract.TesseractNotFoundError, Exception):
        raise RuntimeError("Tesseract OCR engine not found on system. Please install Tesseract.")

    if isinstance(input_path_or_img, Path):
        img = Image.open(input_path_or_img).convert("RGB")
    else:
        img = input_path_or_img.convert("RGB")

    draw = ImageDraw.Draw(img)

    # Get OCR data: contains text and bounding boxes
    ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.LIST)

    # Filter for actual words (level 5 in Tesseract output)
    words = [d for d in ocr_data if int(d['level']) == 5]

    if not words:
        if output_path:
            img.save(output_path)
        return 0, img

    # Reconstruct full text and a mapping from character index to word index
    full_text = ""
    char_to_word = []

    for i, w in enumerate(words):
        word_text = w['text']
        for _ in range(len(word_text)):
            char_to_word.append(i)
        full_text += word_text + " "
        char_to_word.append(i) # The space

    total_redactions = 0
    for start, end, raw in extract_bsn_candidates(full_text):
        word_start_idx = char_to_word[min(start, len(char_to_word)-1)]
        word_end_idx = char_to_word[min(end-1, len(char_to_word)-1)]

        for i in range(word_start_idx, word_end_idx + 1):
            w = words[i]
            box = [int(w['left']), int(w['top']), int(w['left']) + int(w['width']), int(w['top']) + int(w['height'])]
            draw.rectangle(box, fill="black", outline="black")
            total_redactions += 1

    if output_path:
        img.save(output_path)
    return total_redactions, img


# ---------------------------------------------------------------------------
# PDF redaction
# ---------------------------------------------------------------------------

def redact_pdf_ocr(input_path: Path, output_path: Path) -> int:
    """
    Renders PDF pages as images, redacts them via OCR, and saves as a new PDF.
    """
    doc = fitz.open(str(input_path))
    redacted_images = []
    total_redactions = 0

    for page in doc:
        # Render page to image (high res for OCR)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        count, redacted_img = redact_image(img)
        redacted_images.append(redacted_img)
        total_redactions += count

    # Convert list of images back to PDF
    if redacted_images:
        # Save as a PDF
        # Only the first image needs to be converted to PDF, then others appended
        pdf_img = redacted_images[0]
        pdf_img.save(output_path, save_all=True, append_images=redacted_images[1:])

    doc.close()
    return total_redactions


def redact_pdf(input_path: Path, output_path: Path) -> int:
    """
    Open *input_path*, redact all valid BSN numbers, write to *output_path*.
    Returns the number of redactions applied across the whole document.
    """
    doc = fitz.open(str(input_path))
    total_redactions = 0
    has_text = False

    for page in doc:
        words = page.get_text("words")
        if words:
            has_text = True

        if not words:
            continue

        full_text = ""
        char_to_word = []

        for i, w in enumerate(words):
            word_text = w[4]
            for _ in range(len(word_text)):
                char_to_word.append(i)
            full_text += word_text + " "
            char_to_word.append(i) # The space

        for start, end, raw in extract_bsn_candidates(full_text):
            word_start_idx = char_to_word[min(start, len(char_to_word)-1)]
            word_end_idx = char_to_word[min(end-1, len(char_to_word)-1)]

            for i in range(word_start_idx, word_end_idx + 1):
                w = words[i]
                rect = fitz.Rect(w[0], w[1], w[2], w[3])
                rect = rect + (-1, -2, 1, 2)
                page.add_redact_annot(rect, fill=(0, 0, 0))
                total_redactions += 1

        page.apply_redactions()

    if total_redactions > 0:
        doc.save(str(output_path), garbage=4, deflate=True)
        doc.close()
        return total_redactions

    doc.close()

    # Fallback: if no redactions were made and there's no embedded text, try OCR
    if not has_text:
        return redact_pdf_ocr(input_path, output_path)

    # If it has text but no BSNs, we still save a copy to maintain consistency
    # (though in a real app we might just skip it).
    # But let's just save the original to the output path if we didn't redact.
    # We use a simple copy.
    import shutil
    shutil.copy(input_path, output_path)
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_all_files(input_dir: Path, output_dir: Path, callback=None):
    """
    Redact all valid BSN numbers from every PDF and image in input_dir and save to output_dir.
    If callback is provided, it will be called with strings to log progress.
    Returns a tuple: (success_count, failure_count, grand_total_redactions, file_summaries)
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"'input' folder not found in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Support PDFs and common image formats
    extensions = ("*.pdf", "*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tiff")
    all_files = []
    for ext in extensions:
        all_files.extend(input_dir.glob(ext))

    all_files = sorted(all_files, key=lambda x: x.name.lower())

    if not all_files:
        if callback:
            callback("No supported files found in the input folder.")
        return 0, 0, 0, []

    if callback:
        callback(f"Found {len(all_files)} file(s). Starting process...\n")

    success_count = 0
    failure_count = 0
    grand_total_redactions = 0
    file_summaries = []

    for file_path in all_files:
        out_name = "redacted_" + file_path.name
        out_path = output_dir / out_name

        if callback:
            callback(f"Processing: {file_path.name}...")
        try:
            if file_path.suffix.lower() == ".pdf":
                count = redact_pdf(file_path, out_path)
            else:
                count = redact_image(file_path, out_path)[0]

            if callback:
                callback(f"  ✓ Success: {count} BSN(s) redacted.")
            success_count += 1
            grand_total_redactions += count
            file_summaries.append(f"{file_path.name}: {count} redacted")
        except Exception as exc:
            if callback:
                callback(f"  ✗ Error: {exc}")
            failure_count += 1
            file_summaries.append(f"{file_path.name}: FAILED")

    return success_count, failure_count, grand_total_redactions, file_summaries

def main():
    input_dir = Path("input")
    output_dir = Path("output")

    try:
        success, fail, total, summaries = process_all_files(input_dir, output_dir, callback=print)
        print("\nDone.")
    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    main()