"""Common dialog utilities for consistent user interaction.

This module provides reusable dialog functions to improve maintainability
and ensure consistent user experience across the application.
"""

from enum import Enum
from typing import Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget


class MessageType(Enum):
    """Enumeration of message types for dialogs."""

    INFO = "information"
    WARNING = "warning"
    ERROR = "error"
    QUESTION = "question"
    SUCCESS = "success"


class DialogManager:
    """Manages common dialog patterns for better maintainability."""

    @staticmethod
    def show_message(
        parent: Optional[QWidget],
        title: str,
        message: str,
        message_type: MessageType = MessageType.INFO,
        details: Optional[str] = None,
    ) -> None:
        """Show a message dialog with consistent styling.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            message: Main message text.
            message_type: Type of message (info, warning, error, etc.).
            details: Optional detailed message text.
        """
        if message_type == MessageType.INFO:
            icon = QMessageBox.Icon.Information
            if title.lower() == "success":  # Use success styling for info messages about success
                title = "Success"
        elif message_type == MessageType.WARNING:
            icon = QMessageBox.Icon.Warning
        elif message_type == MessageType.ERROR:
            icon = QMessageBox.Icon.Critical
        else:
            icon = QMessageBox.Icon.Information

        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon)

        if details:
            msg_box.setDetailedText(details)

        msg_box.exec()

    @staticmethod
    def show_error(
        parent: Optional[QWidget],
        title: str,
        message: str,
        details: Optional[str] = None,
    ) -> None:
        """Show an error message dialog.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            message: Error message.
            details: Optional error details or stack trace.
        """
        DialogManager.show_message(parent, title, message, MessageType.ERROR, details)

    @staticmethod
    def show_warning(
        parent: Optional[QWidget],
        title: str,
        message: str,
        details: Optional[str] = None,
    ) -> None:
        """Show a warning message dialog.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            message: Warning message.
            details: Optional warning details.
        """
        DialogManager.show_message(parent, title, message, MessageType.WARNING, details)

    @staticmethod
    def show_info(
        parent: Optional[QWidget],
        title: str,
        message: str,
        details: Optional[str] = None,
    ) -> None:
        """Show an information message dialog.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            message: Information message.
            details: Optional additional information.
        """
        DialogManager.show_message(parent, title, message, MessageType.INFO, details)

    @staticmethod
    def show_success(
        parent: Optional[QWidget],
        title: str,
        message: str,
        details: Optional[str] = None,
    ) -> None:
        """Show a success message dialog.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title (defaults to "Success").
            message: Success message.
            details: Optional additional details.
        """
        DialogManager.show_message(parent, title, message, MessageType.SUCCESS, details)

    @staticmethod
    def ask_question(
        parent: Optional[QWidget],
        title: str,
        message: str,
        default_yes: bool = False,
        details: Optional[str] = None,
    ) -> bool:
        """Show a yes/no question dialog.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            message: Question text.
            default_yes: Whether "Yes" should be the default button.
            details: Optional additional details.

        Returns:
            bool: True if user clicked Yes, False otherwise.
        """
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if default_yes:
            msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        else:
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        if details:
            msg_box.setDetailedText(details)

        return msg_box.exec() == QMessageBox.StandardButton.Yes

    @staticmethod
    def ask_confirmation(
        parent: Optional[QWidget],
        title: str,
        message: str,
        confirm_text: str = "Continue",
        cancel_text: str = "Cancel",
        dangerous: bool = False,
    ) -> bool:
        """Show a confirmation dialog with custom button text.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            message: Confirmation message.
            confirm_text: Text for the confirm button.
            cancel_text: Text for the cancel button.
            dangerous: Whether this is a dangerous action (shows warning icon).

        Returns:
            bool: True if user confirmed, False otherwise.
        """
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Warning if dangerous else QMessageBox.Icon.Question)

        confirm_btn = msg_box.addButton(confirm_text, QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = msg_box.addButton(cancel_text, QMessageBox.ButtonRole.RejectRole)

        msg_box.setDefaultButton(cancel_btn if dangerous else confirm_btn)

        msg_box.exec()
        return msg_box.clickedButton() == confirm_btn

    @staticmethod
    def ask_save_changes(
        parent: Optional[QWidget],
        title: str = "Unsaved Changes",
        message: str = "You have unsaved changes. Do you want to save before closing?",
    ) -> Optional[bool]:
        """Show a save changes dialog.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            message: Message about unsaved changes.

        Returns:
            Optional[bool]: True to save, False to discard, None to cancel.
        """
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.Cancel)

        result = msg_box.exec()

        if result == QMessageBox.StandardButton.Save:
            return True
        elif result == QMessageBox.StandardButton.Discard:
            return False
        else:
            return None


