"""Google Gemini AI client for generating executive summaries."""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory

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
    - Progress on important initiatives
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
        model_name: str = "gemini-2.5-flash",
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

            # Initialize model
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                },
            )

            # Test connection
            self._test_connection()

            self.security_logger.log_authentication_attempt(
                service="gemini", success=True
            )

            self.logger.info("Gemini client initialized successfully")

        except Exception as e:
            self.security_logger.log_authentication_attempt(
                service="gemini", success=False, error=str(e)
            )
            raise AuthenticationError(f"Gemini authentication failed: {e}")

    def _test_connection(self) -> None:
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
        """Generate executive summary from Jira activity data."""
        try:
            # Rate limiting
            await self.rate_limiter.acquire()

            # Validate and sanitize input data
            sanitized_data = self._sanitize_activity_data(activity_data)

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

        except Exception as e:
            self.logger.error(f"Failed to generate summary: {e}")
            raise GeminiIntegrationError(f"Failed to generate summary: {e}")

    def _sanitize_activity_data(
        self, activity_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Sanitize activity data for AI processing."""
        sanitized_data = []

        for activity in activity_data:
            sanitized_activity = {}

            # Sanitize text fields
            for key, value in activity.items():
                if isinstance(value, str):
                    sanitized_activity[key] = InputValidator.sanitize_text(value)
                elif isinstance(value, dict):
                    sanitized_activity[key] = self._sanitize_dict(value)
                elif isinstance(value, list):
                    sanitized_activity[key] = self._sanitize_list(value)
                else:
                    sanitized_activity[key] = value

            sanitized_data.append(sanitized_activity)

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

    def _process_response(self, response: Any) -> Dict[str, Any]:
        """Process AI response into structured format."""
        try:
            # First check if response was blocked by safety filters BEFORE trying to access text
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "finish_reason"):
                    # Finish reason 2 = SAFETY, 3 = RECITATION, 4 = OTHER
                    if candidate.finish_reason == 2:
                        raise GeminiIntegrationError(
                            "Content was blocked by Gemini's safety filters. "
                            "The input data may contain content that violates the model's usage policies. "
                            "Try modifying the request or using different data."
                        )
                    elif candidate.finish_reason == 3:
                        raise GeminiIntegrationError(
                            "Content was blocked due to recitation concerns. "
                            "The model detected potential copyright or citation issues."
                        )
                    elif candidate.finish_reason == 4:
                        raise GeminiIntegrationError(
                            "Content generation was blocked for other reasons. "
                            "Please try again with different input."
                        )

            # Now try to extract text content
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

            # Basic validation
            if not content:
                raise GeminiIntegrationError("Empty response from Gemini")

            # Parse response metadata
            usage_metadata = {}
            if hasattr(response, "usage_metadata"):
                usage_metadata = {
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
