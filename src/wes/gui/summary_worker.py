"""Background worker for summary generation."""

import asyncio
from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import QThread, Signal

from ..core.orchestrator import WorkflowOrchestrator
from ..utils.logging_config import get_logger


class SummaryWorker(QThread):
    """Background worker for generating executive summaries.

    Runs the workflow orchestrator in a separate thread to keep UI responsive.
    """

    # Signals
    progress_update = Signal(str, int)  # message, percentage
    generation_complete = Signal(object)  # WorkflowResult
    generation_failed = Signal(str)  # error message

    def __init__(
        self,
        orchestrator: WorkflowOrchestrator,
        users: List[str],
        start_date: datetime,
        end_date: datetime,
        custom_prompt: Optional[str] = None,
        manager_identifier: Optional[str] = None,
        use_ldap_hierarchy: bool = False,
    ):
        """Initialize summary worker.

        Args:
            orchestrator: Workflow orchestrator instance
            users: List of usernames to fetch activities for
            start_date: Start date for activity range
            end_date: End date for activity range
            custom_prompt: Optional custom prompt for AI generation
            manager_identifier: Optional manager email/username for LDAP hierarchy
            use_ldap_hierarchy: Whether to use LDAP to fetch team hierarchy
        """
        super().__init__()

        self.logger = get_logger(__name__)
        self.orchestrator = orchestrator
        self.users = users
        self.start_date = start_date
        self.end_date = end_date
        self.custom_prompt = custom_prompt
        self.manager_identifier = manager_identifier
        self.use_ldap_hierarchy = use_ldap_hierarchy

        # Set up progress callback
        self.orchestrator.set_progress_callback(self._on_progress)

    def _on_progress(self, message: str, percentage: int):
        """Handle progress updates from orchestrator.

        Args:
            message: Progress message
            percentage: Progress percentage (0-100)
        """
        self.progress_update.emit(message, percentage)

    def run(self):
        """Run the summary generation workflow."""
        loop = None
        try:
            self.logger.info("Starting summary generation in background")

            # Create event loop for async operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the workflow
            result = loop.run_until_complete(
                self.orchestrator.execute_workflow(
                    users=self.users,
                    start_date=self.start_date,
                    end_date=self.end_date,
                    custom_prompt=self.custom_prompt,
                    manager_identifier=self.manager_identifier,
                    use_ldap_hierarchy=self.use_ldap_hierarchy,
                )
            )

            # Emit result
            if result.status.value == "completed":
                self.logger.info("Summary generation completed successfully")
                self.generation_complete.emit(result)
            elif result.status.value == "cancelled":
                self.logger.info("Summary generation cancelled")
                self.generation_failed.emit("Generation cancelled by user")
            else:
                error_msg = result.error_message or "Unknown error occurred"
                self.logger.error(f"Summary generation failed: {error_msg}")
                self.generation_failed.emit(error_msg)

        except asyncio.CancelledError:
            self.logger.info("Summary generation was cancelled")
            self.generation_failed.emit("Generation cancelled by user")
        except Exception as e:
            # Check if the error message indicates cancellation
            error_msg = str(e)
            if "cancelled by user" in error_msg.lower():
                self.logger.info("Summary generation cancelled by user")
                self.generation_failed.emit("Generation cancelled by user")
            else:
                self.logger.error(f"Summary worker error: {e}")
                self.generation_failed.emit(error_msg)
        finally:
            # Always clean up the event loop
            if loop is not None:
                try:
                    # Cancel all running tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()

                    # Wait briefly for tasks to cancel
                    if pending:
                        loop.run_until_complete(
                            asyncio.gather(*pending, return_exceptions=True)
                        )

                    loop.close()
                except Exception as e:
                    self.logger.error(f"Error closing event loop: {e}")

    def cancel(self):
        """Cancel the summary generation."""
        self.logger.info("Cancelling summary generation")
        self.orchestrator.cancel()
