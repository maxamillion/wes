"""Tests for validation indicator components."""

from unittest.mock import Mock, patch

import pytest
from PySide6.QtWidgets import QApplication

from wes.gui.unified_config.components.validation_indicator import (
    ValidatedLineEdit,
    ValidationIndicator,
)


class TestValidationIndicator:
    """Test ValidationIndicator functionality."""

    @pytest.fixture
    def app(self, qtbot):
        """Create QApplication for testing."""
        return QApplication.instance() or QApplication([])

    @pytest.fixture
    def indicator(self, qtbot):
        """Create a ValidationIndicator instance."""
        indicator = ValidationIndicator()
        qtbot.addWidget(indicator)
        indicator.show()
        return indicator

    def test_initial_state(self, indicator):
        """Test initial state is idle."""
        assert indicator.current_state == ValidationIndicator.State.IDLE
        assert indicator.icon_label.text() == ""

    def test_set_validating(self, indicator, qtbot):
        """Test setting validating state."""
        with qtbot.waitSignal(indicator.state_changed) as blocker:
            indicator.set_validating("Checking...")

        assert indicator.current_state == ValidationIndicator.State.VALIDATING
        assert indicator.icon_label.text() == "⟳"
        assert blocker.args[0] == ValidationIndicator.State.VALIDATING

    def test_set_valid(self, indicator, qtbot):
        """Test setting valid state."""
        with qtbot.waitSignal(indicator.state_changed) as blocker:
            indicator.set_valid("All good!")

        assert indicator.current_state == ValidationIndicator.State.VALID
        assert indicator.icon_label.text() == "✓"
        assert "green" in indicator.icon_label.styleSheet()
        assert blocker.args[0] == ValidationIndicator.State.VALID

    def test_set_invalid(self, indicator, qtbot):
        """Test setting invalid state."""
        with qtbot.waitSignal(indicator.state_changed) as blocker:
            indicator.set_invalid("Something wrong")

        assert indicator.current_state == ValidationIndicator.State.INVALID
        assert indicator.icon_label.text() == "✗"
        assert "red" in indicator.icon_label.styleSheet()
        assert blocker.args[0] == ValidationIndicator.State.INVALID

    def test_set_warning(self, indicator, qtbot):
        """Test setting warning state."""
        with qtbot.waitSignal(indicator.state_changed) as blocker:
            indicator.set_warning("Be careful")

        assert indicator.current_state == ValidationIndicator.State.WARNING
        assert indicator.icon_label.text() == "⚠"
        assert "orange" in indicator.icon_label.styleSheet()
        assert blocker.args[0] == ValidationIndicator.State.WARNING

    def test_clear(self, indicator):
        """Test clearing state."""
        # Set to valid first
        indicator.set_valid()
        assert indicator.current_state == ValidationIndicator.State.VALID

        # Clear
        indicator.clear()
        assert indicator.current_state == ValidationIndicator.State.IDLE
        assert indicator.icon_label.text() == ""

    def test_show_text(self, indicator):
        """Test showing text label."""
        indicator.set_state(ValidationIndicator.State.VALID, "Success!", show_text=True)

        assert indicator.text_label.isVisible()
        assert indicator.text_label.text() == "Success!"
        assert "green" in indicator.text_label.styleSheet()

    def test_hide_text(self, indicator, qtbot):
        """Test hiding text label."""
        # Show text first
        indicator.set_state(ValidationIndicator.State.VALID, "Success!", show_text=True)
        assert indicator.text_label.isVisible()

        # Clear the indicator which should hide the text
        indicator.clear()
        assert not indicator.text_label.isVisible()

    def test_tooltip(self, indicator):
        """Test tooltip is set correctly."""
        message = "This is a test message"
        indicator.set_valid(message)

        assert indicator.icon_label.toolTip() == message
        assert indicator.text_label.toolTip() == message

    @patch("wes.gui.unified_config.components.validation_indicator.QTimer")
    def test_spinning_animation(self, mock_timer_class, indicator):
        """Test spinning animation for validating state."""
        mock_timer = Mock()
        mock_timer_class.return_value = mock_timer

        # Set validating state
        indicator.set_validating()

        # Timer should be started
        mock_timer.start.assert_called_with(100)

        # Set valid state
        indicator.set_valid()

        # Timer should be stopped
        mock_timer.stop.assert_called()


