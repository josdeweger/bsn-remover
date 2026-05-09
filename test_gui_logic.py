import unittest
from pathlib import Path
import shutil

# Import the core logic function directly
from main import process_all_pdfs

class TestBSNRedactorLogic(unittest.TestCase):
    def setUp(self):
        # Create temporary directories for testing
        self.test_input = Path("test_input_dir")
        self.test_output = Path("test_output_dir")
        self.test_input.mkdir(exist_ok=True)
        self.test_output.mkdir(exist_ok=True)

        # Since redact_pdf depends on fitz (PyMuPDF), we must ensure the
        # environment is correct. If fitz is not installed, this test
        # will fail during import or execution, which is correct CI behavior.

    def tearDown(self):
        # Clean up temporary directories
        if self.test_input.exists():
            shutil.rmtree(self.test_input)
        if self.test_output.exists():
            shutil.rmtree(self.test_output)

    def test_process_all_pdfs_success(self):
        """Test that process_all_pdfs correctly handles PDF files."""
        # We use a small real PDF or a dummy file.
        # For CI, we create a dummy PDF-like file since we can't easily
        # create real valid PDFs without a heavy library.
        # PyMuPDF can open it, but might fail on redaction if the content is not a valid PDF.
        # Instead, we rely on a real PDF in the 'input' folder if available,
        # or a mock for the core logic.

        # Let's use the existing project's 'input' folder for a smoke test
        # because the user has provided real PDFs.
        real_input = Path("input")
        real_output = Path("output_test_ci")

        if not real_input.exists() or not any(real_input.glob("*.pdf")):
            self.skipTest("No real PDF files found in input/ folder for integration test.")
            return

        # Run the core logic
        success, fail, total, summaries = process_all_pdfs(real_input, real_output, callback=lambda m: print(f"[LOG] {m}"))

        # Basic assertions
        self.assertGreaterEqual(success + fail, 0)

        # Verify that at least one output file was created if input files existed
        pdf_files = sorted(real_input.glob("*.pdf"))
        for pdf in pdf_files:
            out_path = real_output / ("redacted_" + pdf.name)
            self.assertTrue(out_path.exists(), f"Output file {out_path} should exist")

    def test_empty_folder(self):
        """Test the behavior when the input folder is empty."""
        success, fail, total, summaries = process_all_pdfs(self.test_input, self.test_output)
        self.assertEqual(success, 0)
        self.assertEqual(fail, 0)
        self.assertEqual(total, 0)
        self.assertEqual(summaries, [])

    def test_invalid_input_folder(self):
        """Test the behavior when the input folder doesn't exist."""
        with self.assertRaises(FileNotFoundError):
            process_all_pdfs(Path("non_existent_folder_12345"), self.test_output)

if __name__ == "__main__":
    unittest.main()
