import sys
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog
)
from PyQt6.QtCore import QObject, pyqtSignal, QThread, Qt
from PyQt6.QtGui import QFont

from main import redact_pdf

class RedactionWorker(QObject):
    """
    Handles the BSN redaction logic in a separate thread to keep the UI responsive.
    """
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, input_dir, output_dir):
        super().__init__()
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)

    def run(self):
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            pdf_files = sorted(self.input_dir.glob("*.pdf"))

            if not pdf_files:
                self.log_signal.emit("No PDF files found in the input folder.")
                self.finished_signal.emit()
                return

            self.log_signal.emit(f"Found {len(pdf_files)} PDF file(s). Starting process...\n")

            total_files = len(pdf_files)
            success_count = 0
            failure_count = 0
            grand_total_redactions = 0
            file_summaries = []

            for pdf_path in pdf_files:
                out_name = "redacted_" + pdf_path.name
                out_path = self.output_dir / out_name

                self.log_signal.emit(f"Processing: {pdf_path.name}...")
                try:
                    count = redact_pdf(pdf_path, out_path)
                    self.log_signal.emit(f"  ✓ Success: {count} BSN(s) redacted.")
                    success_count += 1
                    grand_total_redactions += count
                    file_summaries.append(f"{pdf_path.name}: {count} redacted")
                except Exception as e:
                    self.log_signal.emit(f"  ✗ Error: {str(e)}")
                    failure_count += 1
                    file_summaries.append(f"{pdf_path.name}: FAILED")

            # Final Summary
            summary = "\n" + "="*30 + "\nFINAL SUMMARY\n" + "="*30 + "\n"
            summary += f"Total PDFs processed: {total_files}\n"
            summary += f"Successfully redacted: {success_count}\n"
            summary += f"Failures: {failure_count}\n"
            summary += f"Total redactions made: {grand_total_redactions}\n\n"
            summary += "Details per file:\n"
            summary += "\n".join(file_summaries)
            summary += "\n" + "="*30 + "\n\nDone."

            self.log_signal.emit(summary)

        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            self.finished_signal.emit()

class BSNRedactorWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("BSN Redactor")
        self.setFixedSize(600, 550)

        # --- Styling ---
        # We use QSS (Qt Style Sheets) to ensure consistent cross-platform visibility
        self.bg_color = "#D3D3D3"
        self.style_sheet = f"""
            QMainWindow, QWidget {{
                background-color: {self.bg_color};
            }}
            QLabel {{
                color: black;
                font-weight: bold;
                background: transparent;
            }}
            QLineEdit {{
                background-color: white;
                color: black;
                border: 1px solid #A0A0A0;
                padding: 4px;
                font-size: 13px;
            }}
            QPushButton {{
                background-color: #F0F0F0;
                color: black;
                border: 1px solid #A0A0A0;
                padding: 5px 15px;
                border-radius: 3px;
            }}
            QPushButton:pressed {{
                background-color: #D0D0D0;
            }}
            #StartButton {{
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 10px 20px;
                border-radius: 5px;
            }}
            #StartButton:disabled {{
                background-color: #A0A0A0;
                color: #EEEEEE;
            }}
            QTextEdit {{
                background-color: white;
                color: black;
                border: 1px solid #A0A0A0;
                font-family: 'Menlo', 'Consolas', 'Monospace';
                font-size: 12px;
            }}
        """
        self.setStyleSheet(self.style_sheet)

        # --- Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Input Folder
        input_label = QLabel("Input Folder:")
        main_layout.addWidget(input_label)

        input_hbox = QHBoxLayout()
        self.input_entry = QLineEdit()
        self.input_entry.setPlaceholderText("Select input folder...")
        self.btn_browse_input = QPushButton("Browse")
        self.btn_browse_input.clicked.connect(self.browse_input)
        input_hbox.addWidget(self.input_entry)
        input_hbox.addWidget(self.btn_browse_input)
        main_layout.addLayout(input_hbox)

        # Output Folder
        output_label = QLabel("Output Folder:")
        main_layout.addWidget(output_label)

        output_hbox = QHBoxLayout()
        self.output_entry = QLineEdit()
        self.output_entry.setPlaceholderText("Select output folder...")
        self.btn_browse_output = QPushButton("Browse")
        self.btn_browse_output.clicked.connect(self.browse_output)
        output_hbox.addWidget(self.output_entry)
        output_hbox.addWidget(self.btn_browse_output)
        main_layout.addLayout(output_hbox)

        # Start Button
        self.start_button = QPushButton("Start Redaction")
        self.start_button.setObjectName("StartButton")
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.clicked.connect(self.start_redaction)
        main_layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # Log Area
        log_label = QLabel("Progress & Summary:")
        main_layout.addWidget(log_label)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        main_layout.addWidget(self.log_area)

        # Threading Setup
        self.thread = None
        self.worker = None

    def browse_input(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            self.input_entry.setText(folder)

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_entry.setText(folder)

    def log(self, message):
        self.log_area.append(message)

    def start_redaction(self):
        input_path = self.input_entry.text().strip()
        output_path = self.output_entry.text().strip()

        if not input_path or not output_path:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Input Required", "Please select both input and output folders.")
            return

        # We use standard QMessageBox for alerts
        from PyQt6.QtWidgets import QMessageBox
        if not Path(input_path).is_dir():
            QMessageBox.critical(self, "Invalid Path", "The input path is not a valid directory.")
            return

        # UI State
        self.start_button.setEnabled(False)
        self.log_area.clear()

        # Setup Thread and Worker
        self.thread = QThread()
        self.worker = RedactionWorker(input_path, output_path)
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.log)
        self.worker.error_signal.connect(self.handle_critical_error)
        self.worker.finished_signal.connect(self.thread.quit)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.on_finished)

        self.thread.start()

    def handle_critical_error(self, error_msg):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Critical Error", f"An unexpected error occurred:\n{error_msg}")

    def on_finished(self):
        self.start_button.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BSNRedactorWindow()
    window.show()
    sys.exit(app.exec())
