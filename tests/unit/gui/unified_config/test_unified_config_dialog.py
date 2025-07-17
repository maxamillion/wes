"""Tests for the unified configuration dialog."""

from unittest.mock import Mock, patch

import pytest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from wes.core.config_manager import ConfigManager
from wes.gui.unified_config import UIMode, UnifiedConfigDialog


class TestUnifiedConfigDialog:
    """Test UnifiedConfigDialog functionality."""

    @pytest.fixture
    def app(self, qtbot):
        """Create QApplication for testing."""
        return QApplication.instance() or QApplication([])

    @pytest.fixture
    def config_manager(self):
        """Create a mock ConfigManager."""
        manager = Mock(spec=ConfigManager)
        manager.config = {}
        manager.retrieve_credential.return_value = None
        return manager

    @pytest.fixture
    def dialog(self, qtbot, config_manager):
        """Create a UnifiedConfigDialog instance."""
        dialog = UnifiedConfigDialog(config_manager)
        qtbot.addWidget(dialog)
        return dialog

    def test_mode_detection_empty_config(self, dialog, config_manager):
        """Test that empty config triggers wizard mode."""
        config_manager.config = {}
        dialog._detect_and_set_mode()
        assert dialog.current_mode == UIMode.WIZARD

    def test_mode_detection_incomplete_config(self, dialog, config_manager):
        """Test that incomplete config triggers guided mode."""
        config_manager.config = {
            "jira": {
                "url": "https://example.atlassian.net",
                "username": "user@example.com",
                "api_token": "test-token",
            }
            # Missing google and gemini
        }
        dialog._detect_and_set_mode()
        assert dialog.current_mode == UIMode.GUIDED

    def test_mode_detection_complete_config(self, dialog, config_manager):
        """Test that complete config triggers direct mode."""
        config_manager.config = {
            "jira": {
                "url": "https://example.atlassian.net",
                "username": "user@example.com",
                "api_token": "test-token",
            },
            "google": {"credentials_path": "/path/to/creds.json"},
            "gemini": {"api_key": "AIzaSyTest123456789"},
        }
        dialog._detect_and_set_mode()
        assert dialog.current_mode == UIMode.DIRECT

    def test_mode_switching(self, dialog, qtbot):
        """Test switching between modes."""
        # Switch to wizard mode
        dialog.set_mode(UIMode.WIZARD)
        assert dialog.current_mode == UIMode.WIZARD
        assert dialog.stack.currentIndex() == 0

        # Switch to guided mode
        dialog.set_mode(UIMode.GUIDED)
        assert dialog.current_mode == UIMode.GUIDED
        assert dialog.stack.currentIndex() == 1

        # Switch to direct mode
        dialog.set_mode(UIMode.DIRECT)
        assert dialog.current_mode == UIMode.DIRECT
        assert dialog.stack.currentIndex() == 2

    def test_mode_labels(self, dialog):
        """Test that mode labels are set correctly."""
        # Wizard mode
        dialog.set_mode(UIMode.WIZARD)
        assert "Welcome" in dialog.mode_label.text()

        # Guided mode
        dialog.set_mode(UIMode.GUIDED)
        assert "need configuration" in dialog.mode_label.text()

        # Direct mode
        dialog.set_mode(UIMode.DIRECT)
        assert "Settings" in dialog.mode_label.text()

    def test_button_updates_for_modes(self, dialog):
        """Test that buttons update based on mode."""
        # Wizard mode - should have Cancel button
        dialog.set_mode(UIMode.WIZARD)
        assert dialog.button_box.button(QDialogButtonBox.Cancel) is not None

        # Direct mode - should have Apply, Save, Cancel
        dialog.set_mode(UIMode.DIRECT)
        assert dialog.button_box.button(QDialogButtonBox.Apply) is not None
        assert dialog.button_box.button(QDialogButtonBox.Save) is not None
        assert dialog.button_box.button(QDialogButtonBox.Cancel) is not None

    def test_configuration_save(self, dialog, config_manager):
        """Test saving configuration."""
        # Mock the current widget to return test config
        mock_widget = Mock()
        mock_widget.get_configuration.return_value = {
            "jira": {"url": "https://test.com"}
        }
        dialog.stack.currentWidget = Mock(return_value=mock_widget)

        # Mock validation to pass
        dialog._validate_configuration = Mock(return_value=True)

        # Save configuration
        result = dialog._save_configuration()
        assert result is True

        # Check that config manager was updated
        config_manager.update_service_config.assert_called()
        config_manager.save_config.assert_called()

    def test_validation_before_save(self, dialog):
        """Test that validation runs before saving."""
        # Mock the current widget
        mock_widget = Mock()
        mock_widget.get_configuration.return_value = {}
        dialog.stack.currentWidget = Mock(return_value=mock_widget)

        # Mock validation to fail
        dialog._validate_configuration = Mock(return_value=False)

        # Try to save
        result = dialog._save_configuration()
        assert result is False

    def test_dirty_state_tracking(self, dialog, qtbot):
        """Test that dirty state is tracked."""
        assert dialog.dirty is False

        # Simulate configuration change
        dialog._on_config_changed()
        assert dialog.dirty is True

        # Save should clear dirty state
        dialog._save_configuration = Mock(return_value=True)
        dialog._apply_changes()
        assert dialog.dirty is False

    def test_close_with_unsaved_changes(self, dialog, qtbot, monkeypatch):
        """Test close dialog with unsaved changes."""
        dialog.dirty = True

        # Mock QMessageBox to return Save
        mock_reply = QDialogButtonBox.Save
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.question", lambda *args, **kwargs: mock_reply
        )

        # Mock save to succeed
        dialog._save_configuration = Mock(return_value=True)

        # Trigger close event
        event = Mock()
        dialog.closeEvent(event)

        # Should save and accept
        dialog._save_configuration.assert_called_once()
        event.accept.assert_called_once()

    def test_mode_switch_button_in_wizard(self, dialog):
        """Test mode switch button appears in wizard mode."""
        dialog.set_mode(UIMode.WIZARD)
        assert dialog.mode_switch_button.isVisible()
        assert "Skip" in dialog.mode_switch_button.text()

    def test_wizard_completion(self, dialog):
        """Test wizard completion flow."""
        dialog.set_mode(UIMode.WIZARD)

        # Mock save configuration
        dialog._save_configuration = Mock(return_value=True)

        # Simulate wizard completion
        dialog._on_wizard_complete()

        # Should save and accept dialog
        dialog._save_configuration.assert_called_once()

    @patch("wes.gui.unified_config.unified_config_dialog.WizardView")
    def test_lazy_widget_creation(self, mock_wizard_class, dialog):
        """Test that mode widgets are created lazily."""
        # Initially, wizard widget should be None
        assert dialog.wizard_widget is None

        # Switch to wizard mode
        dialog.set_mode(UIMode.WIZARD)

        # Now wizard widget should be created
        assert dialog.wizard_widget is not None
        mock_wizard_class.assert_called_once()

    def test_configuration_complete_signal(self, dialog, qtbot):
        """Test that configuration_complete signal is emitted."""
        # Set up signal spy
        with qtbot.waitSignal(dialog.configuration_complete) as blocker:
            # Mock successful save
            dialog.stack.currentWidget = Mock()
            dialog.stack.currentWidget().get_configuration.return_value = {
                "test": "config"
            }
            dialog._validate_configuration = Mock(return_value=True)
            dialog.config_manager.update_service_config = Mock()
            dialog.config_manager.save_config = Mock()

            # Save configuration
            dialog._save_configuration()

        # Check signal was emitted with config
        assert blocker.args[0] == {"test": "config"}
