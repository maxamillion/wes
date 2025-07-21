"""Dialog to review Jira data before sending to Gemini."""

import json
import logging
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextEdit,
    QVBoxLayout,
)

class JiraReviewDialog(QDialog):
    """A dialog to display and confirm Jira data before processing."""

    def __init__(self, jira_data, parent=None):
        super().__init__(parent)
        self.jira_data = jira_data
        self.logger = logging.getLogger(__name__)
        self.init_ui()
        self.display_data()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Review Jira Data")
        self.setGeometry(200, 200, 700, 600)
        self.setModal(True)

        layout = QVBoxLayout(self)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        layout.addWidget(self.text_area)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Ok).setText("Proceed to Summary")

        layout.addWidget(button_box)

    def display_data(self):
        """Formats and displays the Jira data, truncating if necessary."""
        MAX_DISPLAY_ITEMS = 50
        MAX_DISPLAY_CHARS = 65536  # 64k characters

        try:
            num_items = len(self.jira_data)
            self.logger.info(f"Reviewing {num_items} Jira items.")
            data_to_display = self.jira_data
            truncation_message = ""

            if num_items > MAX_DISPLAY_ITEMS:
                data_to_display = self.jira_data[:MAX_DISPLAY_ITEMS]
                truncation_message = (
                    f"\n\n... and {num_items - MAX_DISPLAY_ITEMS} more items (truncated for display)."
                )
                self.logger.info(f"Truncating review data to {MAX_DISPLAY_ITEMS} items.")

            # Add default=str to handle non-serializable types like datetime
            formatted_text = json.dumps(data_to_display, indent=4, default=str)

            if len(formatted_text) > MAX_DISPLAY_CHARS:
                formatted_text = formatted_text[:MAX_DISPLAY_CHARS]
                if not truncation_message:
                    truncation_message = "\n\n..."
                truncation_message += "\n(Content truncated due to length)."
                self.logger.info(f"Truncating review text to {MAX_DISPLAY_CHARS} characters.")

            self.text_area.setPlainText(formatted_text + truncation_message)

        except TypeError as e:
            self.logger.error(f"Failed to serialize Jira data for review: {e}")
            # Truncate original data for display in case of error
            self.text_area.setPlainText(f'Error formatting data: {e}\n\n{str(self.jira_data)[:1000]}...')