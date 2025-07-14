"""Google Docs integration client for creating and managing executive summary documents."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..utils.exceptions import (
    AuthenticationError,
    GoogleDocsIntegrationError,
    RateLimitError,
)
from ..utils.logging_config import get_logger, get_security_logger
from ..utils.validators import InputValidator


class GoogleDocsClient:
    """Secure Google Docs API client for document creation and management."""

    # OAuth 2.0 scopes
    SCOPES = [
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/drive.file",
    ]

    def __init__(
        self,
        service_account_path: Optional[str] = None,
        oauth_credentials: Optional[Dict[str, str]] = None,
        rate_limit: int = 100,
        timeout: int = 30,
    ):
        self.logger = get_logger(__name__)
        self.security_logger = get_security_logger()

        self.service_account_path = service_account_path
        self.oauth_credentials = oauth_credentials
        self.timeout = timeout
        self.rate_limit = rate_limit

        # Initialize rate limiter
        self.rate_limiter = self._create_rate_limiter()

        # Initialize Google services
        self.docs_service = None
        self.drive_service = None
        self._initialize_services()

    def _create_rate_limiter(self):
        """Create rate limiter for API requests."""

        class RateLimiter:
            def __init__(self, max_requests: int, time_window: int = 60):
                self.max_requests = max_requests
                self.time_window = time_window
                self.requests = []
                self._lock = asyncio.Lock()

            async def acquire(self):
                async with self._lock:
                    now = time.time()

                    # Remove old requests
                    self.requests = [
                        req_time
                        for req_time in self.requests
                        if now - req_time < self.time_window
                    ]

                    # Check if we're at the limit
                    if len(self.requests) >= self.max_requests:
                        wait_time = self.time_window - (now - self.requests[0])
                        if wait_time > 0:
                            await asyncio.sleep(wait_time)
                            return await self.acquire()

                    # Add current request
                    self.requests.append(now)

        return RateLimiter(max_requests=self.rate_limit, time_window=60)

    def _initialize_services(self) -> None:
        """Initialize Google API services."""
        try:
            # Get credentials
            credentials = self._get_credentials()

            # Build services
            self.docs_service = build("docs", "v1", credentials=credentials)
            self.drive_service = build("drive", "v3", credentials=credentials)

            # Test connection
            self._test_connection()

            self.security_logger.log_authentication_attempt(
                service="google_docs", success=True
            )

            self.logger.info("Google Docs client initialized successfully")

        except Exception as e:
            self.security_logger.log_authentication_attempt(
                service="google_docs", success=False, error=str(e)
            )
            raise AuthenticationError(f"Google Docs authentication failed: {e}")

    def _get_credentials(self) -> Credentials:
        """Get Google API credentials."""
        try:
            if self.service_account_path:
                # Use service account credentials
                credentials = service_account.Credentials.from_service_account_file(
                    self.service_account_path, scopes=self.SCOPES
                )
                return credentials

            elif self.oauth_credentials:
                # Use OAuth credentials
                return self._get_oauth_credentials()

            else:
                raise AuthenticationError("No credentials provided")

        except Exception as e:
            raise AuthenticationError(f"Failed to get credentials: {e}")

    def _get_oauth_credentials(self) -> Credentials:
        """Get OAuth 2.0 credentials."""
        try:
            # Create credentials from stored token
            credentials = Credentials(
                token=self.oauth_credentials.get("access_token"),
                refresh_token=self.oauth_credentials.get("refresh_token"),
                token_uri=self.oauth_credentials.get("token_uri"),
                client_id=self.oauth_credentials.get("client_id"),
                client_secret=self.oauth_credentials.get("client_secret"),
                scopes=self.SCOPES,
            )

            # Refresh if needed
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())

            return credentials

        except Exception as e:
            raise AuthenticationError(f"Failed to get OAuth credentials: {e}")

    def _test_connection(self) -> None:
        """Test Google Docs connection."""
        try:
            # Test with a simple API call
            self.docs_service.documents().get(documentId="test").execute()

        except HttpError as e:
            if e.resp.status == 404:
                # Expected - document doesn't exist
                self.logger.info("Google Docs connection test successful")
            else:
                raise AuthenticationError(f"Google Docs connection test failed: {e}")
        except Exception as e:
            raise AuthenticationError(f"Google Docs connection test failed: {e}")

    async def create_document(self, title: str, folder_id: Optional[str] = None) -> str:
        """Create a new Google Doc."""
        try:
            await self.rate_limiter.acquire()

            # Validate title
            title = InputValidator.sanitize_text(title)

            # Create document
            document = {"title": title}

            doc = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.docs_service.documents().create(body=document).execute(),
            )

            document_id = doc.get("documentId")

            # Move to folder if specified
            if folder_id:
                await self._move_to_folder(document_id, folder_id)

            self.security_logger.log_api_request(
                service="google_docs",
                endpoint="documents.create",
                method="POST",
                status_code=200,
                document_id=document_id,
            )

            self.logger.info(f"Document created: {document_id}")
            return document_id

        except Exception as e:
            self.logger.error(f"Failed to create document: {e}")
            raise GoogleDocsIntegrationError(f"Failed to create document: {e}")

    async def _move_to_folder(self, document_id: str, folder_id: str) -> None:
        """Move document to specified folder."""
        try:
            await self.rate_limiter.acquire()

            # Get current parents
            file = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.drive_service.files()
                .get(fileId=document_id, fields="parents")
                .execute(),
            )

            previous_parents = ",".join(file.get("parents", []))

            # Move to new folder
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.drive_service.files()
                .update(
                    fileId=document_id,
                    addParents=folder_id,
                    removeParents=previous_parents,
                    fields="id, parents",
                )
                .execute(),
            )

            self.logger.info(f"Document {document_id} moved to folder {folder_id}")

        except Exception as e:
            self.logger.error(f"Failed to move document to folder: {e}")
            # Don't raise exception for folder move failure

    async def add_content(
        self, document_id: str, content: str, insert_index: int = 1
    ) -> None:
        """Add content to a Google Doc."""
        try:
            await self.rate_limiter.acquire()

            # Validate and sanitize content
            content = InputValidator.sanitize_text(content)

            # Create requests to insert content
            requests = [
                {"insertText": {"location": {"index": insert_index}, "text": content}}
            ]

            # Execute batch update
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.docs_service.documents()
                .batchUpdate(documentId=document_id, body={"requests": requests})
                .execute(),
            )

            self.security_logger.log_api_request(
                service="google_docs",
                endpoint="documents.batchUpdate",
                method="POST",
                status_code=200,
                document_id=document_id,
            )

            self.logger.info(f"Content added to document: {document_id}")

        except Exception as e:
            self.logger.error(f"Failed to add content: {e}")
            raise GoogleDocsIntegrationError(f"Failed to add content: {e}")

    async def format_document(
        self, document_id: str, formatting_requests: List[Dict[str, Any]]
    ) -> None:
        """Apply formatting to a Google Doc."""
        try:
            await self.rate_limiter.acquire()

            # Execute batch update with formatting
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.docs_service.documents()
                .batchUpdate(
                    documentId=document_id, body={"requests": formatting_requests}
                )
                .execute(),
            )

            self.logger.info(f"Formatting applied to document: {document_id}")

        except Exception as e:
            self.logger.error(f"Failed to format document: {e}")
            raise GoogleDocsIntegrationError(f"Failed to format document: {e}")

    async def create_formatted_summary(
        self, title: str, summary_content: str, folder_id: Optional[str] = None
    ) -> str:
        """Create a formatted executive summary document."""
        try:
            # Create document
            document_id = await self.create_document(title, folder_id)

            # Prepare formatted content
            formatted_content = self._prepare_summary_content(summary_content)

            # Add content
            await self.add_content(document_id, formatted_content)

            # Apply formatting
            formatting_requests = self._create_formatting_requests(formatted_content)
            if formatting_requests:
                await self.format_document(document_id, formatting_requests)

            self.logger.info(f"Formatted summary document created: {document_id}")
            return document_id

        except Exception as e:
            self.logger.error(f"Failed to create formatted summary: {e}")
            raise GoogleDocsIntegrationError(f"Failed to create formatted summary: {e}")

    def _prepare_summary_content(self, summary_content: str) -> str:
        """Prepare summary content with proper formatting."""
        # Add header
        formatted = f"EXECUTIVE SUMMARY\n\n"
        formatted += f"Generated on: {time.strftime('%B %d, %Y at %I:%M %p')}\n\n"
        formatted += "─" * 50 + "\n\n"

        # Add main content
        formatted += summary_content

        # Add footer
        formatted += "\n\n" + "─" * 50 + "\n"
        formatted += "Generated by Executive Summary Tool\n"
        formatted += "Confidential - Internal Use Only"

        return formatted

    def _create_formatting_requests(self, content: str) -> List[Dict[str, Any]]:
        """Create formatting requests for document styling."""
        requests = []

        # Title formatting
        requests.append(
            {
                "updateTextStyle": {
                    "range": {"startIndex": 1, "endIndex": 18},  # "EXECUTIVE SUMMARY"
                    "textStyle": {
                        "bold": True,
                        "fontSize": {"magnitude": 16, "unit": "PT"},
                    },
                    "fields": "bold,fontSize",
                }
            }
        )

        # Header formatting
        requests.append(
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": 1, "endIndex": 18},
                    "paragraphStyle": {"alignment": "CENTER"},
                    "fields": "alignment",
                }
            }
        )

        return requests

    async def share_document(
        self, document_id: str, email: str, role: str = "reader"
    ) -> None:
        """Share document with specified email."""
        try:
            await self.rate_limiter.acquire()

            # Validate email
            if not InputValidator.validate_user_identifier(email):
                raise GoogleDocsIntegrationError(f"Invalid email address: {email}")

            # Create permission
            permission = {"type": "user", "role": role, "emailAddress": email}

            # Add permission
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.drive_service.permissions()
                .create(fileId=document_id, body=permission, sendNotificationEmail=True)
                .execute(),
            )

            self.security_logger.log_api_request(
                service="google_docs",
                endpoint="permissions.create",
                method="POST",
                status_code=200,
                document_id=document_id,
                shared_with=email,
            )

            self.logger.info(f"Document {document_id} shared with {email}")

        except Exception as e:
            self.logger.error(f"Failed to share document: {e}")
            raise GoogleDocsIntegrationError(f"Failed to share document: {e}")

    async def get_document_url(self, document_id: str) -> str:
        """Get the URL for a document."""
        return f"https://docs.google.com/document/d/{document_id}/edit"

    async def get_document_content(self, document_id: str) -> str:
        """Get the text content of a document."""
        try:
            await self.rate_limiter.acquire()

            # Get document
            doc = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.docs_service.documents()
                .get(documentId=document_id)
                .execute(),
            )

            # Extract text content
            content = ""
            for element in doc.get("body", {}).get("content", []):
                if "paragraph" in element:
                    paragraph = element["paragraph"]
                    for text_element in paragraph.get("elements", []):
                        if "textRun" in text_element:
                            content += text_element["textRun"]["content"]

            return content

        except Exception as e:
            self.logger.error(f"Failed to get document content: {e}")
            raise GoogleDocsIntegrationError(f"Failed to get document content: {e}")

    async def update_document_content(self, document_id: str, new_content: str) -> None:
        """Update the entire content of a document."""
        try:
            await self.rate_limiter.acquire()

            # Get current document length
            doc = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.docs_service.documents()
                .get(documentId=document_id)
                .execute(),
            )

            # Calculate end index
            end_index = 1
            for element in doc.get("body", {}).get("content", []):
                if "paragraph" in element:
                    end_index = element["endIndex"]

            # Create requests to replace content
            requests = [
                {
                    "deleteContentRange": {
                        "range": {"startIndex": 1, "endIndex": end_index - 1}
                    }
                },
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": InputValidator.sanitize_text(new_content),
                    }
                },
            ]

            # Execute batch update
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.docs_service.documents()
                .batchUpdate(documentId=document_id, body={"requests": requests})
                .execute(),
            )

            self.logger.info(f"Document content updated: {document_id}")

        except Exception as e:
            self.logger.error(f"Failed to update document content: {e}")
            raise GoogleDocsIntegrationError(f"Failed to update document content: {e}")

    async def list_documents(
        self, folder_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List documents in Drive."""
        try:
            await self.rate_limiter.acquire()

            # Build query
            query = "mimeType='application/vnd.google-apps.document'"
            if folder_id:
                query += f" and '{folder_id}' in parents"

            # List files
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.drive_service.files()
                .list(
                    q=query,
                    fields="files(id, name, createdTime, modifiedTime, webViewLink)",
                )
                .execute(),
            )

            documents = []
            for file in results.get("files", []):
                documents.append(
                    {
                        "id": file["id"],
                        "name": file["name"],
                        "created": file["createdTime"],
                        "modified": file["modifiedTime"],
                        "url": file["webViewLink"],
                    }
                )

            return documents

        except Exception as e:
            self.logger.error(f"Failed to list documents: {e}")
            raise GoogleDocsIntegrationError(f"Failed to list documents: {e}")

    async def delete_document(self, document_id: str) -> None:
        """Delete a document."""
        try:
            await self.rate_limiter.acquire()

            # Move to trash
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.drive_service.files()
                .update(fileId=document_id, body={"trashed": True})
                .execute(),
            )

            self.security_logger.log_api_request(
                service="google_docs",
                endpoint="files.update",
                method="PATCH",
                status_code=200,
                document_id=document_id,
                action="delete",
            )

            self.logger.info(f"Document deleted: {document_id}")

        except Exception as e:
            self.logger.error(f"Failed to delete document: {e}")
            raise GoogleDocsIntegrationError(f"Failed to delete document: {e}")

    async def export_document(self, document_id: str, format: str = "pdf") -> bytes:
        """Export document in specified format."""
        try:
            await self.rate_limiter.acquire()

            # Define MIME types
            mime_types = {
                "pdf": "application/pdf",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "txt": "text/plain",
                "html": "text/html",
            }

            mime_type = mime_types.get(format, "application/pdf")

            # Export document
            export_data = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.drive_service.files()
                .export(fileId=document_id, mimeType=mime_type)
                .execute(),
            )

            self.logger.info(f"Document exported: {document_id} as {format}")
            return export_data

        except Exception as e:
            self.logger.error(f"Failed to export document: {e}")
            raise GoogleDocsIntegrationError(f"Failed to export document: {e}")

    async def close(self) -> None:
        """Close client connections."""
        try:
            # Google API clients don't require explicit cleanup
            self.docs_service = None
            self.drive_service = None

            self.logger.info("Google Docs client closed")

        except Exception as e:
            self.logger.error(f"Error closing Google Docs client: {e}")
