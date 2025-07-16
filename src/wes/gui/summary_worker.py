"""Background worker for summary generation."""

import asyncio
from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal

from ..core.orchestrator import WorkflowOrchestrator, WorkflowResult
from ..utils.exceptions import WesError
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
    ):
        """Initialize summary worker.

        Args:
            orchestrator: Workflow orchestrator instance
            users: List of usernames to fetch activities for
            start_date: Start date for activity range
            end_date: End date for activity range
            custom_prompt: Optional custom prompt for AI generation
        """
        super().__init__()

        self.logger = get_logger(__name__)
        self.orchestrator = orchestrator
        self.users = users
        self.start_date = start_date
        self.end_date = end_date
        self.custom_prompt = custom_prompt

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
                )
            )

            # Close the loop
            loop.close()

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

        except Exception as e:
            self.logger.error(f"Summary worker error: {e}")
            self.generation_failed.emit(str(e))

    def cancel(self):
        """Cancel the summary generation."""
        self.logger.info("Cancelling summary generation")
        self.orchestrator.cancel()