class TestValidatedLineEdit:
    """Test ValidatedLineEdit functionality."""

    @pytest.fixture
    def app(self, qtbot):
        """Create QApplication for testing."""
        return QApplication.instance() or QApplication([])

    @pytest.fixture
    def line_edit(self, qtbot):
        """Create a ValidatedLineEdit instance."""
        line_edit = ValidatedLineEdit("Enter text...")
        qtbot.addWidget(line_edit)
        return line_edit

    def test_initial_state(self, line_edit):
        """Test initial state."""
        assert line_edit.text() == ""
        assert line_edit.line_edit.placeholderText() == "Enter text..."
        assert line_edit.indicator.current_state == ValidationIndicator.State.IDLE

    def test_password_mode(self, qtbot):
        """Test password mode."""
        from PySide6.QtWidgets import QLineEdit
        
        line_edit = ValidatedLineEdit("Password", password=True)
        qtbot.addWidget(line_edit)

        assert line_edit.line_edit.echoMode() == QLineEdit.Password

    def test_text_change_triggers_validation(self, line_edit, qtbot):
        """Test that text change triggers validation."""

        # Set a validator
        def validator(text):
            return len(text) >= 5, "Minimum 5 characters"

        line_edit.set_validator(validator)

        # Type text
        with qtbot.waitSignal(line_edit.text_changed) as blocker:
            line_edit.setText("Hi")

        assert blocker.args[0] == "Hi"

        # Should show validating state initially
        assert line_edit.indicator.current_state == ValidationIndicator.State.VALIDATING

        # Wait for validation to complete
        qtbot.wait(600)  # Wait for validation delay

        # Should be invalid (less than 5 chars)
        assert line_edit.indicator.current_state == ValidationIndicator.State.INVALID

    def test_valid_input(self, line_edit, qtbot):
        """Test valid input."""

        # Set a validator
        def validator(text):
            return len(text) >= 5, "Valid!"

        line_edit.set_validator(validator)

        # Type valid text
        with qtbot.waitSignal(line_edit.validation_changed) as blocker:
            line_edit.setText("Valid text")
            qtbot.wait(600)  # Wait for validation

        assert blocker.args[0] is True  # Valid
        assert line_edit.indicator.current_state == ValidationIndicator.State.VALID
        assert line_edit.is_valid()

    def test_invalid_input(self, line_edit, qtbot):
        """Test invalid input."""

        # Set a validator
        def validator(text):
            return False, "Always invalid"

        line_edit.set_validator(validator)

        # Type text
        with qtbot.waitSignal(line_edit.validation_changed) as blocker:
            line_edit.setText("Any text")
            qtbot.wait(600)  # Wait for validation

        assert blocker.args[0] is False  # Invalid
        assert line_edit.indicator.current_state == ValidationIndicator.State.INVALID
        assert not line_edit.is_valid()

    def test_validator_exception(self, line_edit, qtbot):
        """Test validator that throws exception."""

        # Set a validator that throws
        def bad_validator(text):
            raise ValueError("Test error")

        line_edit.set_validator(bad_validator)

        # Type text
        line_edit.setText("Text")
        qtbot.wait(600)  # Wait for validation

        # Should be invalid with error message
        assert line_edit.indicator.current_state == ValidationIndicator.State.INVALID
        assert "Validation error" in line_edit.indicator._message

    def test_empty_text_clears_validation(self, line_edit, qtbot):
        """Test that empty text clears validation."""
        # Set a validator
        line_edit.set_validator(lambda t: (True, "Valid"))

        # Type and then clear text
        line_edit.setText("Text")
        qtbot.wait(600)
        assert line_edit.indicator.current_state == ValidationIndicator.State.VALID

        line_edit.setText("")
        assert line_edit.indicator.current_state == ValidationIndicator.State.IDLE

    def test_validation_delay(self, line_edit, qtbot):
        """Test validation delay prevents too frequent validation."""
        # Set a validator that counts calls
        call_count = 0

        def counting_validator(text):
            nonlocal call_count
            call_count += 1
            return True, "Valid"

        line_edit.set_validator(counting_validator)
        line_edit.validation_delay = 200  # Shorter delay for testing

        # Type quickly
        line_edit.setText("A")
        line_edit.setText("AB")
        line_edit.setText("ABC")

        # Validation should not have run yet
        assert call_count == 0

        # Wait for validation
        qtbot.wait(300)

        # Should have validated only once
        assert call_count == 1
