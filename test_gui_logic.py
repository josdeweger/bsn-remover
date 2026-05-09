import unittest
from pathlib import Path
from gui import BSNRedactorGUI
import tkinter as tk

class TestBSNRedactorLogic(unittest.TestCase):
    def test_process_files_logic(self):
        # Mock the root and the log method to avoid needing a display
        root = tk.Tk()
        root.withdraw() # Hide window
        app = BSNRedactorGUI(root)
        
        # Use existing input and output folders
        input_dir = Path("input")
        output_dir = Path("output")
        
        # We can't easily call process_files because it uses self.log which 
        # interacts with a widget. We'll mock the log method.
        app.log = lambda msg: print(f"[LOG]: {msg}")
        
        # Execute the logic
        app.process_files(input_dir, output_dir)
        
        # Verify output files exist
        pdf_files = sorted(input_dir.glob("*.pdf"))
        for pdf in pdf_files:
            out_path = output_dir / ("redacted_" + pdf.name)
            self.assertTrue(out_path.exists(), f"Output file {out_path} should exist")

if __name__ == "__main__":
    unittest.main()
