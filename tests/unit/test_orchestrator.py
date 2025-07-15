"""Unit tests for the workflow orchestrator."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.wes.core.orchestrator import (
    WorkflowOrchestrator,
    WorkflowResult,
    WorkflowStatus,
)
from src.wes.utils.exceptions import (
    GeminiIntegrationError,
    JiraIntegrationError,
    WesError,
)


@pytest.fixture
def mock_config_manager():
    """Create a mock config manager."""
    config_manager = Mock()
    config_manager.validate_configuration.return_value = True
    config_manager.retrieve_credential.side_effect = (
        lambda service, key: f"test_{service}_{key}"
    )

    # Mock configuration getters
    jira_config = Mock(
        url="https://test.atlassian.net",
        username="test@example.com",
        rate_limit=100,
        timeout=30,
        default_users=["user1", "user2"],
    )
    config_manager.get_jira_config.return_value = jira_config

    ai_config = Mock(
        model_name="gemini-2.5-flash",
        rate_limit=50,
        timeout=30,
        temperature=0.7,
        max_tokens=2048,
        custom_prompt=None,
    )
    config_manager.get_ai_config.return_value = ai_config

    return config_manager


@pytest.fixture
def orchestrator(mock_config_manager):
    """Create an orchestrator instance with mocked dependencies."""
    with patch("src.wes.core.orchestrator.ServiceFactory") as MockServiceFactory:
        mock_factory = Mock()
        MockServiceFactory.return_value = mock_factory
        return WorkflowOrchestrator(mock_config_manager)


class TestWorkflowOrchestrator:
    """Test suite for WorkflowOrchestrator."""

    def test_initialization(self, orchestrator, mock_config_manager):
        """Test orchestrator initialization."""
        assert orchestrator.config_manager == mock_config_manager
        assert orchestrator.is_cancelled is False
        assert orchestrator.current_stage == 0
        assert len(orchestrator.stages) == 5
        assert orchestrator.jira_client is None
        assert orchestrator.gemini_client is None

    def test_set_progress_callback(self, orchestrator):
        """Test setting progress callback."""
        callback = Mock()
        orchestrator.set_progress_callback(callback)
        assert orchestrator.progress_callback == callback

        # Test progress update
        orchestrator._update_progress("Test message", 50)
        callback.assert_called_once_with("Test message", 50)

    def test_cancel_workflow(self, orchestrator):
        """Test workflow cancellation."""
        orchestrator.cancel()
        assert orchestrator.is_cancelled is True

    @pytest.mark.asyncio
    async def test_execute_workflow_success(self, orchestrator, mock_config_manager):
        """Test successful workflow execution."""
        # Mock all stage methods
        orchestrator._stage_validate_configuration = AsyncMock()
        orchestrator._stage_initialize_clients = AsyncMock()
        orchestrator._stage_fetch_jira_data = AsyncMock(
            return_value=[
                {"id": "TEST-1", "summary": "Test issue", "assignee": "user1"}
            ]
        )
        orchestrator._stage_generate_summary = AsyncMock(
            return_value={
                "content": "Test summary content",
                "model": "gemini-2.5-flash",
            }
        )
        orchestrator._stage_finalize = AsyncMock()
        orchestrator._cleanup_clients = AsyncMock()

        # Execute workflow
        users = ["user1", "user2"]
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()

        result = await orchestrator.execute_workflow(
            users=users,
            start_date=start_date,
            end_date=end_date,
            custom_prompt="Custom prompt",
        )

        # Verify result
        assert result.status == WorkflowStatus.COMPLETED
        assert result.summary_content == "Test summary content"
        assert result.activity_count == 1
        assert result.execution_time > 0
        assert result.error_message is None
        assert len(result.stages_completed) == 5

        # Verify all stages were called
        orchestrator._stage_validate_configuration.assert_called_once()
        orchestrator._stage_initialize_clients.assert_called_once()
        orchestrator._stage_fetch_jira_data.assert_called_once_with(
            users, start_date, end_date
        )
        orchestrator._stage_generate_summary.assert_called_once()
        orchestrator._stage_finalize.assert_called_once()
        orchestrator._cleanup_clients.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_workflow_with_cancellation(self, orchestrator):
        """Test workflow execution with cancellation."""
        # Mock stages
        orchestrator._stage_validate_configuration = AsyncMock()
        orchestrator._stage_initialize_clients = AsyncMock()
        orchestrator._cleanup_clients = AsyncMock()

        # Cancel after initialization
        async def cancel_after_init():
            orchestrator.is_cancelled = True

        orchestrator._stage_initialize_clients.side_effect = cancel_after_init

        # Execute workflow
        result = await orchestrator.execute_workflow(
            users=["user1"],
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now(),
        )

        # Verify cancellation
        assert result.status == WorkflowStatus.CANCELLED
        assert result.error_message == "Workflow was cancelled by user"
        assert len(result.stages_completed) == 2  # validate and initialize
        orchestrator._cleanup_clients.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_workflow_with_error(self, orchestrator):
        """Test workflow execution with error."""
        # Mock stage to raise error
        orchestrator._stage_validate_configuration = AsyncMock(
            side_effect=WesError("Configuration validation failed")
        )
        orchestrator._cleanup_clients = AsyncMock()

        # Execute workflow
        result = await orchestrator.execute_workflow(
            users=["user1"],
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now(),
        )

        # Verify error handling
        assert result.status == WorkflowStatus.FAILED
        assert "Configuration validation failed" in result.error_message
        assert result.execution_time > 0
        orchestrator._cleanup_clients.assert_called_once()

    @pytest.mark.asyncio
    async def test_stage_validate_configuration_success(
        self, orchestrator, mock_config_manager
    ):
        """Test successful configuration validation."""
        mock_config_manager.validate_configuration.return_value = True
        mock_config_manager.retrieve_credential.side_effect = (
            lambda service, key: f"test_{key}"
        )

        # Should not raise any exception
        await orchestrator._stage_validate_configuration()

        mock_config_manager.validate_configuration.assert_called_once()
        mock_config_manager.retrieve_credential.assert_any_call("jira", "api_token")
        mock_config_manager.retrieve_credential.assert_any_call("ai", "gemini_api_key")

    @pytest.mark.asyncio
    async def test_stage_validate_configuration_missing_credentials(
        self, orchestrator, mock_config_manager
    ):
        """Test configuration validation with missing credentials."""
        # Override the side_effect to return None
        mock_config_manager.retrieve_credential.side_effect = None
        mock_config_manager.retrieve_credential.return_value = None

        with pytest.raises(WesError, match="Jira API token not configured"):
            await orchestrator._stage_validate_configuration()

    @pytest.mark.asyncio
    async def test_stage_initialize_clients(self, orchestrator, mock_config_manager):
        """Test client initialization."""
        # Configure mocks
        mock_jira = Mock()
        mock_gemini = Mock()

        # Mock service factory methods
        orchestrator.service_factory.create_jira_client = AsyncMock(
            return_value=mock_jira
        )
        orchestrator.service_factory.create_gemini_client = AsyncMock(
            return_value=mock_gemini
        )

        # Execute initialization
        await orchestrator._stage_initialize_clients()

        # Verify clients were created
        assert orchestrator.jira_client == mock_jira
        assert orchestrator.gemini_client == mock_gemini

        # Verify factory methods were called
        orchestrator.service_factory.create_jira_client.assert_called_once()
        orchestrator.service_factory.create_gemini_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_stage_fetch_jira_data(self, orchestrator):
        """Test Jira data fetching."""
        # Mock Jira client
        mock_jira = AsyncMock()
        mock_activities = [
            {"id": "TEST-1", "summary": "Issue 1"},
            {"id": "TEST-2", "summary": "Issue 2"},
        ]
        mock_jira.get_user_activities.return_value = mock_activities
        orchestrator.jira_client = mock_jira

        # Fetch data
        users = ["user1", "user2"]
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()

        result = await orchestrator._stage_fetch_jira_data(users, start_date, end_date)

        # Verify
        assert result == mock_activities
        mock_jira.get_user_activities.assert_called_once_with(
            users=users,
            start_date=start_date,
            end_date=end_date,
            include_comments=True,
            max_results=1000,
        )

    @pytest.mark.asyncio
    async def test_stage_fetch_jira_data_error(self, orchestrator):
        """Test Jira data fetching with error."""
        # Mock Jira client to raise error
        mock_jira = AsyncMock()
        mock_jira.get_user_activities.side_effect = Exception("API Error")
        orchestrator.jira_client = mock_jira

        with pytest.raises(JiraIntegrationError, match="Failed to fetch Jira data"):
            await orchestrator._stage_fetch_jira_data(
                ["user1"], datetime.now(), datetime.now()
            )

    @pytest.mark.asyncio
    async def test_stage_generate_summary(self, orchestrator, mock_config_manager):
        """Test summary generation."""
        # Mock Gemini client
        mock_gemini = AsyncMock()
        mock_summary = {
            "content": "Generated summary",
            "tokens_used": 500,
            "model": "gemini-2.5-flash",
        }
        mock_gemini.generate_summary.return_value = mock_summary
        orchestrator.gemini_client = mock_gemini

        # Generate summary
        activity_data = [{"id": "TEST-1", "summary": "Test issue"}]
        result = await orchestrator._stage_generate_summary(
            activity_data, "Custom prompt"
        )

        # Verify
        assert result == mock_summary
        ai_config = mock_config_manager.get_ai_config()
        mock_gemini.generate_summary.assert_called_once_with(
            activity_data=activity_data,
            custom_prompt="Custom prompt",
            temperature=ai_config.temperature,
            max_tokens=ai_config.max_tokens,
        )

    @pytest.mark.asyncio
    async def test_cleanup_clients(self, orchestrator):
        """Test client cleanup."""
        # Mock service factory close_all method
        orchestrator.service_factory.close_all = AsyncMock()

        # Cleanup
        await orchestrator._cleanup_clients()

        # Verify service factory close_all was called
        orchestrator.service_factory.close_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_clients_with_error(self, orchestrator):
        """Test client cleanup with errors."""
        # Mock service factory that raises error
        orchestrator.service_factory.close_all = AsyncMock(
            side_effect=Exception("Cleanup error")
        )

        # Should not raise exception
        await orchestrator._cleanup_clients()

    @pytest.mark.asyncio
    async def test_test_connections(self, orchestrator):
        """Test connection testing functionality."""
        with (
            patch.object(
                orchestrator, "_stage_validate_configuration", new_callable=AsyncMock
            ),
            patch.object(
                orchestrator, "_stage_initialize_clients", new_callable=AsyncMock
            ),
            patch.object(orchestrator, "_cleanup_clients", new_callable=AsyncMock),
        ):

            # Mock service factory health check
            health_results = {
                "jira": {"healthy": True, "message": "Connected"},
                "gemini": {"healthy": True, "message": "API key valid"},
            }
            orchestrator.service_factory.health_check_all = AsyncMock(
                return_value=health_results
            )

            # Test connections
            results = await orchestrator.test_connections()

            # Verify results
            assert results["jira"] is True
            assert results["gemini"] is True

            # Verify cleanup was called
            orchestrator._cleanup_clients.assert_called_once()
