"""Test headless GUI functionality."""

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget


class TestHeadlessGUI:
    """Test that GUI components work in headless mode."""

    def test_qapplication_creation(self, qapp):
        """Test that QApplication can be created in headless mode."""
        assert qapp is not None
        assert isinstance(qapp, QApplication)

    def test_qt_platform_is_offscreen(self, qapp):
        """Test that Qt is using offscreen platform."""
        platform = os.environ.get("QT_QPA_PLATFORM", "not set")
        assert platform == "offscreen", f"Expected offscreen, got: {platform}"

    def test_widget_creation(self, qapp, qtbot):
        """Test that widgets can be created in headless mode."""
        widget = QWidget()
        qtbot.addWidget(widget)

        # Set up a simple layout
        layout = QVBoxLayout()
        label = QLabel("Test Label")
        button = QPushButton("Test Button")

        layout.addWidget(label)
        layout.addWidget(button)
        widget.setLayout(layout)

        # Verify the widget structure
        assert widget.layout() is not None
        assert widget.layout().count() == 2
        assert label.text() == "Test Label"
        assert button.text() == "Test Button"

    def test_widget_signals(self, qapp, qtbot):
        """Test that signals work in headless mode."""
        button = QPushButton("Click Me")
        qtbot.addWidget(button)

        clicked = False

        def on_clicked():
            nonlocal clicked
            clicked = True

        button.clicked.connect(on_clicked)

        # Simulate button click
        qtbot.mouseClick(button, Qt.LeftButton)

        assert clicked, "Button click signal was not emitted"

    def test_widget_show_hide(self, qapp, qtbot):
        """Test that show/hide operations work in headless mode."""
        widget = QWidget()
        qtbot.addWidget(widget)

        # Initially hidden
        assert not widget.isVisible()

        # Show widget
        widget.show()
        qtbot.waitForWindowShown(widget)
        assert widget.isVisible()

        # Hide widget
        widget.hide()
        assert not widget.isVisible()

    def test_environment_variables(self):
        """Test that required environment variables are set."""
        # QT_QPA_PLATFORM should be set to offscreen
        assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"

        # QT_LOGGING_RULES should be set to reduce noise
        logging_rules = os.environ.get("QT_LOGGING_RULES", "")
        assert "debug=false" in logging_rules

        # DISPLAY should be set (even if virtual)
        assert os.environ.get("DISPLAY") is not None

    def test_no_display_dependency(self, qapp):
        """Test that GUI works even without a real display."""
        # This test verifies that we don't need a real X11 display
        # The QApplication should work with offscreen platform

        # Try to get screen information
        screen = qapp.primaryScreen()
        assert screen is not None

        # Get screen geometry (should work in offscreen mode)
        geometry = screen.geometry()
        assert geometry.width() > 0
        assert geometry.height() > 0

    def test_concurrent_widgets(self, qapp, qtbot):
        """Test that multiple widgets can be created concurrently."""
        widgets = []

        # Create multiple widgets
        for i in range(5):
            widget = QWidget()
            widget.setObjectName(f"widget_{i}")
            qtbot.addWidget(widget)
            widgets.append(widget)

        # Verify all widgets were created
        assert len(widgets) == 5

        # Verify each widget is unique
        for i, widget in enumerate(widgets):
            assert widget.objectName() == f"widget_{i}"

    def test_widget_resize_in_headless(self, qapp, qtbot):
        """Test that widget resizing works in headless mode."""
        widget = QWidget()
        qtbot.addWidget(widget)

        # Set initial size
        widget.resize(100, 100)
        assert widget.size().width() == 100
        assert widget.size().height() == 100

        # Resize widget
        widget.resize(200, 150)
        assert widget.size().width() == 200
        assert widget.size().height() == 150

    def test_layout_operations_headless(self, qapp, qtbot):
        """Test that layout operations work in headless mode."""
        widget = QWidget()
        qtbot.addWidget(widget)

        layout = QVBoxLayout()
        widget.setLayout(layout)

        # Add items to layout
        items = []
        for i in range(3):
            label = QLabel(f"Label {i}")
            layout.addWidget(label)
            items.append(label)

        # Verify layout has correct number of items
        assert layout.count() == 3

        # Verify items are accessible
        for i in range(3):
            item = layout.itemAt(i)
            assert item is not None
            assert item.widget().text() == f"Label {i}"

    def test_style_operations_headless(self, qapp, qtbot):
        """Test that style operations work in headless mode."""
        widget = QWidget()
        qtbot.addWidget(widget)

        # Set stylesheet
        widget.setStyleSheet("QWidget { background-color: red; }")
        assert "background-color: red" in widget.styleSheet()

        # Change stylesheet
        widget.setStyleSheet("QWidget { background-color: blue; }")
        assert "background-color: blue" in widget.styleSheet()
