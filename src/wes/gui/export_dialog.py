"""Export dialog for saving summaries in various formats."""

from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.export_manager import ExportManager
from ..utils.exceptions import ExportError
from ..utils.logging_config import get_logger


class ExportDialog(QDialog):
    """Dialog for exporting executive summaries.

    Provides options to:
    - Preview the summary
    - Select export format
    - Save to file or copy to clipboard
    """

    # Signals
    export_complete = Signal(str, str)  # format, filepath

    def __init__(self, summary: Dict[str, Any], parent: Optional[QWidget] = None):
        """Initialize export dialog.

        Args:
            summary: Summary data to export
            parent: Parent widget
        """
        super().__init__(parent)

        self.logger = get_logger(__name__)
        self.summary = summary
        self.export_manager = ExportManager()

        self.setWindowTitle("Export Executive Summary")
        self.setModal(True)
        self.setMinimumSize(800, 600)

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Export Executive Summary")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Preview section
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlainText(self.summary.get("content", ""))
        preview_layout.addWidget(self.preview_text)

        layout.addWidget(preview_group)

        # Export options
        options_group = QGroupBox("Export Options")
        options_layout = QVBoxLayout(options_group)

        # Format selection
        format_label = QLabel("Select export format:")
        options_layout.addWidget(format_label)

        self.format_group = QButtonGroup()

        formats = [
            (
                "Markdown (.md)",
                "markdown",
                "Best for documentation and version control",
            ),
            ("HTML (.html)", "html", "Web-viewable with professional styling"),
            ("PDF (.pdf)", "pdf", "Professional format for sharing"),
            ("Plain Text (.txt)", "text", "Universal compatibility"),
            ("Copy to Clipboard", "clipboard", "Quick paste into any application"),
        ]

        for i, (label, value, description) in enumerate(formats):
            radio_layout = QHBoxLayout()

            radio = QRadioButton(label)
            radio.setProperty("format", value)
            self.format_group.addButton(radio, i)
            radio_layout.addWidget(radio)

            desc_label = QLabel(f" - {description}")
            desc_label.setStyleSheet("color: #666; font-size: 11px;")
            radio_layout.addWidget(desc_label)
            radio_layout.addStretch()

            options_layout.addLayout(radio_layout)

            # Select markdown by default
            if value == "markdown":
                radio.setChecked(True)

        layout.addWidget(options_group)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.export_button = QPushButton("Export")
        self.export_button.setStyleSheet(
            """
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """
        )
        self.export_button.clicked.connect(self.export_summary)
        button_layout.addWidget(self.export_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def get_selected_format(self) -> str:
        """Get the currently selected export format.

        Returns:
            Selected format string
        """
        checked_button = self.format_group.checkedButton()
        if checked_button:
            return checked_button.property("format")
        return "markdown"

    def export_summary(self):
        """Export the summary in the selected format."""
        format = self.get_selected_format()

        try:
            if format == "clipboard":
                # Copy to clipboard
                success = self.export_manager.copy_to_clipboard(self.summary)
                if success:
                    QMessageBox.information(
                        self, "Success", "Summary copied to clipboard!"
                    )
                    self.export_complete.emit(format, "")
                    self.accept()
            else:
                # Get file path
                file_extensions = {
                    "markdown": ("Markdown Files (*.md)", ".md"),
                    "html": ("HTML Files (*.html)", ".html"),
                    "pdf": ("PDF Files (*.pdf)", ".pdf"),
                    "text": ("Text Files (*.txt)", ".txt"),
                }

                filter_text, extension = file_extensions.get(
                    format, ("All Files (*)", "")
                )

                # Suggest filename
                from datetime import datetime

                date_str = datetime.now().strftime("%Y-%m-%d")
                suggested_name = f"executive_summary_{date_str}{extension}"

                filepath, _ = QFileDialog.getSaveFileName(
                    self, "Save Executive Summary", suggested_name, filter_text
                )

                if filepath:
                    # Ensure correct extension
                    filepath = Path(filepath)
                    if not filepath.suffix:
                        filepath = filepath.with_suffix(extension)

                    # Export file
                    success = self.export_manager.export_summary(
                        self.summary, format, filepath
                    )

                    if success:
                        QMessageBox.information(
                            self, "Success", f"Summary exported to:\n{filepath}"
                        )
                        self.export_complete.emit(format, str(filepath))
                        self.accept()

        except ExportError as e:
            QMessageBox.critical(
                self, "Export Failed", f"Failed to export summary:\n{str(e)}"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error during export: {e}")
            QMessageBox.critical(
                self, "Export Failed", f"An unexpected error occurred:\n{str(e)}"
            )


class QuickExportWidget(QWidget):
    """Quick export widget for main window integration.

    Provides quick access buttons for common export operations.
    """

    # Signals
    export_requested = Signal(str)  # format

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize quick export widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Quick export buttons
        self.save_button = QPushButton("Save")
        self.save_button.setToolTip("Save summary to file")
        self.save_button.clicked.connect(lambda: self.export_requested.emit("save"))
        layout.addWidget(self.save_button)

        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.setToolTip("Copy summary to clipboard")
        self.copy_button.clicked.connect(
            lambda: self.export_requested.emit("clipboard")
        )
        layout.addWidget(self.copy_button)

        self.pdf_button = QPushButton("Export PDF")
        self.pdf_button.setToolTip("Export as PDF document")
        self.pdf_button.clicked.connect(lambda: self.export_requested.emit("pdf"))
        layout.addWidget(self.pdf_button)

        layout.addStretch()
