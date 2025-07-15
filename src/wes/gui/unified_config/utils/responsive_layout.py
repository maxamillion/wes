"""Responsive layout manager for configuration pages."""

from typing import Dict, List, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout, QWidget

from wes.gui.unified_config.utils.styles import StyleManager


class ResponsiveConfigLayout(QObject):
    """Manages responsive layout adjustments for config pages.

    This class provides responsive layout capabilities for configuration pages,
    automatically adjusting spacing, visibility, and styling based on available
    screen space. It supports compact mode for small screens and provides
    utilities for creating collapsible sections and multi-column layouts.

    Attributes:
        COMPACT_HEIGHT_THRESHOLD (int): Height below which compact mode activates (600px).
        COMPACT_WIDTH_THRESHOLD (int): Width below which compact mode activates (800px).

    Signals:
        layout_mode_changed (bool): Emitted when switching between normal and compact modes.
                                   True indicates compact mode is active.
    """

    # Signals
    layout_mode_changed = Signal(bool)  # is_compact

    # Layout thresholds
    COMPACT_HEIGHT_THRESHOLD = 600  # Height threshold for compact mode
    COMPACT_WIDTH_THRESHOLD = 800  # Width threshold for compact mode

    def __init__(self, config_page: QWidget, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.config_page: QWidget = config_page
        self.is_compact: bool = False
        self.original_spacing: Dict[QWidget, int] = {}
        self.hidden_widgets: List[QWidget] = []

    def adjust_for_size(self, width: int, height: int) -> None:
        """Adjust layout based on available size."""
        should_be_compact = (
            height < self.COMPACT_HEIGHT_THRESHOLD
            or width < self.COMPACT_WIDTH_THRESHOLD
        )

        if should_be_compact != self.is_compact:
            self.is_compact = should_be_compact
            if should_be_compact:
                self._apply_compact_mode()
            else:
                self._apply_normal_mode()
            self.layout_mode_changed.emit(should_be_compact)

    def _apply_compact_mode(self) -> None:
        """Apply compact layout for small screens."""
        # Reduce spacing in all layouts
        self._adjust_spacing(5)

        # Hide less important elements
        self._hide_descriptions()

        # Apply compact stylesheet using StyleManager
        self.config_page.setStyleSheet(StyleManager.get_compact_mode_style())

    def _apply_normal_mode(self) -> None:
        """Apply normal layout for larger screens."""
        # Restore normal spacing
        self._adjust_spacing(10)

        # Show all elements
        self._show_descriptions()

        # Remove compact stylesheet
        self.config_page.setStyleSheet("")

    def _adjust_spacing(self, spacing: int) -> None:
        """Recursively adjust spacing in all layouts."""
        self._adjust_widget_spacing(self.config_page, spacing)

    def _adjust_widget_spacing(self, widget: QWidget, spacing: int) -> None:
        """Adjust spacing for a widget and its children."""
        try:
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
        except AttributeError:
            # Widget might not have a layout, skip it
            pass

    def _hide_descriptions(self) -> None:
        """Hide description labels and less important widgets."""
        self.hidden_widgets = []

        # Find and hide description labels
        for label in self.config_page.findChildren(QWidget):
            # Check various ways description widgets might be identified
            is_description = (
                (
                    hasattr(label, "objectName")
                    and "description" in label.objectName().lower()
                )
                or (hasattr(label, "property") and label.property("is_description"))
                or (
                    hasattr(label, "styleSheet") and "color: gray" in label.styleSheet()
                )
                or (
                    isinstance(label.parent(), QWidget)
                    and hasattr(label.parent(), "objectName")
                    and "description" in label.parent().objectName().lower()
                )
            )
            if is_description:
                label.hide()
                self.hidden_widgets.append(label)

    def _show_descriptions(self) -> None:
        """Show previously hidden widgets."""
        for widget in self.hidden_widgets:
            widget.show()
        self.hidden_widgets = []

    def create_collapsible_section(
        self, title: str, content_widget: QWidget, start_collapsed: bool = True
    ) -> QGroupBox:
        """Create a collapsible section for better space usage.

        Args:
            title: The title to display for the section.
            content_widget: The widget to show/hide when toggling.
            start_collapsed: Whether to start in collapsed state (default: True).

        Returns:
            QGroupBox: A styled, collapsible group box containing the content.
        """
        group = QGroupBox(title)
        group.setCheckable(True)
        group.setChecked(not start_collapsed)

        # Create layout and add content
        layout = QVBoxLayout()
        layout.addWidget(content_widget)
        group.setLayout(layout)

        # Style for collapsible indicator using StyleManager
        group.setStyleSheet(StyleManager.get_group_box_style(collapsible=True))

        # Update title with indicator
        def update_title():
            prefix = "▼" if group.isChecked() else "▶"
            group.setTitle(f"{prefix} {title}")

        group.toggled.connect(update_title)
        update_title()

        return group

    def create_two_column_layout(self, items: List[QWidget]) -> QHBoxLayout:
        """Create a two-column layout for better space usage.

        Distributes widgets evenly between two columns, with the first half
        in the left column and the second half in the right column.

        Args:
            items: List of widgets to arrange in two columns.

        Returns:
            QHBoxLayout: A horizontal layout containing two columns of widgets.
        """
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

    def make_responsive(self) -> None:
        """Make the config page responsive to size changes."""
        # Override the resizeEvent of the config page
        original_resize_event = self.config_page.resizeEvent

        def new_resize_event(event):
            original_resize_event(event)
            self.adjust_for_size(event.size().width(), event.size().height())

        self.config_page.resizeEvent = new_resize_event
