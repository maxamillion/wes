"""Main application entry point for Wes."""

import sys
import os
import argparse
import asyncio
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QDir, qInstallMessageHandler, QtMsgType
from PySide6.QtGui import QIcon

try:
    from .gui.main_window import MainWindow
    from .core.config_manager import ConfigManager
    from .utils.logging_config import setup_logging, get_logger
    from .utils.exceptions import WesError
except ImportError:
    from wes.gui.main_window import MainWindow
    from wes.core.config_manager import ConfigManager
    from wes.utils.logging_config import setup_logging, get_logger
    from wes.utils.exceptions import WesError


def qt_message_handler(mode: QtMsgType, context, message: str):
    """Custom Qt message handler for logging."""
    logger = get_logger("qt")

    if mode == QtMsgType.QtDebugMsg:
        logger.debug(f"Qt Debug: {message}")
    elif mode == QtMsgType.QtWarningMsg:
        logger.warning(f"Qt Warning: {message}")
    elif mode == QtMsgType.QtCriticalMsg:
        logger.error(f"Qt Critical: {message}")
    elif mode == QtMsgType.QtFatalMsg:
        logger.critical(f"Qt Fatal: {message}")


def setup_application_paths():
    """Setup application directories and paths."""
    # Ensure application directory exists
    app_dir = Path.home() / ".wes"
    app_dir.mkdir(parents=True, exist_ok=True)

    # Setup subdirectories
    (app_dir / "logs").mkdir(exist_ok=True)
    (app_dir / "config").mkdir(exist_ok=True)
    (app_dir / "cache").mkdir(exist_ok=True)

    return app_dir


def setup_environment():
    """Setup application environment."""
    # Set application properties
    QApplication.setApplicationName("Wes")
    QApplication.setApplicationVersion("1.0.0")
    QApplication.setOrganizationName("Company")
    QApplication.setOrganizationDomain("company.com")

    # Setup Qt settings location
    app_dir = setup_application_paths()
    QDir.addSearchPath("config", str(app_dir / "config"))

    return app_dir


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Wes - Automated executive summary generation"
    )

    parser.add_argument("--config", type=str, help="Path to configuration file")

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--log-file",
        type=str,
        help="Log file path (default: ~/.wes/logs/app.log)",
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    parser.add_argument(
        "--no-gui", action="store_true", help="Run in CLI mode (not implemented yet)"
    )

    parser.add_argument(
        "--test-connections",
        action="store_true",
        help="Test all API connections and exit",
    )

    parser.add_argument(
        "--version", action="version", version="Wes 1.0.0"
    )

    return parser.parse_args()


def initialize_logging(args, app_dir: Path):
    """Initialize logging system."""
    if args.debug:
        log_level = "DEBUG"
    else:
        log_level = args.log_level

    if args.log_file:
        log_file = args.log_file
    else:
        log_file = str(app_dir / "logs" / "app.log")

    setup_logging(
        level=log_level,
        log_file=log_file,
        enable_console=True,
        enable_structured=True,
        sanitize=True,
    )

    # Install Qt message handler
    qInstallMessageHandler(qt_message_handler)

    logger = get_logger(__name__)
    logger.info(f"Wes starting - Version 1.0.0")
    logger.info(f"Log level: {log_level}")
    logger.info(f"Log file: {log_file}")

    return logger


def setup_application_style(app: QApplication):
    """Setup application styling and theme."""
    # Set application icon
    icon_path = Path(__file__).parent / "gui" / "resources" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Apply modern styling
    app.setStyle("Fusion")

    # Set application-wide stylesheet
    stylesheet = """
    QApplication {
        font-family: "Segoe UI", "San Francisco", "Helvetica Neue", Arial, sans-serif;
        font-size: 9pt;
    }
    
    QMainWindow {
        background-color: #f5f5f5;
    }
    
    QMenuBar {
        background-color: #ffffff;
        border-bottom: 1px solid #d0d0d0;
        padding: 2px;
    }
    
    QMenuBar::item {
        background-color: transparent;
        padding: 4px 8px;
    }
    
    QMenuBar::item:selected {
        background-color: #e0e0e0;
        border-radius: 4px;
    }
    
    QStatusBar {
        background-color: #ffffff;
        border-top: 1px solid #d0d0d0;
    }
    """

    app.setStyleSheet(stylesheet)


async def test_connections_cli(config_manager: ConfigManager) -> bool:
    """Test all connections in CLI mode."""
    try:
        from .core.orchestrator import WorkflowOrchestrator
    except ImportError:
        from wes.core.orchestrator import WorkflowOrchestrator

    logger = get_logger(__name__)
    logger.info("Testing API connections...")

    try:
        orchestrator = WorkflowOrchestrator(config_manager)
        results = await orchestrator.test_connections()

        print("\nConnection Test Results:")
        print("=" * 30)

        for service, status in results.items():
            status_text = "✓ Connected" if status else "✗ Failed"
            print(f"{service.title():<15}: {status_text}")

        all_connected = all(results.values())

        if all_connected:
            print("\n✓ All connections successful!")
            logger.info("All connection tests passed")
            return True
        else:
            print("\n✗ Some connections failed. Please check your configuration.")
            logger.warning("Some connection tests failed")
            return False

    except Exception as e:
        print(f"\n✗ Connection test failed: {e}")
        logger.error(f"Connection test failed: {e}")
        return False


def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler."""
    logger = get_logger(__name__)

    if issubclass(exc_type, KeyboardInterrupt):
        # Handle Ctrl+C gracefully
        logger.info("Application interrupted by user")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Log the exception
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    # Show error dialog if GUI is available
    if QApplication.instance():
        error_msg = f"An unexpected error occurred:\n\n{exc_value}\n\nPlease check the logs for more details."
        QMessageBox.critical(None, "Unexpected Error", error_msg)

    # Call the default handler
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def main():
    """Main application entry point."""
    # Parse arguments
    args = parse_arguments()

    # Setup environment
    app_dir = setup_environment()

    # Initialize logging
    logger = initialize_logging(args, app_dir)

    # Install global exception handler
    sys.excepthook = handle_exception

    try:
        # Initialize configuration manager
        config_manager = ConfigManager()

        # Handle CLI mode operations
        if args.test_connections:
            # Test connections and exit
            result = asyncio.run(test_connections_cli(config_manager))
            sys.exit(0 if result else 1)

        if args.no_gui:
            logger.error("CLI mode not implemented yet")
            print("CLI mode is not implemented yet. Please use GUI mode.")
            sys.exit(1)

        # Create GUI application
        app = QApplication(sys.argv)

        # Setup application properties
        setup_application_style(app)

        # Create main window
        main_window = MainWindow()

        # Show main window
        main_window.show()

        logger.info("Application GUI started successfully")

        # Run event loop
        exit_code = app.exec()

        logger.info(f"Application exiting with code: {exit_code}")
        return exit_code

    except WesError as e:
        logger.error(f"Application error: {e}")
        if QApplication.instance():
            QMessageBox.critical(None, "Application Error", str(e))
        else:
            print(f"Error: {e}")
        return 1

    except Exception as e:
        logger.critical(f"Unexpected error during startup: {e}")
        if QApplication.instance():
            QMessageBox.critical(
                None, "Startup Error", f"Failed to start application: {e}"
            )
        else:
            print(f"Startup error: {e}")
        return 1


def gui_main():
    """Entry point for GUI-only execution."""
    # Filter out CLI-specific arguments for GUI mode
    filtered_args = [arg for arg in sys.argv if not arg.startswith("--no-gui")]
    sys.argv = filtered_args

    return main()


if __name__ == "__main__":
    sys.exit(main())
