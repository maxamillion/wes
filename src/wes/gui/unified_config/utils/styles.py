"""Centralized style definitions for the unified configuration dialog.

This module provides consistent styling across all UI components to improve
maintainability and ensure a cohesive visual design.
"""


class StyleManager:
    """Manages application-wide styles and themes."""

    # Color Palette
    COLORS = {
        "primary": "#4285f4",
        "primary_hover": "#357ae8",
        "primary_pressed": "#2968c8",
        "success": "#28a745",
        "warning": "#ffc107",
        "danger": "#dc3545",
        "info": "#17a2b8",
        "text_primary": "#212529",
        "text_secondary": "#666666",
        "text_muted": "#999999",
        "background": "#ffffff",
        "background_secondary": "#f0f0f0",
        "border": "#d0d0d0",
        "border_light": "#e0e0e0",
    }

    # Font Sizes
    FONT_SIZES = {
        "tiny": "10px",
        "small": "11px",
        "normal": "12px",
        "medium": "14px",
        "large": "16px",
        "xlarge": "18px",
        "heading": "24px",
    }

    # Spacing
    SPACING = {
        "tiny": 2,
        "small": 5,
        "normal": 10,
        "medium": 15,
        "large": 20,
        "xlarge": 30,
    }

    @classmethod
    def get_button_style(cls, variant: str = "default") -> str:
        """Get button style based on variant.

        Args:
            variant: Button variant ('primary', 'secondary', 'danger', etc.)

        Returns:
            QString: CSS stylesheet for the button.
        """
        if variant == "primary":
            return f"""
                QPushButton {{
                    background-color: {cls.COLORS['primary']};
                    color: white;
                    font-weight: bold;
                    padding: 5px 15px;
                    border-radius: 3px;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {cls.COLORS['primary_hover']};
                }}
                QPushButton:pressed {{
                    background-color: {cls.COLORS['primary_pressed']};
                }}
                QPushButton:disabled {{
                    background-color: {cls.COLORS['text_muted']};
                    color: {cls.COLORS['background_secondary']};
                }}
            """
        elif variant == "secondary":
            return f"""
                QPushButton {{
                    background-color: {cls.COLORS['background']};
                    color: {cls.COLORS['text_primary']};
                    padding: 5px 15px;
                    border-radius: 3px;
                    border: 1px solid {cls.COLORS['border']};
                }}
                QPushButton:hover {{
                    background-color: {cls.COLORS['background_secondary']};
                }}
                QPushButton:pressed {{
                    background-color: {cls.COLORS['border_light']};
                }}
            """
        elif variant == "danger":
            return f"""
                QPushButton {{
                    background-color: {cls.COLORS['danger']};
                    color: white;
                    padding: 5px 15px;
                    border-radius: 3px;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: #c82333;
                }}
                QPushButton:pressed {{
                    background-color: #bd2130;
                }}
            """
        return ""

    @classmethod
    def get_label_style(cls, variant: str = "default") -> str:
        """Get label style based on variant.

        Args:
            variant: Label variant ('success', 'warning', 'danger', 'muted', etc.)

        Returns:
            QString: CSS stylesheet for the label.
        """
        color_map = {
            "success": cls.COLORS["success"],
            "warning": cls.COLORS["warning"],
            "danger": cls.COLORS["danger"],
            "info": cls.COLORS["info"],
            "muted": cls.COLORS["text_muted"],
            "secondary": cls.COLORS["text_secondary"],
        }

        color = color_map.get(variant, cls.COLORS["text_primary"])
        return f"color: {color};"

    @classmethod
    def get_group_box_style(cls, collapsible: bool = False) -> str:
        """Get group box style.

        Args:
            collapsible: Whether the group box is collapsible.

        Returns:
            QString: CSS stylesheet for the group box.
        """
        base_style = f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {cls.COLORS['border']};
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
        """

        if collapsible:
            base_style += """
                QGroupBox::indicator {
                    width: 13px;
                    height: 13px;
                }
            """

        return base_style

    @classmethod
    def get_scroll_area_style(cls) -> str:
        """Get scroll area style with custom scrollbars.

        Returns:
            QString: CSS stylesheet for scroll areas.
        """
        return f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                width: 12px;
                background: {cls.COLORS['background_secondary']};
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {cls.COLORS['border']};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {cls.COLORS['text_muted']};
            }}
            QScrollBar:horizontal {{
                height: 12px;
                background: {cls.COLORS['background_secondary']};
                border-radius: 6px;
            }}
            QScrollBar::handle:horizontal {{
                background: {cls.COLORS['border']};
                border-radius: 6px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {cls.COLORS['text_muted']};
            }}
        """

    @classmethod
    def get_compact_mode_style(cls) -> str:
        """Get stylesheet for compact mode on small screens.

        Returns:
            QString: CSS stylesheet for compact mode.
        """
        return f"""
            QLabel {{
                font-size: {cls.FONT_SIZES['small']};
                padding: 1px;
            }}
            QLineEdit {{
                padding: 2px;
                font-size: {cls.FONT_SIZES['small']};
            }}
            QPushButton {{
                padding: 4px 8px;
                font-size: {cls.FONT_SIZES['small']};
            }}
            QGroupBox {{
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                font-size: {cls.FONT_SIZES['normal']};
            }}
            QCheckBox, QRadioButton {{
                font-size: {cls.FONT_SIZES['small']};
                spacing: 3px;
            }}
            QSpinBox, QComboBox {{
                padding: 2px;
                font-size: {cls.FONT_SIZES['small']};
            }}
        """

    @classmethod
    def get_dialog_header_style(cls) -> str:
        """Get style for dialog headers.

        Returns:
            QString: CSS stylesheet for dialog headers.
        """
        return f"""
            #configHeader {{
                background-color: {cls.COLORS['background_secondary']};
                border-bottom: 1px solid {cls.COLORS['border']};
            }}
            #modeLabel {{
                font-size: {cls.FONT_SIZES['large']};
                font-weight: bold;
            }}
            #buttonArea {{
                background-color: {cls.COLORS['background_secondary']};
                border-top: 1px solid {cls.COLORS['border']};
            }}
        """


class StyleConstants:
    """Constants for consistent styling across the application."""

    # Dialog Sizes
    DIALOG_SIZES = {
        "small": (400, 300),
        "medium": (600, 500),
        "large": (800, 600),
        "xlarge": (1000, 800),
    }

    # Minimum Sizes
    MIN_DIALOG_SIZE = (600, 400)
    MIN_BUTTON_WIDTH = 80

    # Maximum Sizes
    MAX_INSTRUCTION_HEIGHT = 150
    MAX_DESCRIPTION_WIDTH = 600

    # Layout Constants
    DEFAULT_SPACING = 10
    COMPACT_SPACING = 5
    FORM_SPACING = 15

    # Animation Durations (ms)
    ANIMATION_FAST = 150
    ANIMATION_NORMAL = 300
    ANIMATION_SLOW = 500
