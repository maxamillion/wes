"""Enhanced content sanitization for AI safety compliance."""

import re
from typing import Any, Dict, List, Tuple

from ..utils.logging_config import get_logger


class ContentSanitizer:
    """Advanced content sanitizer to prevent AI safety filter triggers."""

    def __init__(self):
        self.logger = get_logger(__name__)

        # Technical terms that might be misinterpreted
        self.technical_replacements = {
            # Process/system terms
            r"\bkill\b": "terminate",
            r"\bkilled\b": "terminated",
            r"\bkilling\b": "terminating",
            r"\bdead\b": "inactive",
            r"\bdie\b": "stop",
            r"\bdied\b": "stopped",
            r"\bdying\b": "stopping",
            r"\bcrash\b": "failure",
            r"\bcrashed\b": "failed",
            r"\bcrashing\b": "failing",
            r"\bhang\b": "freeze",
            r"\bhanged\b": "frozen",
            r"\bhanging\b": "freezing",
            r"\babort\b": "cancel",
            r"\baborted\b": "cancelled",
            # Master/slave terminology
            r"\bmaster\b": "primary",
            r"\bslave\b": "secondary",
            r"\bblacklist\b": "blocklist",
            r"\bwhitelist\b": "allowlist",
            # Aggressive technical terms
            r"\battack\b": "access attempt",
            r"\battacked\b": "accessed",
            r"\battacker\b": "unauthorized user",
            r"\bexploit\b": "vulnerability",
            r"\bexploited\b": "compromised",
            r"\bexploiting\b": "utilizing vulnerability",
            r"\binject\b": "insert",
            r"\binjection\b": "insertion",
            r"\binjected\b": "inserted",
            # Other potentially problematic terms
            r"\bfatal\b": "critical",
            r"\blethal\b": "critical",
            r"\bdeadly\b": "severe",
            r"\bpoison\b": "corrupt",
            r"\bpoisoned\b": "corrupted",
            r"\bbomb\b": "error",
            r"\bnuke\b": "remove",
            r"\bnuked\b": "removed",
            r"\bwar\b": "conflict",
            r"\bfight\b": "resolve",
            r"\bfighting\b": "resolving",
        }

        # Profanity and offensive language patterns
        self.profanity_patterns = [
            r"\bf+[*u]+c+k+",
            r"\bs+h+[*i]+t+",
            r"\ba+s+s+h+o+l+e+",
            r"\bb+[*i]+t+c+h+",
            r"\bd+a+m+n+",
            r"\bh+e+l+l+",
            r"\bc+r+a+p+",
            r"\bp+[*i]+s+s+",
        ]

        # Aggressive complaint patterns
        self.complaint_patterns = [
            r"this is (?:completely |totally |absolutely )?(?:stupid|idiotic|moronic|dumb)",
            r"(?:what|who) the (?:hell|heck|f\*\*\*)",
            r"this (?:sucks|blows)",
            r"(?:terrible|horrible|awful|pathetic|useless|worthless|garbage|trash)",
            r"(?:hate|despise|loathe) this",
            r"(?:incompetent|incompetence)",
            r"(?:ridiculous|absurd|insane|crazy)",
        ]

        # Security-related patterns that might trigger filters
        self.security_patterns = {
            r'(?:password|passwd|pwd)[\s]*[:=][\s]*["\']?[\w\s]+["\']?': "[CREDENTIALS_REMOVED]",
            r'(?:api[_-]?key|apikey)[\s]*[:=][\s]*["\']?[\w\s]+["\']?': "[API_KEY_REMOVED]",
            r'(?:token|secret)[\s]*[:=][\s]*["\']?[\w\s]+["\']?': "[SECRET_REMOVED]",
            r"(?:CVE-\d{4}-\d+)": "[CVE_REFERENCE]",
            r"(?:exploit|vulnerability|0day|zero-day)": "security issue",
        }

        # Violence-related terms in error messages
        self.violence_terms = {
            r"\bdestroy\b": "remove",
            r"\bdestroyed\b": "removed",
            r"\bdestroying\b": "removing",
            r"\bannihilate\b": "remove completely",
            r"\bobliterate\b": "delete",
            r"\bexecute\b": "run",
            r"\bexecuted\b": "ran",
            r"\bexecution\b": "operation",
            r"\bterminate\b": "end",
            r"\bterminated\b": "ended",
            r"\btermination\b": "ending",
        }

    def sanitize_text(
        self, text: str, aggressive: bool = False
    ) -> Tuple[str, List[str]]:
        """
        Sanitize text to prevent AI safety filter triggers.

        Args:
            text: The text to sanitize
            aggressive: Use more aggressive sanitization

        Returns:
            Tuple of (sanitized_text, list_of_changes_made)
        """
        if not text:
            return text, []

        original_text = text
        changes_made = []

        # Apply technical term replacements
        for pattern, replacement in self.technical_replacements.items():
            if re.search(pattern, text, re.IGNORECASE):
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
                changes_made.append(f"Replaced technical term: {pattern}")

        # Remove profanity
        for pattern in self.profanity_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                text = re.sub(pattern, "[removed]", text, flags=re.IGNORECASE)
                changes_made.append("Removed profanity")

        # Soften aggressive complaints
        for pattern in self.complaint_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                text = re.sub(pattern, "[feedback removed]", text, flags=re.IGNORECASE)
                changes_made.append("Removed aggressive complaint")

        # Handle security patterns
        for pattern, replacement in self.security_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
                changes_made.append("Sanitized security content")

        # Apply violence-related replacements if aggressive mode
        if aggressive:
            for pattern, replacement in self.violence_terms.items():
                if re.search(pattern, text, re.IGNORECASE):
                    text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
                    changes_made.append(f"Replaced violence-related term: {pattern}")

        # Remove excessive caps (often used in angry comments)
        if len(re.findall(r"[A-Z]", text)) / max(len(text), 1) > 0.5:
            text = text.lower()
            changes_made.append("Converted excessive caps to lowercase")

        # Remove multiple exclamation marks (anger indicator)
        if "!!!" in text:
            text = re.sub(r"!{3,}", "!", text)
            changes_made.append("Reduced excessive exclamation marks")

        # Log significant changes
        if changes_made and original_text != text:
            self.logger.debug(
                f"Sanitized text - changes: {', '.join(set(changes_made))}"
            )

        return text, changes_made

    def sanitize_jira_activity(
        self, activity: Dict[str, Any], aggressive: bool = False
    ) -> Dict[str, Any]:
        """
        Sanitize a complete Jira activity record.

        Args:
            activity: The activity dictionary to sanitize
            aggressive: Use more aggressive sanitization

        Returns:
            Sanitized activity dictionary
        """
        sanitized = activity.copy()
        total_changes = []

        # Fields that commonly contain problematic content
        text_fields = [
            "summary",
            "description",
            "comment",
            "body",
            "title",
            "details",
            "message",
            "text",
            "resolution",
            "environment",
            "steps_to_reproduce",
        ]

        def sanitize_nested(obj: Any, path: str = "") -> Any:
            """Recursively sanitize nested structures."""
            if isinstance(obj, str):
                cleaned, changes = self.sanitize_text(obj, aggressive)
                if changes:
                    total_changes.extend([f"{path}: {change}" for change in changes])
                return cleaned
            elif isinstance(obj, dict):
                return {k: sanitize_nested(v, f"{path}.{k}") for k, v in obj.items()}
            elif isinstance(obj, list):
                return [
                    sanitize_nested(item, f"{path}[{i}]") for i, item in enumerate(obj)
                ]
            else:
                return obj

        # Sanitize all text fields
        for field in text_fields:
            if field in sanitized:
                sanitized[field], changes = self.sanitize_text(
                    str(sanitized[field]), aggressive
                )
                if changes:
                    total_changes.extend([f"{field}: {change}" for change in changes])

        # Handle nested structures like comments
        if "comments" in sanitized and isinstance(sanitized["comments"], list):
            sanitized["comments"] = sanitize_nested(sanitized["comments"], "comments")

        # Handle custom fields
        if "customfield" in str(sanitized):
            for key, value in sanitized.items():
                if key.startswith("customfield") and isinstance(value, str):
                    sanitized[key], changes = self.sanitize_text(value, aggressive)
                    if changes:
                        total_changes.extend([f"{key}: {change}" for change in changes])

        # Log if significant sanitization occurred
        if total_changes:
            self.logger.debug(
                f"Sanitized Jira activity {activity.get('key', 'unknown')}: "
                f"{len(total_changes)} changes made"
            )

        return sanitized

    def detect_problematic_content(self, text: str) -> List[str]:
        """
        Detect potentially problematic content without modifying it.

        Args:
            text: Text to analyze

        Returns:
            List of detected issues
        """
        issues = []

        # Check for technical terms
        for pattern in self.technical_replacements:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Technical term that might be misinterpreted: {pattern}")

        # Check for profanity
        for pattern in self.profanity_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append("Contains profanity")
                break

        # Check for aggressive language
        for pattern in self.complaint_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append("Contains aggressive complaint language")
                break

        # Check for security content
        for pattern in self.security_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append("Contains security-related content")
                break

        # Check for excessive caps
        if len(text) > 10 and len(re.findall(r"[A-Z]", text)) / len(text) > 0.5:
            issues.append("Excessive capitalization (shouting)")

        return issues

    def create_summary_safe_activity(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a summary-safe version of an activity by keeping only essential fields.

        Args:
            activity: Original activity

        Returns:
            Minimal activity dict safe for summarization
        """
        safe_activity = {
            "key": activity.get("key", "UNKNOWN"),
            "type": activity.get("type", "unknown"),
            "status": activity.get("status", "unknown"),
            "priority": activity.get("priority", "unknown"),
            "created": activity.get("created", ""),
            "updated": activity.get("updated", ""),
            "assignee": activity.get("assignee", "unassigned"),
            "reporter": activity.get("reporter", "unknown"),
        }

        # Add sanitized summary if available
        if "summary" in activity:
            safe_summary, _ = self.sanitize_text(activity["summary"], aggressive=True)
            safe_activity["summary"] = safe_summary[:100]  # Limit length

        return safe_activity
