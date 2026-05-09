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
# PDF redaction
# ---------------------------------------------------------------------------

def redact_pdf(input_path: Path, output_path: Path) -> int:
    """
    Open *input_path*, redact all valid BSN numbers, write to *output_path*.
    Returns the number of redactions applied across the whole document.
    """
    doc = fitz.open(str(input_path))
    total_redactions = 0

    for page in doc:
        # Use "words" instead of "rawdict" for more stable bounding boxes.
        # get_text("words") returns (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        words = page.get_text("words")

        if not words:
            continue

        # Build the full text and a mapping from character index to word index
        full_text = ""
        char_to_word = []

        for i, w in enumerate(words):
            word_text = w[4]
            for _ in range(len(word_text)):
                char_to_word.append(i)
            full_text += word_text + " "
            char_to_word.append(i) # The space

        for start, end, raw in extract_bsn_candidates(full_text):
            # Identify which words overlap with the match
            # We clamp indices to avoid out-of-bounds
            word_start_idx = char_to_word[min(start, len(char_to_word)-1)]
            word_end_idx = char_to_word[min(end-1, len(char_to_word)-1)]

            # Redact each word in the range
            for i in range(word_start_idx, word_end_idx + 1):
                w = words[i]
                rect = fitz.Rect(w[0], w[1], w[2], w[3])

                # Add a small vertical padding
                rect = rect + (-1, -2, 1, 2)

                page.add_redact_annot(rect, fill=(0, 0, 0))
                total_redactions += 1

        page.apply_redactions()

    doc.save(str(output_path), garbage=4, deflate=True)
    doc.close()
    return total_redactions


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_all_pdfs(input_dir: Path, output_dir: Path, callback=None):
    """
    Redact all valid BSN numbers from every PDF in input_dir and save to output_dir.
    If callback is provided, it will be called with strings to log progress.
    Returns a tuple: (success_count, failure_count, grand_total_redactions, file_summaries)
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"'input' folder not found in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        if callback:
            callback("No PDF files found in the input folder.")
        return 0, 0, 0, []

    if callback:
        callback(f"Found {len(pdf_files)} PDF file(s). Starting process...\n")

    success_count = 0
    failure_count = 0
    grand_total_redactions = 0
    file_summaries = []

    for pdf_path in pdf_files:
        out_name = "redacted_" + pdf_path.name
        out_path = output_dir / out_name

        if callback:
            callback(f"Processing: {pdf_path.name}...")
        try:
            count = redact_pdf(pdf_path, out_path)
            if callback:
                callback(f"  ✓ Success: {count} BSN(s) redacted.")
            success_count += 1
            grand_total_redactions += count
            file_summaries.append(f"{pdf_path.name}: {count} redacted")
        except Exception as exc:
            if callback:
                callback(f"  ✗ Error: {exc}")
            failure_count += 1
            file_summaries.append(f"{pdf_path.name}: FAILED")

    return success_count, failure_count, grand_total_redactions, file_summaries

def main():
    input_dir = Path("input")
    output_dir = Path("output")

    try:
        success, fail, total, summaries = process_all_pdfs(input_dir, output_dir, callback=print)
        print("\nDone.")
    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    main()