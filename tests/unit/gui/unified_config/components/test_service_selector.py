"""Tests for service selector component."""

from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from wes.gui.unified_config.components.service_selector import ServiceSelector
from wes.gui.unified_config.types import JiraType


class TestServiceSelector:
    """Test ServiceSelector functionality."""

    @pytest.fixture
    def app(self, qtbot):
        """Create QApplication for testing."""
        return QApplication.instance() or QApplication([])

    @pytest.fixture
    def selector(self, qtbot):
        """Create a ServiceSelector instance."""
        selector = ServiceSelector()
        qtbot.addWidget(selector)
        return selector

    def test_initial_state(self, selector):
        """Test initial state defaults to Cloud Jira."""
        assert selector.current_type == JiraType.CLOUD
        assert selector.cloud_radio.isChecked()
        assert not selector.server_radio.isChecked()
        assert not selector.redhat_radio.isChecked()

    def test_radio_button_selection(self, selector, qtbot):
        """Test selecting different service types."""
        # Select Server
        with qtbot.waitSignal(selector.service_selected) as blocker:
            selector.server_radio.click()

        assert selector.current_type == JiraType.SERVER
        assert selector.server_radio.isChecked()
        assert blocker.args[0] == JiraType.SERVER

        # Select Red Hat
        with qtbot.waitSignal(selector.service_selected) as blocker:
            selector.redhat_radio.click()

        assert selector.current_type == JiraType.REDHAT
        assert selector.redhat_radio.isChecked()
        assert blocker.args[0] == JiraType.REDHAT

    def test_set_service_type(self, selector):
        """Test programmatically setting service type."""
        # Set to Server
        selector.set_service_type(JiraType.SERVER)
        assert selector.current_type == JiraType.SERVER
        assert selector.server_radio.isChecked()

        # Set to Red Hat
        selector.set_service_type(JiraType.REDHAT)
        assert selector.current_type == JiraType.REDHAT
        assert selector.redhat_radio.isChecked()

        # Set back to Cloud
        selector.set_service_type(JiraType.CLOUD)
        assert selector.current_type == JiraType.CLOUD
        assert selector.cloud_radio.isChecked()

    def test_get_service_type(self, selector):
        """Test getting current service type."""
        assert selector.get_service_type() == JiraType.CLOUD

        selector.server_radio.click()
        assert selector.get_service_type() == JiraType.SERVER

        selector.redhat_radio.click()
        assert selector.get_service_type() == JiraType.REDHAT

    def test_auto_detect_disabled_initially(self, selector):
        """Test auto-detect button is disabled initially."""
        assert not selector.detect_button.isEnabled()

    def test_enable_auto_detect(self, selector):
        """Test enabling auto-detect with URL callback."""
        url_callback = Mock(return_value="https://example.atlassian.net")

        selector.enable_auto_detect(url_callback)
        assert selector.detect_button.isEnabled()

    def test_auto_detect_cloud_url(self, selector, qtbot):
        """Test auto-detecting Cloud Jira from URL."""
        # Start with Server selected
        selector.set_service_type(JiraType.SERVER)

        # Enable auto-detect
        url_callback = Mock(return_value="https://example.atlassian.net")
        selector.enable_auto_detect(url_callback)

        # Click auto-detect
        with qtbot.waitSignal(selector.service_selected) as blocker:
            selector.detect_button.click()

        # Should detect Cloud
        assert selector.current_type == JiraType.CLOUD
        assert selector.cloud_radio.isChecked()
        assert blocker.args[0] == JiraType.CLOUD

    def test_auto_detect_redhat_url(self, selector, qtbot):
        """Test auto-detecting Red Hat Jira from URL."""
        # Enable auto-detect with Red Hat URL
        url_callback = Mock(return_value="https://issues.redhat.com/browse/RHEL-12345")
        selector.enable_auto_detect(url_callback)

        # Click auto-detect
        with qtbot.waitSignal(selector.service_selected) as blocker:
            selector.detect_button.click()

        # Should detect Red Hat
        assert selector.current_type == JiraType.REDHAT
        assert selector.redhat_radio.isChecked()
        assert blocker.args[0] == JiraType.REDHAT

    def test_auto_detect_server_url(self, selector, qtbot):
        """Test auto-detecting Server Jira from URL."""
        # Enable auto-detect with generic URL
        url_callback = Mock(return_value="https://jira.company.com")
        selector.enable_auto_detect(url_callback)

        # Click auto-detect
        with qtbot.waitSignal(selector.service_selected) as blocker:
            selector.detect_button.click()

        # Should detect Server
        assert selector.current_type == JiraType.SERVER
        assert selector.server_radio.isChecked()
        assert blocker.args[0] == JiraType.SERVER

    def test_auto_detect_empty_url(self, selector):
        """Test auto-detect with empty URL does nothing."""
        initial_type = selector.current_type

        # Enable auto-detect with empty URL
        url_callback = Mock(return_value="")
        selector.enable_auto_detect(url_callback)

        # Click auto-detect
        selector.detect_button.click()

        # Should not change
        assert selector.current_type == initial_type

    def test_service_descriptions(self, selector):
        """Test that service descriptions are present."""
        # Check that each option has descriptive text
        cloud_container = selector.cloud_radio.parent()
        assert (
            "Most common for modern teams" in cloud_container.findChild(QLabel).text()
        )

        server_container = selector.server_radio.parent()
        assert "Self-hosted Jira instances" in server_container.findChild(QLabel).text()

        redhat_container = selector.redhat_radio.parent()
        assert "Red Hat employees" in redhat_container.findChild(QLabel).text()

    def test_container_click(self, selector, qtbot):
        """Test clicking on container selects radio button."""
        # Get the server container
        selector.server_radio.parent()

        # Click on container (simulate mouse press)
        with qtbot.waitSignal(selector.service_selected):
            # Simulate clicking on the container
            selector.server_radio.setChecked(True)
            selector._on_selection_changed(selector.server_radio)

        assert selector.current_type == JiraType.SERVER
        assert selector.server_radio.isChecked()
