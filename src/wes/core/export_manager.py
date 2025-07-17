"""Export manager for generating summary outputs in various formats."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from ..utils.exceptions import ExportError
from ..utils.logging_config import get_logger


class ExportManager:
    """Handle summary exports to various formats.

    Supports exporting executive summaries to:
    - Markdown (.md)
    - HTML (.html)
    - PDF (.pdf)
    - Plain Text (.txt)
    - Clipboard
    """

    def __init__(self):
        """Initialize the export manager."""
        self.logger = get_logger(__name__)

    def export_summary(
        self, summary: Dict[str, Any], format: str, filepath: Optional[Path] = None
    ) -> bool:
        """Export summary in the specified format.

        Args:
            summary: Summary data containing content and metadata
            format: Export format (markdown, html, pdf, text, clipboard)
            filepath: Output file path (not needed for clipboard)

        Returns:
            True if export successful, False otherwise

        Raises:
            ExportError: If export fails
        """
        try:
            format = format.lower()

            if format == "markdown":
                return self.export_markdown(summary, filepath)
            elif format == "html":
                return self.export_html(summary, filepath)
            elif format == "pdf":
                return self.export_pdf(summary, filepath)
            elif format == "text":
                return self.export_text(summary, filepath)
            elif format == "clipboard":
                return self.copy_to_clipboard(summary)
            else:
                raise ExportError(f"Unsupported export format: {format}")

        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            raise ExportError(f"Failed to export summary: {e}")

    def export_markdown(self, summary: Dict[str, Any], filepath: Path) -> bool:
        """Export summary as Markdown file.

        Args:
            summary: Summary data
            filepath: Output file path

        Returns:
            True if successful
        """
        try:
            content = self._format_markdown(summary)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            self.logger.info(f"Exported summary to Markdown: {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Markdown export failed: {e}")
            raise ExportError(f"Failed to export Markdown: {e}")

    def export_html(self, summary: Dict[str, Any], filepath: Path) -> bool:
        """Export summary as HTML with styling.

        Args:
            summary: Summary data
            filepath: Output file path

        Returns:
            True if successful
        """
        try:
            content = self._format_html(summary)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            self.logger.info(f"Exported summary to HTML: {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"HTML export failed: {e}")
            raise ExportError(f"Failed to export HTML: {e}")

    def export_pdf(self, summary: Dict[str, Any], filepath: Path) -> bool:
        """Export summary as PDF document.

        Args:
            summary: Summary data
            filepath: Output file path

        Returns:
            True if successful
        """
        try:
            # Create PDF document
            doc = SimpleDocTemplate(
                str(filepath),
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18,
            )

            # Container for the 'Flowable' objects
            elements = []

            # Define styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=24,
                textColor=colors.HexColor("#1a1a1a"),
                spaceAfter=30,
            )

            heading_style = ParagraphStyle(
                "CustomHeading",
                parent=styles["Heading2"],
                fontSize=16,
                textColor=colors.HexColor("#333333"),
                spaceAfter=12,
            )

            body_style = ParagraphStyle(
                "CustomBody",
                parent=styles["BodyText"],
                fontSize=11,
                leading=16,
                spaceAfter=12,
            )

            # Add title
            elements.append(Paragraph("Executive Summary", title_style))

            # Add metadata
            generated_at = summary.get("generated_at", datetime.now())
            if isinstance(generated_at, (int, float)):
                generated_at = datetime.fromtimestamp(generated_at)

            metadata = f"Generated on {generated_at.strftime('%B %d, %Y at %I:%M %p')}"
            elements.append(Paragraph(metadata, body_style))
            elements.append(Spacer(1, 0.5 * inch))

            # Process content
            content = summary.get("content", "")
            lines = content.split("\n")

            for line in lines:
                line = line.strip()
                if not line:
                    elements.append(Spacer(1, 0.2 * inch))
                elif line.startswith("# "):
                    elements.append(Paragraph(line[2:], heading_style))
                elif line.startswith("## "):
                    elements.append(Paragraph(line[3:], heading_style))
                else:
                    # Handle bullet points
                    if line.startswith("- ") or line.startswith("* "):
                        line = "• " + line[2:]
                    elements.append(Paragraph(line, body_style))

            # Add footer
            elements.append(Spacer(1, 0.5 * inch))
            footer_text = f"Generated by WES using {summary.get('model', 'AI')}"
            elements.append(Paragraph(footer_text, body_style))

            # Build PDF
            doc.build(elements)

            self.logger.info(f"Exported summary to PDF: {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"PDF export failed: {e}")
            raise ExportError(f"Failed to export PDF: {e}")

    def export_text(self, summary: Dict[str, Any], filepath: Path) -> bool:
        """Export summary as plain text.

        Args:
            summary: Summary data
            filepath: Output file path

        Returns:
            True if successful
        """
        try:
            content = self._format_text(summary)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            self.logger.info(f"Exported summary to text: {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Text export failed: {e}")
            raise ExportError(f"Failed to export text: {e}")

    def copy_to_clipboard(self, summary: Dict[str, Any]) -> bool:
        """Copy formatted summary to clipboard.

        Args:
            summary: Summary data

        Returns:
            True if successful
        """
        try:
            # Format content for clipboard
            content = self._format_markdown(summary)

            # Get clipboard from Qt application
            app = QApplication.instance() or QGuiApplication.instance()
            if app:
                clipboard = app.clipboard()
                clipboard.setText(content)

                self.logger.info("Copied summary to clipboard")
                return True
            else:
                raise ExportError("No Qt application instance available")

        except Exception as e:
            self.logger.error(f"Clipboard copy failed: {e}")
            raise ExportError(f"Failed to copy to clipboard: {e}")

    def _format_markdown(self, summary: Dict[str, Any]) -> str:
        """Format summary content as Markdown.

        Args:
            summary: Summary data

        Returns:
            Formatted Markdown string
        """
        content = summary.get("content", "")

        # Add header
        formatted = "# Executive Summary\n\n"

        # Add metadata
        generated_at = summary.get("generated_at", datetime.now())
        if isinstance(generated_at, (int, float)):
            generated_at = datetime.fromtimestamp(generated_at)

        formatted += (
            f"*Generated on {generated_at.strftime('%B %d, %Y at %I:%M %p')}*\n\n"
        )

        # Add content
        formatted += content

        # Add footer
        formatted += "\n\n---\n"
        formatted += f"*Generated by WES using {summary.get('model', 'AI')}*\n"

        return formatted

    def _format_html(self, summary: Dict[str, Any]) -> str:
        """Format summary content as HTML.

        Args:
            summary: Summary data

        Returns:
            Formatted HTML string
        """
        content = summary.get("content", "")

        # Convert Markdown-style formatting to HTML
        html_content = content.replace("\n", "<br>\n")
        html_content = html_content.replace("# ", "<h1>")
        html_content = html_content.replace("## ", "<h2>")
        html_content = html_content.replace("### ", "<h3>")

        # Handle lists
        lines = html_content.split("<br>\n")
        formatted_lines = []
        in_list = False

        for line in lines:
            if line.strip().startswith("- ") or line.strip().startswith("* "):
                if not in_list:
                    formatted_lines.append("<ul>")
                    in_list = True
                formatted_lines.append(f"<li>{line.strip()[2:]}</li>")
            else:
                if in_list:
                    formatted_lines.append("</ul>")
                    in_list = False
                formatted_lines.append(line)

        if in_list:
            formatted_lines.append("</ul>")

        html_content = "\n".join(formatted_lines)

        # Build complete HTML
        generated_at = summary.get("generated_at", datetime.now())
        if isinstance(generated_at, (int, float)):
            generated_at = datetime.fromtimestamp(generated_at)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Executive Summary - {generated_at.strftime('%Y-%m-%d')}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1a1a1a;
            border-bottom: 2px solid #0084ff;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #333;
            margin-top: 30px;
        }}
        h3 {{
            color: #555;
        }}
        .metadata {{
            color: #666;
            font-style: italic;
            margin-bottom: 20px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #666;
            font-size: 0.9em;
        }}
        ul {{
            padding-left: 30px;
        }}
        li {{
            margin-bottom: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Executive Summary</h1>
        <div class="metadata">Generated on {generated_at.strftime('%B %d, %Y at %I:%M %p')}</div>
        {html_content}
        <div class="footer">
            Generated by WES using {summary.get('model', 'AI')}
        </div>
    </div>
</body>
</html>"""

        return html

    def _format_text(self, summary: Dict[str, Any]) -> str:
        """Format summary content as plain text.

        Args:
            summary: Summary data

        Returns:
            Formatted plain text string
        """
        content = summary.get("content", "")

        # Remove Markdown formatting
        text = content.replace("# ", "")
        text = text.replace("## ", "")
        text = text.replace("### ", "")
        text = text.replace("**", "")
        text = text.replace("*", "")
        text = text.replace("`", "")

        # Add header
        formatted = "EXECUTIVE SUMMARY\n"
        formatted += "=" * 50 + "\n\n"

        # Add metadata
        generated_at = summary.get("generated_at", datetime.now())
        if isinstance(generated_at, (int, float)):
            generated_at = datetime.fromtimestamp(generated_at)

        formatted += (
            f"Generated on {generated_at.strftime('%B %d, %Y at %I:%M %p')}\n\n"
        )

        # Add content
        formatted += text

        # Add footer
        formatted += "\n\n" + "-" * 50 + "\n"
        formatted += f"Generated by WES using {summary.get('model', 'AI')}\n"

        return formatted
