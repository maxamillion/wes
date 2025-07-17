"""Workflow orchestrator for executive summary generation."""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..core.config_manager import ConfigManager
from ..core.service_factory import ServiceFactory
from ..integrations.gemini_client import SummaryFormatter
from ..integrations.jira_client import JiraActivitySummary
from ..utils.exceptions import (
    GeminiIntegrationError,
    JiraIntegrationError,
    WesError,
)
from ..utils.logging_config import get_logger, get_security_logger


class WorkflowStatus(Enum):
    """Workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowResult:
    """Result of workflow execution."""

    status: WorkflowStatus
    summary_data: Optional[Dict[str, Any]] = None
    summary_content: Optional[str] = None
    activity_count: int = 0
    execution_time: float = 0.0
    error_message: Optional[str] = None
    stages_completed: Optional[List[str]] = None

    def __post_init__(self):
        if self.stages_completed is None:
            self.stages_completed = []


class WorkflowOrchestrator:
    """Orchestrates the complete executive summary generation workflow.

    This class manages the entire workflow from fetching Jira data to generating
    executive summaries. It coordinates between different service clients and handles
    the workflow stages, error recovery, and progress tracking.

    Attributes:
        config_manager: Configuration manager instance
        service_factory: Factory for creating service clients
        is_cancelled: Flag to track workflow cancellation
        progress_callback: Optional callback for progress updates
        stages: List of workflow stage names
        current_stage: Index of current stage being executed

    Example:
        ```python
        orchestrator = WorkflowOrchestrator(config_manager)
        orchestrator.set_progress_callback(update_ui)

        result = await orchestrator.execute_workflow(
            users=["user1", "user2"],
            start_date=start,
            end_date=end,
            document_title="Weekly Summary"
        )
        ```
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        self.config_manager = config_manager
        self.logger = get_logger(__name__)
        self.security_logger = get_security_logger()

        # Service factory for client management
        self.service_factory = ServiceFactory(config_manager)

        # Clients (will be created by factory)
        self.jira_client: Optional[Any] = None
        self.gemini_client: Optional[Any] = None

        # Workflow state
        self.is_cancelled: bool = False
        self.progress_callback: Optional[Callable[[str, int], None]] = None

        # Workflow stages
        self.stages = [
            "validate_configuration",
            "initialize_clients",
            "fetch_jira_data",
            "generate_summary",
            "finalize",
        ]
        self.current_stage = 0

    def set_progress_callback(self, callback: Callable[[str, int], None]) -> None:
        """Set callback for progress updates.

        The callback will be called with progress messages and percentage.

        Args:
            callback: Function that accepts message (str) and percentage (int)
        """
        self.progress_callback = callback

    def _update_progress(self, message: str, percentage: Optional[int] = None) -> None:
        """Update progress if callback is set.

        Args:
            message: Progress message to display
            percentage: Optional progress percentage (0-100)
        """
        if self.progress_callback:
            if percentage is None:
                percentage = int((self.current_stage / len(self.stages)) * 100)
            self.progress_callback(message, percentage)

    def cancel(self) -> None:
        """Cancel the workflow execution."""
        self.is_cancelled = True
        self.logger.info("Workflow cancellation requested")
    
    def _check_cancelled(self) -> bool:
        """Check if the workflow has been cancelled."""
        return self.is_cancelled

    async def execute_manager_team_workflow(
        self,
        manager_identifier: str,
        start_date: datetime,
        end_date: datetime,
        custom_prompt: Optional[str] = None,
    ) -> WorkflowResult:
        """Execute workflow for a manager's entire team using LDAP.

        This is a convenience method that automatically uses LDAP to fetch
        the full organizational hierarchy for a manager.

        Args:
            manager_identifier: Manager's email or username
            start_date: Start date for activity range
            end_date: End date for activity range
            custom_prompt: Optional custom prompt for AI generation

        Returns:
            WorkflowResult containing status, summary data, and execution details
        """
        return await self.execute_workflow(
            users=[],  # Will be populated by LDAP
            start_date=start_date,
            end_date=end_date,
            custom_prompt=custom_prompt,
            manager_identifier=manager_identifier,
            use_ldap_hierarchy=True,
        )

    async def execute_workflow(
        self,
        users: List[str],
        start_date: datetime,
        end_date: datetime,
        custom_prompt: Optional[str] = None,
        manager_identifier: Optional[str] = None,
        use_ldap_hierarchy: bool = False,
    ) -> WorkflowResult:
        """Execute the complete workflow.

        Runs through all workflow stages: validation, client initialization,
        data fetching, and summary generation.

        Args:
            users: List of usernames to fetch activities for
            start_date: Start date for activity range
            end_date: End date for activity range
            custom_prompt: Optional custom prompt for AI generation
            manager_identifier: Manager email/username for LDAP hierarchy queries
            use_ldap_hierarchy: Whether to use LDAP to get full team hierarchy

        Returns:
            WorkflowResult containing status, summary data, and execution details

        Raises:
            WesError: If any stage fails during execution
        """
        start_time = datetime.now()
        result = WorkflowResult(status=WorkflowStatus.RUNNING)

        try:
            self.logger.info("Starting executive summary workflow")
            self.security_logger.log_security_event(
                "workflow_started",
                users_count=len(users),
                date_range=f"{start_date.date()} to {end_date.date()}",
            )

            # Stage 1: Validate configuration
            await self._execute_stage("validate_configuration", result)
            if self._check_cancelled():
                return self._handle_cancellation(result)

            # Stage 2: Initialize clients
            await self._execute_stage("initialize_clients", result)
            if self._check_cancelled():
                return self._handle_cancellation(result)

            # Stage 3: Fetch Jira data
            if use_ldap_hierarchy and manager_identifier:
                # Use LDAP to get team hierarchy
                activity_data = await self._execute_stage(
                    "fetch_jira_data_with_ldap",
                    result,
                    manager_identifier,
                    start_date,
                    end_date,
                )
            else:
                # Use standard user list
                activity_data = await self._execute_stage(
                    "fetch_jira_data", result, users, start_date, end_date
                )
            if self._check_cancelled():
                return self._handle_cancellation(result)

            result.activity_count = len(activity_data)

            # Stage 4: Generate summary
            summary = await self._execute_stage(
                "generate_summary", result, activity_data, custom_prompt
            )
            if self._check_cancelled():
                return self._handle_cancellation(result)

            result.summary_content = summary.get("content", "")
            result.summary_data = summary

            # Stage 5: Finalize
            await self._execute_stage("finalize", result)

            # Complete workflow
            result.status = WorkflowStatus.COMPLETED
            result.execution_time = (datetime.now() - start_time).total_seconds()

            self.logger.info(
                f"Workflow completed successfully in {result.execution_time:.2f}s"
            )
            self.security_logger.log_security_event(
                "workflow_completed",
                execution_time=result.execution_time,
                activity_count=result.activity_count,
            )

            return result

        except Exception as e:
            result.status = WorkflowStatus.FAILED
            result.error_message = str(e)
            result.execution_time = (datetime.now() - start_time).total_seconds()

            self.logger.error(f"Workflow failed: {e}")
            self.security_logger.log_security_event(
                "workflow_failed",
                error_type=type(e).__name__,
                error_message=str(e),
                execution_time=result.execution_time,
            )

            return result

        finally:
            await self._cleanup_clients()

    async def _execute_stage(
        self, stage_name: str, result: WorkflowResult, *args, **kwargs
    ):
        """Execute a specific workflow stage.

        Manages individual stage execution with progress tracking and error handling.
        Updates the result object with completed stages.

        Args:
            stage_name: Name of the stage to execute
            result: WorkflowResult object to update
            *args: Positional arguments for the stage method
            **kwargs: Keyword arguments for the stage method

        Returns:
            Result from the stage execution

        Raises:
            WesError: If the stage fails
        """
        self.current_stage = self.stages.index(stage_name)
        stage_number = self.current_stage + 1

        self.logger.info(f"Executing stage {stage_number}: {stage_name}")
        self._update_progress(
            f"Stage {stage_number}: {stage_name.replace('_', ' ').title()}"
        )

        try:
            # Get the method for this stage
            method = getattr(self, f"_stage_{stage_name}")
            stage_result = await method(*args, **kwargs)

            if result.stages_completed is not None:
                result.stages_completed.append(stage_name)
            self.logger.info(f"Stage {stage_number} completed: {stage_name}")

            return stage_result

        except Exception as e:
            self.logger.error(f"Stage {stage_number} failed: {stage_name} - {e}")
            raise WesError(f"Stage {stage_name} failed: {e}")

    async def _stage_validate_configuration(self) -> None:
        """Stage 1: Validate configuration."""
        self._update_progress("Validating configuration...")

        if not self.config_manager.validate_configuration():
            raise WesError("Configuration validation failed")

        # Check essential credentials
        jira_token = self.config_manager.retrieve_credential("jira", "api_token")
        if not jira_token:
            raise WesError("Jira API token not configured")

        gemini_key = self.config_manager.retrieve_credential("ai", "gemini_api_key")
        if not gemini_key:
            raise WesError("Gemini API key not configured")

        self.logger.info("Configuration validation passed")

    async def _stage_initialize_clients(self) -> None:
        """Stage 2: Initialize API clients using factory."""
        self._update_progress("Initializing API clients...")

        try:
            # Check if we should use LDAP-enabled Red Hat Jira
            jira_config = self.config_manager.get_jira_config()
            ldap_config = self.config_manager.get_ldap_config()

            if ldap_config.enabled and "redhat.com" in jira_config.url:
                # Use LDAP-enabled Red Hat Jira integration
                self.jira_client = (
                    await self.service_factory.create_redhat_jira_ldap_integration()
                )
                self.logger.info("Using Red Hat Jira with LDAP integration")
            else:
                # Use standard Jira client
                self.jira_client = await self.service_factory.create_jira_client()

            self.gemini_client = await self.service_factory.create_gemini_client()

            self.logger.info("API clients initialized successfully")

        except Exception as e:
            raise WesError(f"Failed to initialize clients: {e}")

    async def _stage_fetch_jira_data(
        self, users: List[str], start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Stage 3: Fetch data from Jira."""
        self._update_progress("Fetching Jira activity data...")

        try:
            activity_data = await self.jira_client.get_user_activities(
                users=users,
                start_date=start_date,
                end_date=end_date,
                include_comments=True,
                max_results=1000,
            )

            self.logger.info(f"Fetched {len(activity_data)} activities from Jira")

            if not activity_data:
                self.logger.warning("No activity data found for the specified criteria")
            else:
                # Log summary of fetched data for debugging
                valid_activities = [
                    a for a in activity_data if not a.get("_processing_error")
                ]
                error_activities = [
                    a for a in activity_data if a.get("_processing_error")
                ]

                self.logger.info(
                    f"Valid activities: {len(valid_activities)}, Error activities: {len(error_activities)}"
                )

                if error_activities:
                    self.logger.warning(
                        f"Failed to process {len(error_activities)} issues:"
                    )
                    for activity in error_activities:
                        self.logger.warning(
                            f"  - {activity.get('id', 'UNKNOWN')}: {activity.get('_processing_error', 'Unknown error')}"
                        )

                # Log a sample of the data structure for debugging (first activity only)
                if activity_data and self.logger.isEnabledFor(logging.DEBUG):
                    first_activity = activity_data[0].copy()
                    # Remove potentially sensitive data for logging
                    first_activity.pop("description", None)
                    first_activity.pop("comments", None)
                    self.logger.debug(
                        f"Sample activity structure: {json.dumps(first_activity, indent=2, default=str)}"
                    )

            return activity_data

        except Exception as e:
            raise JiraIntegrationError(f"Failed to fetch Jira data: {e}")

    async def _stage_fetch_jira_data_with_ldap(
        self, manager_identifier: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Stage 3 Alternative: Fetch data from Jira using LDAP hierarchy."""
        self._update_progress("Fetching team hierarchy from LDAP...")

        try:
            # Check if we have the LDAP-enabled integration
            from ..integrations.redhat_jira_ldap_integration import (
                RedHatJiraLDAPIntegration,
            )

            if not isinstance(self.jira_client, RedHatJiraLDAPIntegration):
                self.logger.warning(
                    "LDAP-enabled Jira client not available, falling back to standard fetch"
                )
                # Fall back to using manager identifier as single user
                return await self._stage_fetch_jira_data(
                    users=[manager_identifier],
                    start_date=start_date,
                    end_date=end_date
                )

            # Use LDAP to get full team
            activity_data, hierarchy = (
                await self.jira_client.get_manager_team_activities(
                    manager_identifier=manager_identifier,
                    start_date=start_date,
                    end_date=end_date,
                    include_comments=True,
                    max_results=1000,
                )
            )

            self.logger.info(
                f"Fetched {len(activity_data)} activities for manager {manager_identifier}'s team"
            )

            # Store hierarchy info in result for reference
            if hasattr(self, "result"):
                self.result.hierarchy = hierarchy

            return activity_data

        except Exception as e:
            raise JiraIntegrationError(f"Failed to fetch Jira data with LDAP: {e}")

    async def _stage_generate_summary(
        self, activity_data: List[Dict[str, Any]], custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Stage 4: Generate AI summary."""
        self._update_progress("Generating AI summary...")

        try:
            # Filter out activities with processing errors before sending to Gemini
            valid_activities = [
                a for a in activity_data if not a.get("_processing_error")
            ]

            if not valid_activities:
                # If all activities had errors, create a special summary
                self.logger.error(
                    "No valid activities to summarize - all had processing errors"
                )
                return WorkflowResult(
                    status=WorkflowStatus.FAILED,
                    summary_data=None,
                    summary_content=None
                )

            ai_config = self.config_manager.get_ai_config()

            summary = await self.gemini_client.generate_summary(
                activity_data=valid_activities,  # Only send valid activities
                custom_prompt=custom_prompt or ai_config.custom_prompt,
                temperature=ai_config.temperature,
                max_tokens=ai_config.max_tokens,
            )

            self.logger.info("AI summary generated successfully")
            return summary

        except Exception as e:
            raise GeminiIntegrationError(f"Failed to generate summary: {e}")

    async def _stage_finalize(self) -> None:
        """Stage 5: Finalize workflow."""
        self._update_progress("Finalizing...")

        # Perform any cleanup or final tasks
        await asyncio.sleep(0.5)  # Brief pause for UI

        self.logger.info("Workflow finalization completed")

    def _handle_cancellation(self, result: WorkflowResult) -> WorkflowResult:
        """Handle workflow cancellation."""
        result.status = WorkflowStatus.CANCELLED
        result.error_message = "Workflow was cancelled by user"

        self.logger.info("Workflow cancelled by user")
        self.security_logger.log_security_event(
            "workflow_cancelled",
            stage=self.current_stage,
            stages_completed=len(result.stages_completed) if result.stages_completed else 0,
        )

        return result

    async def _cleanup_clients(self):
        """Clean up API clients using factory."""
        try:
            await self.service_factory.close_all()
            self.logger.info("API clients cleaned up")

        except Exception as e:
            self.logger.error(f"Error during client cleanup: {e}")

    async def test_connections(self) -> Dict[str, bool]:
        """Test all API connections using service factory."""
        self.logger.info("Testing API connections")

        try:
            # Validate configuration first
            await self._stage_validate_configuration()

            # Use factory's health check functionality
            health_results = await self.service_factory.health_check_all()

            # Convert health check results to simple boolean
            results = {
                service: health["healthy"] for service, health in health_results.items()
            }

            self.logger.info(f"Connection test results: {results}")
            return results

        except Exception as e:
            self.logger.error(f"Connection test error: {e}")
            return {"jira": False, "gemini": False}

        finally:
            await self._cleanup_clients()

    def get_activity_summary(
        self, activity_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get summary statistics of activity data."""
        return JiraActivitySummary.summarize_activities(activity_data)
