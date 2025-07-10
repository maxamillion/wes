"""Workflow orchestrator for executive summary generation."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

from ..integrations.jira_client import JiraClient, JiraActivitySummary
from ..integrations.gemini_client import GeminiClient, SummaryFormatter
from ..integrations.google_docs_client import GoogleDocsClient, DocumentTemplate
from ..core.config_manager import ConfigManager
from ..utils.exceptions import (
    ExecutiveSummaryToolError,
    JiraIntegrationError,
    GeminiIntegrationError,
    GoogleDocsIntegrationError,
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
    document_id: Optional[str] = None
    document_url: Optional[str] = None
    summary_content: Optional[str] = None
    activity_count: int = 0
    execution_time: float = 0.0
    error_message: Optional[str] = None
    stages_completed: List[str] = None

    def __post_init__(self):
        if self.stages_completed is None:
            self.stages_completed = []


class WorkflowOrchestrator:
    """Orchestrates the complete executive summary generation workflow."""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.logger = get_logger(__name__)
        self.security_logger = get_security_logger()

        # Clients
        self.jira_client: Optional[JiraClient] = None
        self.gemini_client: Optional[GeminiClient] = None
        self.google_docs_client: Optional[GoogleDocsClient] = None

        # Workflow state
        self.is_cancelled = False
        self.progress_callback: Optional[Callable[[str, int], None]] = None

        # Workflow stages
        self.stages = [
            "validate_configuration",
            "initialize_clients",
            "fetch_jira_data",
            "generate_summary",
            "create_document",
            "finalize",
        ]
        self.current_stage = 0

    def set_progress_callback(self, callback: Callable[[str, int], None]):
        """Set callback for progress updates."""
        self.progress_callback = callback

    def _update_progress(self, message: str, percentage: int = None):
        """Update progress if callback is set."""
        if self.progress_callback:
            if percentage is None:
                percentage = int((self.current_stage / len(self.stages)) * 100)
            self.progress_callback(message, percentage)

    def cancel(self):
        """Cancel the workflow execution."""
        self.is_cancelled = True
        self.logger.info("Workflow cancellation requested")

    async def execute_workflow(
        self,
        users: List[str],
        start_date: datetime,
        end_date: datetime,
        document_title: Optional[str] = None,
        folder_id: Optional[str] = None,
        share_email: Optional[str] = None,
        custom_prompt: Optional[str] = None,
    ) -> WorkflowResult:
        """Execute the complete workflow."""
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
            if self.is_cancelled:
                return self._handle_cancellation(result)

            # Stage 2: Initialize clients
            await self._execute_stage("initialize_clients", result)
            if self.is_cancelled:
                return self._handle_cancellation(result)

            # Stage 3: Fetch Jira data
            activity_data = await self._execute_stage(
                "fetch_jira_data", result, users, start_date, end_date
            )
            if self.is_cancelled:
                return self._handle_cancellation(result)

            result.activity_count = len(activity_data)

            # Stage 4: Generate summary
            summary = await self._execute_stage(
                "generate_summary", result, activity_data, custom_prompt
            )
            if self.is_cancelled:
                return self._handle_cancellation(result)

            result.summary_content = summary.get("content", "")

            # Stage 5: Create document
            document_info = await self._execute_stage(
                "create_document",
                result,
                summary,
                document_title,
                folder_id,
                share_email,
            )
            if self.is_cancelled:
                return self._handle_cancellation(result)

            result.document_id = document_info.get("document_id")
            result.document_url = document_info.get("document_url")

            # Stage 6: Finalize
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
                document_id=result.document_id,
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
        """Execute a specific workflow stage."""
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

            result.stages_completed.append(stage_name)
            self.logger.info(f"Stage {stage_number} completed: {stage_name}")

            return stage_result

        except Exception as e:
            self.logger.error(f"Stage {stage_number} failed: {stage_name} - {e}")
            raise ExecutiveSummaryToolError(f"Stage {stage_name} failed: {e}")

    async def _stage_validate_configuration(self) -> None:
        """Stage 1: Validate configuration."""
        self._update_progress("Validating configuration...")

        if not self.config_manager.validate_configuration():
            raise ExecutiveSummaryToolError("Configuration validation failed")

        # Check essential credentials
        jira_token = self.config_manager.retrieve_credential("jira", "api_token")
        if not jira_token:
            raise ExecutiveSummaryToolError("Jira API token not configured")

        gemini_key = self.config_manager.retrieve_credential("ai", "gemini_api_key")
        if not gemini_key:
            raise ExecutiveSummaryToolError("Gemini API key not configured")

        self.logger.info("Configuration validation passed")

    async def _stage_initialize_clients(self) -> None:
        """Stage 2: Initialize API clients."""
        self._update_progress("Initializing API clients...")

        try:
            # Initialize Jira client
            jira_config = self.config_manager.get_jira_config()
            jira_token = self.config_manager.retrieve_credential("jira", "api_token")

            self.jira_client = JiraClient(
                url=jira_config.url,
                username=jira_config.username,
                api_token=jira_token,
                rate_limit=jira_config.rate_limit,
                timeout=jira_config.timeout,
            )

            # Initialize Gemini client
            ai_config = self.config_manager.get_ai_config()
            gemini_key = self.config_manager.retrieve_credential("ai", "gemini_api_key")

            self.gemini_client = GeminiClient(
                api_key=gemini_key,
                model_name=ai_config.model_name,
                rate_limit=ai_config.rate_limit,
                timeout=ai_config.timeout,
            )

            # Initialize Google Docs client
            google_config = self.config_manager.get_google_config()

            if google_config.service_account_path:
                self.google_docs_client = GoogleDocsClient(
                    service_account_path=google_config.service_account_path,
                    rate_limit=google_config.rate_limit,
                    timeout=google_config.timeout,
                )
            else:
                # Use OAuth credentials
                oauth_credentials = {
                    "client_id": google_config.oauth_client_id,
                    "client_secret": self.config_manager.retrieve_credential(
                        "google", "oauth_client_secret"
                    ),
                    "refresh_token": self.config_manager.retrieve_credential(
                        "google", "oauth_refresh_token"
                    ),
                }

                self.google_docs_client = GoogleDocsClient(
                    oauth_credentials=oauth_credentials,
                    rate_limit=google_config.rate_limit,
                    timeout=google_config.timeout,
                )

            self.logger.info("API clients initialized successfully")

        except Exception as e:
            raise ExecutiveSummaryToolError(f"Failed to initialize clients: {e}")

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

            return activity_data

        except Exception as e:
            raise JiraIntegrationError(f"Failed to fetch Jira data: {e}")

    async def _stage_generate_summary(
        self, activity_data: List[Dict[str, Any]], custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Stage 4: Generate AI summary."""
        self._update_progress("Generating AI summary...")

        try:
            ai_config = self.config_manager.get_ai_config()

            summary = await self.gemini_client.generate_summary(
                activity_data=activity_data,
                custom_prompt=custom_prompt or ai_config.custom_prompt,
                temperature=ai_config.temperature,
                max_tokens=ai_config.max_tokens,
            )

            self.logger.info("AI summary generated successfully")
            return summary

        except Exception as e:
            raise GeminiIntegrationError(f"Failed to generate summary: {e}")

    async def _stage_create_document(
        self,
        summary: Dict[str, Any],
        document_title: Optional[str] = None,
        folder_id: Optional[str] = None,
        share_email: Optional[str] = None,
    ) -> Dict[str, str]:
        """Stage 5: Create Google Doc."""
        self._update_progress("Creating Google Doc...")

        try:
            # Prepare document title
            if not document_title:
                date_str = datetime.now().strftime("%Y-%m-%d")
                document_title = f"Executive Summary - {date_str}"

            # Format summary content
            formatted_content = SummaryFormatter.format_for_document(summary)

            # Create document
            document_id = await self.google_docs_client.create_formatted_summary(
                title=document_title,
                summary_content=formatted_content,
                folder_id=folder_id,
            )

            # Share document if email provided
            if share_email:
                await self.google_docs_client.share_document(
                    document_id=document_id, email=share_email, role="reader"
                )

            # Get document URL
            document_url = await self.google_docs_client.get_document_url(document_id)

            self.logger.info(f"Google Doc created: {document_id}")

            return {"document_id": document_id, "document_url": document_url}

        except Exception as e:
            raise GoogleDocsIntegrationError(f"Failed to create document: {e}")

    async def _stage_finalize(self) -> None:
        """Stage 6: Finalize workflow."""
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
            stages_completed=len(result.stages_completed),
        )

        return result

    async def _cleanup_clients(self):
        """Clean up API clients."""
        try:
            if self.jira_client:
                await self.jira_client.close()

            if self.gemini_client:
                await self.gemini_client.close()

            if self.google_docs_client:
                await self.google_docs_client.close()

            self.logger.info("API clients cleaned up")

        except Exception as e:
            self.logger.error(f"Error during client cleanup: {e}")

    async def test_connections(self) -> Dict[str, bool]:
        """Test all API connections."""
        self.logger.info("Testing API connections")
        results = {}

        try:
            # Test Jira connection
            try:
                await self._stage_validate_configuration()
                await self._stage_initialize_clients()

                # Test Jira
                if self.jira_client:
                    connection_info = self.jira_client.get_connection_info()
                    results["jira"] = connection_info.get("connected", False)
                else:
                    results["jira"] = False

                # Test Gemini
                if self.gemini_client:
                    results["gemini"] = await self.gemini_client.validate_api_key()
                else:
                    results["gemini"] = False

                # Test Google Docs (basic connection test)
                if self.google_docs_client:
                    # Simple test - try to list documents
                    try:
                        await self.google_docs_client.list_documents()
                        results["google_docs"] = True
                    except Exception:
                        results["google_docs"] = False
                else:
                    results["google_docs"] = False

            except Exception as e:
                self.logger.error(f"Connection test failed: {e}")
                results = {"jira": False, "gemini": False, "google_docs": False}

            finally:
                await self._cleanup_clients()

            self.logger.info(f"Connection test results: {results}")
            return results

        except Exception as e:
            self.logger.error(f"Connection test error: {e}")
            return {"jira": False, "gemini": False, "google_docs": False}

    def get_activity_summary(
        self, activity_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get summary statistics of activity data."""
        return JiraActivitySummary.summarize_activities(activity_data)
