"""Google Gemini AI client for generating executive summaries."""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory

from ..utils.content_sanitizer import ContentSanitizer
from ..utils.exceptions import (
    AuthenticationError,
    GeminiIntegrationError,
    RateLimitError,
)
from ..utils.logging_config import get_logger, get_security_logger
from ..utils.validators import InputValidator


class GeminiClient:
    """Secure Google Gemini AI client for executive summary generation."""

    DEFAULT_EXECUTIVE_PROMPT = """
    You are an executive assistant creating a weekly summary for a senior executive.
    Please analyze the following Jira activity data and create a concise executive summary.

    Focus on:
    - Key achievements and completed work
    - Progress on important initiatives, prioritize importance by jira priority level
    - Any blockers or risks that need executive attention
    - Team productivity insights
    - Upcoming priorities

    Format the summary as a professional executive briefing with clear sections.
    Keep it concise but comprehensive, suitable for a C-level executive.

    Jira Activity Data:
    {activity_data}

    Executive Summary:
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-pro",
        rate_limit: int = 60,
        timeout: int = 60,
    ):
        self.logger = get_logger(__name__)
        self.security_logger = get_security_logger()

        # Validate inputs
        InputValidator.validate_api_key(api_key)

        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        self.rate_limit = rate_limit

        # Initialize rate limiter
        self.rate_limiter = self._create_rate_limiter()

        # Initialize content sanitizer
        self.sanitizer = ContentSanitizer()

        # Initialize Gemini client
        self._initialize_client()

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

    def _initialize_client(self) -> None:
        """Initialize Gemini client with API key."""
        try:
            # Configure API key
            genai.configure(api_key=self.api_key)

            # Initialize model with adjusted safety settings for technical content
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                },
            )

            # Test connection
            self.test_connection()

            self.security_logger.log_authentication_attempt(
                service="gemini", success=True
            )

            self.logger.info("Gemini client initialized successfully")

        except Exception as e:
            self.security_logger.log_authentication_attempt(
                service="gemini", success=False, error=str(e)
            )
            raise AuthenticationError(f"Gemini authentication failed: {e}")

    def test_connection(self) -> None:
        """Test Gemini connection with a simple request."""
        try:
            # Use a simple math question to avoid content filters
            response = self.model.generate_content(
                "What is 2 + 2? Please respond with just the number."
            )

            # Try to access response.text, but catch the specific error
            try:
                if response.text:
                    self.logger.info("Gemini connection test successful")
                    return
            except Exception as text_error:
                # Check if this is the expected error for filtered content
                if "finish_reason" in str(text_error):
                    # This means the API is working but content was filtered
                    self.logger.info(
                        "Gemini connection test successful (content filtered)"
                    )
                    return
                # For other exceptions, check response structure

            # Check if response was blocked by safety filters
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "finish_reason"):
                    # Finish reason 2 = SAFETY, 3 = RECITATION, etc.
                    if candidate.finish_reason in [2, 3]:
                        # This is actually a successful connection, just blocked content
                        self.logger.info(
                            "Gemini connection test successful (content filtered)"
                        )
                        return
                    else:
                        raise Exception(
                            f"Response blocked with finish_reason: "
                            f"{candidate.finish_reason}"
                        )

            # If we have a response object but no text, connection is still valid
            if response:
                self.logger.info("Gemini connection test successful (empty response)")
                return

            raise Exception("No response from Gemini API")

        except AuthenticationError:
            # Re-raise authentication errors
            raise
        except Exception as e:
            # Check if this is the specific text accessor error
            if "response.text" in str(e) and "finish_reason" in str(e):
                self.logger.info("Gemini connection test successful (content filtered)")
                return
            raise AuthenticationError(f"Gemini connection test failed: {e}")

    async def generate_summary(
        self,
        activity_data: List[Dict[str, Any]],
        custom_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Generate executive summary from Jira activity data with safety retry logic."""
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                # Rate limiting
                await self.rate_limiter.acquire()

                # Progressively aggressive sanitization based on attempt
                aggressive = attempt > 0
                if attempt == 2:
                    self.logger.warning(
                        "Using maximum sanitization after safety filter blocks"
                    )

                # Validate and sanitize input data
                sanitized_data = self._sanitize_activity_data(
                    activity_data, aggressive=aggressive
                )

                # On final attempt, use minimal data
                if attempt == 2:
                    self.logger.info("Final attempt: using minimal activity data")
                    sanitized_data = [
                        self.sanitizer.create_summary_safe_activity(activity)
                        for activity in activity_data[:30]  # Limit to 30 activities
                    ]

                # Prepare prompt
                prompt = self._prepare_prompt(sanitized_data, custom_prompt)

                # Generate summary
                response = await self._generate_content(prompt, temperature, max_tokens)

                # Process response
                summary = self._process_response(response)

                self.security_logger.log_api_request(
                    service="gemini",
                    endpoint="generate_content",
                    method="POST",
                    status_code=200,
                    input_tokens=len(prompt.split()),
                    output_tokens=len(summary.get("content", "").split()),
                )

                return summary

            except GeminiIntegrationError as e:
                last_error = e
                error_msg = str(e)

                # Check if it's a safety filter error
                if (
                    "safety filter" in error_msg.lower()
                    or "blocked" in error_msg.lower()
                ):
                    self.logger.warning(
                        f"Attempt {attempt + 1} blocked by safety filters: {error_msg}"
                    )

                    if attempt < max_retries - 1:
                        self.logger.info(
                            f"Retrying with more aggressive sanitization..."
                        )
                        await asyncio.sleep(1)  # Brief delay before retry
                        continue

                    self.logger.error("All attempts failed due to safety filters")
                    # Return a fallback summary
                    return self._create_fallback_summary(activity_data, error_msg)
                else:
                    # For non-safety errors, don't retry
                    raise

            except Exception as e:
                self.logger.error(f"Failed to generate summary: {e}")
                raise GeminiIntegrationError(f"Failed to generate summary: {e}")

        # If we get here, all retries failed
        if last_error:
            raise last_error
        else:
            raise GeminiIntegrationError("Failed to generate summary after all retries")

    def _sanitize_activity_data(
        self, activity_data: List[Dict[str, Any]], aggressive: bool = False
    ) -> List[Dict[str, Any]]:
        """Sanitize activity data for AI processing with enhanced safety compliance."""
        sanitized_data = []
        total_issues = []

        self.logger.info(
            f"Sanitizing {len(activity_data)} activities for AI safety compliance"
        )

        for i, activity in enumerate(activity_data):
            # First detect problematic content
            activity_text = json.dumps(activity, default=str)
            issues = self.sanitizer.detect_problematic_content(activity_text)

            if issues:
                total_issues.extend(issues)
                self.logger.debug(f"Activity {i} has potential issues: {issues}")

            # Sanitize the activity
            sanitized_activity = self.sanitizer.sanitize_jira_activity(
                activity, aggressive
            )

            # If still too problematic, create a minimal safe version
            if aggressive and issues:
                self.logger.debug(
                    f"Using minimal safe version for activity {activity.get('key', i)}"
                )
                sanitized_activity = self.sanitizer.create_summary_safe_activity(
                    activity
                )

            sanitized_data.append(sanitized_activity)

        if total_issues:
            self.logger.warning(
                f"Found {len(set(total_issues))} types of potentially problematic content "
                f"across {len(activity_data)} activities"
            )

        return sanitized_data

    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize dictionary recursively."""
        sanitized = {}

        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = InputValidator.sanitize_text(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = self._sanitize_list(value)
            else:
                sanitized[key] = value

        return sanitized

    def _sanitize_list(self, data: List[Any]) -> List[Any]:
        """Sanitize list recursively."""
        sanitized = []

        for item in data:
            if isinstance(item, str):
                sanitized.append(InputValidator.sanitize_text(item))
            elif isinstance(item, dict):
                sanitized.append(self._sanitize_dict(item))
            elif isinstance(item, list):
                sanitized.append(self._sanitize_list(item))
            else:
                sanitized.append(item)

        return sanitized

    def _prepare_prompt(
        self, activity_data: List[Dict[str, Any]], custom_prompt: Optional[str] = None
    ) -> str:
        """Prepare prompt for AI generation."""
        # Convert activity data to JSON string
        activity_json = json.dumps(activity_data, indent=2, default=str)

        # Use custom prompt or default
        if custom_prompt:
            prompt = custom_prompt.format(activity_data=activity_json)
        else:
            prompt = self.DEFAULT_EXECUTIVE_PROMPT.format(activity_data=activity_json)

        # Validate prompt length (Gemini has token limits)
        if len(prompt.split()) > 30000:  # Conservative limit
            # Truncate activity data if prompt is too long
            truncated_data = activity_data[:50]  # Limit to 50 activities
            activity_json = json.dumps(truncated_data, indent=2, default=str)

            if custom_prompt:
                prompt = custom_prompt.format(activity_data=activity_json)
            else:
                prompt = self.DEFAULT_EXECUTIVE_PROMPT.format(
                    activity_data=activity_json
                )

            self.logger.warning("Activity data truncated due to prompt length limits")

        return prompt

    async def _generate_content(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> Any:
        """Generate content using Gemini API."""
        try:
            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                candidate_count=1,
            )

            # Generate content
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.model.generate_content(
                    prompt, generation_config=generation_config
                ),
            )

            return response

        except Exception as e:
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                raise RateLimitError(f"Gemini rate limit exceeded: {e}")
            else:
                raise GeminiIntegrationError(f"Content generation failed: {e}")

    def _check_finish_reason(self, candidate: Any) -> None:
        """Check if response was blocked by safety filters."""
        if not hasattr(candidate, "finish_reason"):
            return

        # Finish reason 2 = SAFETY, 3 = RECITATION, 4 = OTHER
        finish_reason_errors = {
            2: (
                "Content was blocked by Gemini's safety filters. "
                "The input data may contain content that violates the model's usage policies. "
                "Try modifying the request or using different data."
            ),
            3: (
                "Content was blocked due to recitation concerns. "
                "The model detected potential copyright or citation issues."
            ),
            4: (
                "Content generation was blocked for other reasons. "
                "Please try again with different input."
            ),
        }

        if candidate.finish_reason in finish_reason_errors:
            raise GeminiIntegrationError(finish_reason_errors[candidate.finish_reason])

    def _extract_content(self, response: Any) -> str:
        """Extract text content from response."""
        content = ""
        try:
            content = response.text
        except Exception as text_error:
            # If we can't get text due to finish_reason error, we already handled it above
            # This catch is for other unexpected cases
            if "finish_reason" in str(text_error) and "is 2" in str(text_error):
                # This is a safety filter block that wasn't caught above
                raise GeminiIntegrationError(
                    "Content was blocked by Gemini's safety filters. "
                    "The input data may contain content that violates the model's usage policies."
                )
            # Otherwise, try to get content from candidates manually
            if hasattr(response, "candidates") and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, "content") and hasattr(
                        candidate.content, "parts"
                    ):
                        for part in candidate.content.parts:
                            if hasattr(part, "text"):
                                content += part.text

        return content

    def _extract_usage_metadata(self, response: Any) -> Dict[str, Any]:
        """Extract usage metadata from response."""
        if not hasattr(response, "usage_metadata"):
            return {}

        return {
            "prompt_token_count": getattr(
                response.usage_metadata, "prompt_token_count", 0
            ),
            "candidates_token_count": getattr(
                response.usage_metadata, "candidates_token_count", 0
            ),
            "total_token_count": getattr(
                response.usage_metadata, "total_token_count", 0
            ),
        }

    def _process_response(self, response: Any) -> Dict[str, Any]:
        """Process AI response into structured format."""
        try:
            # First check if response was blocked by safety filters BEFORE trying to access text
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                self._check_finish_reason(candidate)

            # Now try to extract text content
            content = self._extract_content(response)

            # Basic validation
            if not content:
                raise GeminiIntegrationError("Empty response from Gemini")

            # Parse response metadata
            usage_metadata = self._extract_usage_metadata(response)

            # Structure response
            summary = {
                "content": InputValidator.sanitize_text(content),
                "model": self.model_name,
                "usage": usage_metadata,
                "generated_at": time.time(),
                "safety_ratings": self._extract_safety_ratings(response),
            }

            return summary

        except GeminiIntegrationError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            self.logger.error(f"Failed to process response: {e}")
            raise GeminiIntegrationError(f"Failed to process response: {e}")

    def _extract_safety_ratings(self, response: Any) -> List[Dict[str, Any]]:
        """Extract safety ratings from response."""
        safety_ratings = []

        try:
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "safety_ratings"):
                    for rating in candidate.safety_ratings:
                        safety_ratings.append(
                            {
                                "category": rating.category.name,
                                "probability": rating.probability.name,
                            }
                        )
        except Exception as e:
            self.logger.error(f"Failed to extract safety ratings: {e}")

        return safety_ratings

    def _create_fallback_summary(
        self, activity_data: List[Dict[str, Any]], error_msg: str
    ) -> Dict[str, Any]:
        """Create a fallback summary when AI generation fails due to safety filters."""
        self.logger.info("Creating fallback summary due to safety filter issues")

        # Calculate basic statistics
        total_activities = len(activity_data)
        activities_by_type = {}
        activities_by_status = {}
        activities_by_assignee = {}

        for activity in activity_data:
            # Count by type
            activity_type = activity.get("type", "Unknown")
            activities_by_type[activity_type] = (
                activities_by_type.get(activity_type, 0) + 1
            )

            # Count by status
            status = activity.get("status", "Unknown")
            activities_by_status[status] = activities_by_status.get(status, 0) + 1

            # Count by assignee
            assignee = activity.get("assignee", "Unassigned")
            activities_by_assignee[assignee] = (
                activities_by_assignee.get(assignee, 0) + 1
            )

        # Create a basic statistical summary
        content = f"""# Executive Summary

