"""Responsive layout manager for configuration pages."""

from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout, QWidget


class ResponsiveConfigLayout(QObject):
    """Manages responsive layout adjustments for config pages."""

    # Signals
    layout_mode_changed = Signal(bool)  # is_compact

    # Layout thresholds
    COMPACT_HEIGHT_THRESHOLD = 600  # Height threshold for compact mode
    COMPACT_WIDTH_THRESHOLD = 800  # Width threshold for compact mode

    def __init__(self, config_page: QWidget, parent=None):
        super().__init__(parent)
        self.config_page = config_page
        self.is_compact = False
        self.original_spacing = {}
        self.hidden_widgets = []

    def adjust_for_size(self, width: int, height: int):
        """Adjust layout based on available size."""
        should_be_compact = (
            height < self.COMPACT_HEIGHT_THRESHOLD
            or width < self.COMPACT_WIDTH_THRESHOLD
        )

        if should_be_compact != self.is_compact:
            self.is_compact = should_be_compact
            (
                self._apply_compact_mode()
                if should_be_compact
                else self._apply_normal_mode()
            )
            self.layout_mode_changed.emit(should_be_compact)

    def _apply_compact_mode(self):
        """Apply compact layout for small screens."""
        # Reduce spacing in all layouts
        self._adjust_spacing(5)

        # Hide less important elements
        self._hide_descriptions()

        # Apply compact stylesheet
        self.config_page.setStyleSheet(
            """
            QLabel { 
                font-size: 11px; 
                padding: 1px;
            }
            QLineEdit { 
                padding: 2px;
                font-size: 11px;
            }
            QPushButton { 
                padding: 4px 8px;
                font-size: 11px;
            }
            QGroupBox {
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                font-size: 12px;
            }
            QCheckBox, QRadioButton {
                font-size: 11px;
                spacing: 3px;
            }
            QSpinBox, QComboBox {
                padding: 2px;
                font-size: 11px;
            }
        """
        )

    def _apply_normal_mode(self):
        """Apply normal layout for larger screens."""
        # Restore normal spacing
        self._adjust_spacing(10)

        # Show all elements
        self._show_descriptions()

        # Remove compact stylesheet
        self.config_page.setStyleSheet("")

    def _adjust_spacing(self, spacing: int):
        """Recursively adjust spacing in all layouts."""
        self._adjust_widget_spacing(self.config_page, spacing)

    def _adjust_widget_spacing(self, widget: QWidget, spacing: int):
        """Adjust spacing for a widget and its children."""
        # Store original spacing if not already stored
        if widget not in self.original_spacing and widget.layout():
            self.original_spacing[widget] = widget.layout().spacing()

        # Adjust layout spacing
        if widget.layout():
            widget.layout().setSpacing(spacing)

            # Adjust margins for compact mode
            if self.is_compact:
                margins = widget.layout().contentsMargins()
                widget.layout().setContentsMargins(
                    max(5, margins.left() // 2),
                    max(5, margins.top() // 2),
                    max(5, margins.right() // 2),
                    max(5, margins.bottom() // 2),
                )

        # Recursively adjust children
        for child in widget.findChildren(QWidget):
            if child.layout() and child.parent() == widget:
                self._adjust_widget_spacing(child, spacing)

    def _hide_descriptions(self):
        """Hide description labels and less important widgets."""
        self.hidden_widgets = []

        # Find and hide description labels
        for label in self.config_page.findChildren(QWidget):
            # Check various ways description widgets might be identified
            if any(
                [
                    hasattr(label, "objectName")
                    and "description" in label.objectName().lower(),
                    hasattr(label, "property") and label.property("is_description"),
                    hasattr(label, "styleSheet")
                    and "color: gray" in label.styleSheet(),
                    isinstance(label.parent(), QWidget)
                    and hasattr(label.parent(), "objectName")
                    and "description" in label.parent().objectName().lower(),
                ]
            ):
                label.hide()
                self.hidden_widgets.append(label)

    def _show_descriptions(self):
        """Show previously hidden widgets."""
        for widget in self.hidden_widgets:
            widget.show()
        self.hidden_widgets = []

    def create_collapsible_section(
        self, title: str, content_widget: QWidget, start_collapsed: bool = True
    ) -> QGroupBox:
        """Create a collapsible section for better space usage."""
        group = QGroupBox(title)
        group.setCheckable(True)
        group.setChecked(not start_collapsed)

        # Create layout and add content
        layout = QVBoxLayout()
        layout.addWidget(content_widget)
        group.setLayout(layout)

        # Style for collapsible indicator
        group.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QGroupBox::indicator {
                width: 13px;
                height: 13px;
            }
        """
        )

        # Update title with indicator
        def update_title():
            prefix = "▼" if group.isChecked() else "▶"
            group.setTitle(f"{prefix} {title}")

        group.toggled.connect(update_title)
        update_title()

        return group

    def create_two_column_layout(self, items: list) -> QHBoxLayout:
        """Create a two-column layout for better space usage."""
        layout = QHBoxLayout()
        layout.setSpacing(20)

        # Create two columns
        left_column = QVBoxLayout()
        right_column = QVBoxLayout()

        # Distribute items between columns
        for i, item in enumerate(items):
            if i < len(items) // 2:
                left_column.addWidget(item)
            else:
                right_column.addWidget(item)

        # Add stretch to align items to top
        left_column.addStretch()
        right_column.addStretch()

        layout.addLayout(left_column)
        layout.addLayout(right_column)

        return layout

    def make_responsive(self):
        """Make the config page responsive to size changes."""
        # Override the resizeEvent of the config page
        original_resize_event = self.config_page.resizeEvent

        def new_resize_event(event):
            original_resize_event(event)
            self.adjust_for_size(event.size().width(), event.size().height())

        self.config_page.resizeEvent = new_resize_event