class ValidationDialog:
    """Provides common validation feedback patterns."""

    @staticmethod
    def show_validation_error(
        parent: Optional[QWidget],
        field_name: str,
        error_message: str,
        suggestion: Optional[str] = None,
    ) -> None:
        """Show a validation error dialog with consistent formatting.

        Args:
            parent: Parent widget for the dialog.
            field_name: Name of the field that failed validation.
            error_message: Specific validation error.
            suggestion: Optional suggestion for fixing the error.
        """
        message = f"Invalid {field_name}:\n{error_message}"

        if suggestion:
            message += f"\n\n{suggestion}"

        DialogManager.show_error(parent, "Validation Error", message)

    @staticmethod
    def show_missing_fields(
        parent: Optional[QWidget], missing_fields: list[str]
    ) -> None:
        """Show a dialog for missing required fields.

        Args:
            parent: Parent widget for the dialog.
            missing_fields: List of missing field names.
        """
        if len(missing_fields) == 1:
            message = f"Please fill in the required field: {missing_fields[0]}"
        else:
            fields_list = "\n".join(f"• {field}" for field in missing_fields)
            message = f"Please fill in the following required fields:\n\n{fields_list}"

        DialogManager.show_warning(parent, "Required Fields Missing", message)


class FileDialogManager:
    """Manages file dialog operations with consistent behavior."""

    @staticmethod
    def get_open_file_path(
        parent: Optional[QWidget],
        title: str = "Open File",
        directory: str = "",
        filter: str = "All Files (*)",
        selected_filter: Optional[str] = None,
    ) -> Optional[str]:
        """Show file open dialog and return selected file path.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            directory: Starting directory.
            filter: File filter string (e.g., "JSON Files (*.json);;All Files (*)").
            selected_filter: Initially selected filter.

        Returns:
            Optional[str]: Selected file path or None if cancelled.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            parent, title, directory, filter, selected_filter or ""
        )
        return file_path if file_path else None

    @staticmethod
    def get_save_file_path(
        parent: Optional[QWidget],
        title: str = "Save File",
        directory: str = "",
        filter: str = "All Files (*)",
        selected_filter: Optional[str] = None,
    ) -> Optional[str]:
        """Show file save dialog and return selected file path.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            directory: Starting directory.
            filter: File filter string.
            selected_filter: Initially selected filter.

        Returns:
            Optional[str]: Selected file path or None if cancelled.
        """
        file_path, _ = QFileDialog.getSaveFileName(
            parent, title, directory, filter, selected_filter or ""
        )
        return file_path if file_path else None

    @staticmethod
    def get_directory_path(
        parent: Optional[QWidget], title: str = "Select Directory", directory: str = ""
    ) -> Optional[str]:
        """Show directory selection dialog and return selected path.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            directory: Starting directory.

        Returns:
            Optional[str]: Selected directory path or None if cancelled.
        """
        dir_path = QFileDialog.getExistingDirectory(
            parent,
            title,
            directory,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        return dir_path if dir_path else None

    @staticmethod
    def get_json_file_path(
        parent: Optional[QWidget], title: str = "Select JSON File", directory: str = ""
    ) -> Optional[str]:
        """Show dialog specifically for JSON files.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            directory: Starting directory.

        Returns:
            Optional[str]: Selected JSON file path or None if cancelled.
        """
        return FileDialogManager.get_open_file_path(
            parent=parent,
            title=title,
            directory=directory,
            filter="JSON Files (*.json);;All Files (*)"
        )