## Summary Generation Notice

The AI-powered summary generation encountered content filtering issues.
This is a basic statistical summary of the Jira activities.

## Activity Overview

**Total Activities**: {total_activities}

### Activities by Type:
"""
        for activity_type, count in sorted(
            activities_by_type.items(), key=lambda x: x[1], reverse=True
        )[:10]:
            content += f"- {activity_type}: {count}\n"

        content += "\n### Activities by Status:\n"
        for status, count in sorted(
            activities_by_status.items(), key=lambda x: x[1], reverse=True
        ):
            content += f"- {status}: {count}\n"

        content += "\n### Top Contributors:\n"
        top_assignees = sorted(
            activities_by_assignee.items(), key=lambda x: x[1], reverse=True
        )[:10]
        for assignee, count in top_assignees:
            content += f"- {assignee}: {count} activities\n"

        content += """
## Recommendations

1. Review the Jira data for any content that might trigger AI safety filters
2. Consider removing or sanitizing descriptions with technical security terms
3. Check for any customer complaints or aggressive language in comments
4. Try generating summaries with smaller batches of activities

## Technical Note

The summary generation was blocked due to content safety filters. This typically occurs when:
- Technical security terms are misinterpreted as harmful content
- Bug descriptions contain aggressive or violent language
- Customer feedback includes inappropriate content
- Code snippets or logs contain patterns that trigger filters

