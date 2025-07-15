"""Real-time validation indicator component."""

from typing import Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class ValidationIndicator(QWidget):
    """
    Visual indicator for field validation status with animations
    and helpful tooltips.
    """

    # Validation states
    class State:
        IDLE = "idle"
        VALIDATING = "validating"
        VALID = "valid"
        INVALID = "invalid"
        WARNING = "warning"

    state_changed = Signal(str)  # Emits new state

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_state = self.State.IDLE
        self._message = ""
        self._init_ui()
        self._setup_animations()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Status icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(16, 16)
        layout.addWidget(self.icon_label)

        # Status text (optional, hidden by default)
        self.text_label = QLabel()
        self.text_label.hide()
        layout.addWidget(self.text_label)

        layout.addStretch()

        # Set initial state
        self._update_display()

    def _setup_animations(self):
        """Setup fade animations for smooth transitions."""
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)

    def set_state(self, state: str, message: str = "", show_text: bool = False):
        """
        Set the validation state.

        Args:
            state: One of the State constants
            message: Tooltip/text message
            show_text: Whether to show text label
        """
        if state == self.current_state and message == self._message:
            return

        self.current_state = state
        self._message = message

        # Show/hide text label
        if show_text and message:
            self.text_label.setText(message)
            self.text_label.show()
        else:
            self.text_label.hide()

        # Update display with animation
        self._animate_transition()
        self.state_changed.emit(state)

    def _update_display(self):
        """Update the visual display based on current state."""
        styles = {
            self.State.IDLE: {"icon": "", "color": "transparent", "tooltip": ""},
            self.State.VALIDATING: {
                "icon": "⟳",
                "color": "#666",
                "tooltip": "Validating...",
            },
            self.State.VALID: {
                "icon": "✓",
                "color": "green",
                "tooltip": self._message or "Valid",
            },
            self.State.INVALID: {
                "icon": "✗",
                "color": "red",
                "tooltip": self._message or "Invalid",
            },
            self.State.WARNING: {
                "icon": "⚠",
                "color": "orange",
                "tooltip": self._message or "Warning",
            },
        }

        style = styles.get(self.current_state, styles[self.State.IDLE])

        # Update icon
        self.icon_label.setText(style["icon"])
        self.icon_label.setStyleSheet(f"color: {style['color']}; font-size: 14px;")

        # Update text color if visible
        if self.text_label.isVisible():
            self.text_label.setStyleSheet(f"color: {style['color']};")

        # Update tooltip
        tooltip = style["tooltip"]
        self.icon_label.setToolTip(tooltip)
        self.text_label.setToolTip(tooltip)

    def _animate_transition(self):
        """Animate the state transition."""
        # Quick fade effect
        self.fade_animation.setStartValue(0.7)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()

        # Update display
        self._update_display()

        # For validating state, add spinning animation
        if self.current_state == self.State.VALIDATING:
            self._start_spinning()
        else:
            self._stop_spinning()

    def _start_spinning(self):
        """Start spinning animation for validating state."""
        if not hasattr(self, "spin_timer"):
            self.spin_timer = QTimer()
            self.spin_timer.timeout.connect(self._rotate_icon)

        self.spin_angle = 0
        self.spin_timer.start(100)  # Update every 100ms

    def _stop_spinning(self):
        """Stop spinning animation."""
        if hasattr(self, "spin_timer"):
            self.spin_timer.stop()

    def _rotate_icon(self):
        """Rotate the validating icon."""
        # Simple rotation effect using Unicode characters
        spin_chars = ["⟳", "⟲", "⟳", "⟲"]
        self.spin_angle = (self.spin_angle + 1) % len(spin_chars)
        self.icon_label.setText(spin_chars[self.spin_angle])

    def clear(self):
        """Clear the validation state."""
        self.set_state(self.State.IDLE)

    def set_validating(self, message: str = "Validating..."):
        """Set validating state."""
        self.set_state(self.State.VALIDATING, message)

    def set_valid(self, message: str = "Valid"):
        """Set valid state."""
        self.set_state(self.State.VALID, message)

    def set_invalid(self, message: str = "Invalid"):
        """Set invalid state."""
        self.set_state(self.State.INVALID, message)

    def set_warning(self, message: str = "Warning"):
        """Set warning state."""
        self.set_state(self.State.WARNING, message)


class ValidatedLineEdit(QWidget):
    """
    Line edit with integrated validation indicator.
    """

    text_changed = Signal(str)
    validation_changed = Signal(bool)  # valid/invalid

    def __init__(self, placeholder: str = "", password: bool = False, parent=None):
        super().__init__(parent)
        self.validator_func = None
        self.validation_delay = 500  # ms
        self._init_ui(placeholder, password)
        self._setup_validation()

    def _init_ui(self, placeholder: str, password: bool):
        """Initialize the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Line edit
        from PySide6.QtWidgets import QLineEdit

        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText(placeholder)
        if password:
            self.line_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.line_edit)

        # Validation indicator
        self.indicator = ValidationIndicator()
        layout.addWidget(self.indicator)

        # Connect signals
        self.line_edit.textChanged.connect(self._on_text_changed)

    def _setup_validation(self):
        """Setup validation timer."""
        self.validation_timer = QTimer()
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self._perform_validation)

    def _on_text_changed(self, text: str):
        """Handle text change."""
        self.text_changed.emit(text)

        # Reset validation timer
        self.validation_timer.stop()

        if self.validator_func and text:
            # Show validating state
            self.indicator.set_validating()
            # Start validation timer
            self.validation_timer.start(self.validation_delay)
        else:
            # Clear validation if no text
            self.indicator.clear()

    def _perform_validation(self):
        """Perform the validation."""
        if not self.validator_func:
            return

        text = self.line_edit.text()
        if not text:
            self.indicator.clear()
            return

        # Run validator
        try:
            is_valid, message = self.validator_func(text)

            if is_valid:
                self.indicator.set_valid(message)
            else:
                self.indicator.set_invalid(message)

            self.validation_changed.emit(is_valid)

        except Exception as e:
            self.indicator.set_invalid(f"Validation error: {str(e)}")
            self.validation_changed.emit(False)

    def set_validator(self, validator_func):
        """
        Set the validation function.

        Args:
            validator_func: Function that takes text and returns (is_valid, message)
        """
        self.validator_func = validator_func

        # Trigger validation if we have text
        if self.line_edit.text():
            self._on_text_changed(self.line_edit.text())

    def text(self) -> str:
        """Get the current text."""
        return self.line_edit.text()

    def setText(self, text: str):
        """Set the text."""
        self.line_edit.setText(text)

    def setPlaceholderText(self, text: str):
        """Set placeholder text."""
        self.line_edit.setPlaceholderText(text)

    def setFocus(self):
        """Set focus to the line edit."""
        self.line_edit.setFocus()

    def is_valid(self) -> bool:
        """Check if current text is valid."""
        return self.indicator.current_state == ValidationIndicator.State.VALID