For assistance, please contact your system administrator.
"""

        return {
            "content": content,
            "model": "fallback_generator",
            "usage": {"total_activities": total_activities},
            "generated_at": time.time(),
            "safety_ratings": [],
            "error": f"AI generation blocked: {error_msg}",
            "fallback": True,
        }

    async def generate_insights(
        self, activity_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate insights and recommendations from activity data."""
        insights_prompt = """
        As a business intelligence analyst, analyze the following Jira activity data and provide:

        1. Key performance metrics and trends
        2. Team productivity insights
        3. Potential risks and blockers
        4. Recommendations for improvement
        5. Strategic insights for leadership

        Format as a structured analysis with clear sections and actionable recommendations.

        Activity Data:
        {activity_data}

        Analysis:
        """

        return await self.generate_summary(activity_data, insights_prompt)

    async def generate_action_items(
        self, activity_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate action items from activity data."""
        action_items_prompt = """
        Based on the following Jira activity data, identify and prioritize action items for executive attention:

        1. Critical blockers requiring immediate attention
        2. Resource allocation issues
        3. Process improvements needed
        4. Team support requirements
        5. Strategic decisions needed

        Format as a prioritized action item list with owners and timelines where applicable.

        Activity Data:
        {activity_data}

        Action Items:
        """

        return await self.generate_summary(activity_data, action_items_prompt)

    async def validate_api_key(self) -> bool:
        """Validate API key with a simple request."""
        try:
            await self.rate_limiter.acquire()

            response = await self._generate_content("Test", 0.1, 10)

            # Try to access response.text safely
            try:
                if response.text:
                    return True
            except Exception as text_error:
                # Check if this is the expected error for filtered content
                if "response.text" in str(text_error) and "finish_reason" in str(
                    text_error
                ):
                    # This means the API is working but content was filtered
                    self.logger.info("API key validation successful (content filtered)")
                    return True

            # Check response structure for other validation patterns
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "finish_reason"):
                    # Finish reason 2 = SAFETY, 3 = RECITATION, etc.
                    if candidate.finish_reason in [2, 3]:
                        # This is actually a successful connection, just blocked content
                        self.logger.info(
                            "API key validation successful (content filtered)"
                        )
                        return True

            # If we have a response object but no text, connection is still valid
            if response:
                self.logger.info("API key validation successful (empty response)")
                return True

            return False

        except Exception as e:
            self.logger.error(f"API key validation failed: {e}")
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        try:
            models = genai.list_models()

            for model in models:
                if self.model_name in model.name:
                    return {
                        "name": model.name,
                        "display_name": model.display_name,
                        "description": model.description,
                        "input_token_limit": model.input_token_limit,
                        "output_token_limit": model.output_token_limit,
                        "supported_generation_methods": model.supported_generation_methods,
                        "temperature": model.temperature,
                        "top_p": model.top_p,
                        "top_k": model.top_k,
                    }

            return {"name": self.model_name, "status": "unknown"}

        except Exception as e:
            self.logger.error(f"Failed to get model info: {e}")
            return {"name": self.model_name, "error": str(e)}

    async def close(self) -> None:
        """Close client connections."""
        try:
            # Gemini client doesn't require explicit cleanup
            self.model = None
            self.logger.info("Gemini client closed")

        except Exception as e:
            self.logger.error(f"Error closing Gemini client: {e}")


class SummaryFormatter:
    """Format AI-generated summaries for different outputs."""

    @staticmethod
    def format_for_document(summary: Dict[str, Any]) -> str:
        """Format summary for document output."""
        content = summary.get("content", "")

        # Add header
        formatted = f"# Executive Summary\n\n"
        formatted += f"*Generated on {time.strftime('%Y-%m-%d %H:%M:%S')}*\n\n"

        # Add content
        formatted += content

        # Add footer
        formatted += f"\n\n---\n"
        formatted += (
            f"*Generated by Executive Summary Tool using "
            f"{summary.get('model', 'AI')}*\n"
        )

        return formatted

    @staticmethod
    def format_for_email(summary: Dict[str, Any]) -> str:
        """Format summary for email output."""
        content = summary.get("content", "")

        # Convert to plain text format
        formatted = content.replace("# ", "")
        formatted = formatted.replace("## ", "")
        formatted = formatted.replace("### ", "")
        formatted = formatted.replace("**", "")
        formatted = formatted.replace("*", "")

        return formatted

    @staticmethod
    def extract_key_points(summary: Dict[str, Any]) -> List[str]:
        """Extract key points from summary."""
        content = summary.get("content", "")

        # Simple extraction of bullet points
        lines = content.split("\n")
        key_points = []

        for line in lines:
            line = line.strip()
            if line.startswith("- ") or line.startswith("* "):
                key_points.append(line[2:])
            elif line.startswith("• "):
                key_points.append(line[2:])

        return key_points
