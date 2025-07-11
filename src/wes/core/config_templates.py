"""Smart defaults and configuration templates for simplified setup."""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path

from ..utils.logging_config import get_logger


class ConfigTemplate:
    """Base class for configuration templates."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def generate_config(self, user_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate configuration from user inputs."""
        raise NotImplementedError

    def get_required_inputs(self) -> List[Dict[str, str]]:
        """Get list of required user inputs."""
        raise NotImplementedError


class JiraConfigTemplate(ConfigTemplate):
    """Template for Jira configuration."""

    def __init__(self):
        super().__init__(
            "Jira Configuration", "Standard Jira setup for team activity tracking"
        )

    def generate_config(self, user_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Jira configuration."""
        company_name = user_inputs.get("company_name", "")
        team_size = user_inputs.get("team_size", "small")
        use_case = user_inputs.get("use_case", "executive_summary")

        # Smart defaults based on inputs
        rate_limits = {
            "small": 50,  # 1-10 people
            "medium": 100,  # 11-50 people
            "large": 200,  # 50+ people
        }

        timeouts = {
            "executive_summary": 30,
            "detailed_analysis": 60,
            "bulk_export": 120,
        }

        # Common JQL queries based on use case
        default_queries = {
            "executive_summary": "project = {project} AND updated >= -1w ORDER BY updated DESC",
            "weekly_review": "project = {project} AND updated >= -7d AND status changed ORDER BY updated DESC",
            "sprint_summary": "project = {project} AND sprint in openSprints() ORDER BY rank",
            "team_performance": "assignee in ({users}) AND updated >= -2w ORDER BY assignee, updated DESC",
        }

        config = {
            "default_project": self._suggest_project_key(company_name),
            "default_query": default_queries.get(
                use_case, default_queries["executive_summary"]
            ),
            "rate_limit": rate_limits.get(team_size, 100),
            "timeout": timeouts.get(use_case, 30),
            "default_users": [],  # Will be populated after connection
            "pagination_size": min(100, rate_limits.get(team_size, 100)),
        }

        return config

    def get_required_inputs(self) -> List[Dict[str, str]]:
        """Get required inputs for Jira template."""
        return [
            {
                "key": "company_name",
                "label": "Company Name",
                "type": "text",
                "description": "Used to suggest project keys and naming conventions",
            },
            {
                "key": "team_size",
                "label": "Team Size",
                "type": "select",
                "options": ["small", "medium", "large"],
                "description": "Helps optimize rate limits and performance settings",
            },
            {
                "key": "use_case",
                "label": "Primary Use Case",
                "type": "select",
                "options": [
                    "executive_summary",
                    "weekly_review",
                    "sprint_summary",
                    "team_performance",
                ],
                "description": "Determines default query templates and settings",
            },
        ]

    def _suggest_project_key(self, company_name: str) -> str:
        """Suggest project key based on company name."""
        if not company_name:
            return "PROJ"

        # Extract meaningful words and create acronym
        words = company_name.upper().split()
        if len(words) == 1:
            return words[0][:4]
        elif len(words) == 2:
            return words[0][:2] + words[1][:2]
        else:
            return "".join(word[0] for word in words[:4])


class GoogleConfigTemplate(ConfigTemplate):
    """Template for Google services configuration."""

    def __init__(self):
        super().__init__(
            "Google Services Configuration",
            "Google Drive and Docs setup for document management",
        )

    def generate_config(self, user_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Google configuration."""
        document_frequency = user_inputs.get("document_frequency", "weekly")
        sharing_scope = user_inputs.get("sharing_scope", "team")
        storage_preference = user_inputs.get("storage_preference", "organized")

        # Rate limits based on usage frequency
        rate_limits = {"daily": 200, "weekly": 100, "monthly": 50, "ad_hoc": 25}

        # Document organization suggestions
        folder_structures = {
            "organized": "Executive Summaries/{year}/{month}",
            "simple": "Executive Summaries",
            "project_based": "Projects/{project}/Summaries",
        }

        config = {
            "rate_limit": rate_limits.get(document_frequency, 100),
            "timeout": 60,
            "default_folder_structure": folder_structures.get(
                storage_preference, "Executive Summaries"
            ),
            "auto_share": sharing_scope != "private",
            "document_template": "executive_summary_standard",
        }

        return config

    def get_required_inputs(self) -> List[Dict[str, str]]:
        """Get required inputs for Google template."""
        return [
            {
                "key": "document_frequency",
                "label": "How often will you create documents?",
                "type": "select",
                "options": ["daily", "weekly", "monthly", "ad_hoc"],
                "description": "Helps set appropriate rate limits",
            },
            {
                "key": "sharing_scope",
                "label": "Document Sharing",
                "type": "select",
                "options": ["private", "team", "organization"],
                "description": "Default sharing permissions for created documents",
            },
            {
                "key": "storage_preference",
                "label": "Organization Style",
                "type": "select",
                "options": ["organized", "simple", "project_based"],
                "description": "How to organize documents in Google Drive",
            },
        ]


class AIConfigTemplate(ConfigTemplate):
    """Template for AI/Gemini configuration."""

    def __init__(self):
        super().__init__(
            "AI Configuration", "Google Gemini setup for intelligent summary generation"
        )

    def generate_config(self, user_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI configuration."""
        summary_style = user_inputs.get("summary_style", "executive")
        detail_level = user_inputs.get("detail_level", "medium")
        audience = user_inputs.get("audience", "executives")

        # Model selection based on requirements
        models = {
            "basic": "gemini-2.5-flash",
            "advanced": "gemini-2.5-pro",
            "vision": "gemini-2.5-pro",  # 2.5 models support vision natively
        }

        # Temperature settings for different styles
        temperatures = {
            "executive": 0.3,  # More factual, less creative
            "technical": 0.2,  # Very factual
            "narrative": 0.7,  # More creative storytelling
            "analytical": 0.4,  # Balanced
        }

        # Token limits based on detail level
        token_limits = {
            "brief": 1024,
            "medium": 2048,
            "detailed": 4096,
            "comprehensive": 8192,
        }

        # Custom prompts for different audiences
        audience_prompts = {
            "executives": "You are an executive assistant creating a summary for C-level executives. Focus on high-level insights, risks, and strategic implications.",
            "managers": "You are creating a summary for middle management. Include operational details and team performance metrics.",
            "technical": "You are creating a technical summary. Include specific implementation details and technical challenges.",
            "stakeholders": "You are creating a summary for project stakeholders. Focus on progress, milestones, and impact.",
        }

        config = {
            "model_name": models.get("basic", "gemini-2.5-flash"),
            "temperature": temperatures.get(summary_style, 0.3),
            "max_tokens": token_limits.get(detail_level, 2048),
            "rate_limit": 60,  # Standard rate limit
            "timeout": 120,  # Allow time for longer generation
            "custom_prompt": audience_prompts.get(
                audience, audience_prompts["executives"]
            ),
            "safety_settings": "medium",  # Balance safety with usefulness
            "retry_attempts": 3,
        }

        return config

    def get_required_inputs(self) -> List[Dict[str, str]]:
        """Get required inputs for AI template."""
        return [
            {
                "key": "summary_style",
                "label": "Summary Style",
                "type": "select",
                "options": ["executive", "technical", "narrative", "analytical"],
                "description": "Writing style for generated summaries",
            },
            {
                "key": "detail_level",
                "label": "Detail Level",
                "type": "select",
                "options": ["brief", "medium", "detailed", "comprehensive"],
                "description": "How much detail to include in summaries",
            },
            {
                "key": "audience",
                "label": "Primary Audience",
                "type": "select",
                "options": ["executives", "managers", "technical", "stakeholders"],
                "description": "Who will primarily read these summaries?",
            },
        ]


class SecurityConfigTemplate(ConfigTemplate):
    """Template for security configuration."""

    def __init__(self):
        super().__init__("Security Configuration", "Security and compliance settings")

    def generate_config(self, user_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate security configuration."""
        compliance_level = user_inputs.get("compliance_level", "standard")
        data_sensitivity = user_inputs.get("data_sensitivity", "medium")
        audit_requirements = user_inputs.get("audit_requirements", False)

        # Security settings based on compliance level
        compliance_settings = {
            "basic": {
                "encryption_enabled": True,
                "key_rotation_days": 180,
                "session_timeout_minutes": 120,
                "max_login_attempts": 5,
                "audit_logging": False,
            },
            "standard": {
                "encryption_enabled": True,
                "key_rotation_days": 90,
                "session_timeout_minutes": 60,
                "max_login_attempts": 3,
                "audit_logging": True,
            },
            "strict": {
                "encryption_enabled": True,
                "key_rotation_days": 30,
                "session_timeout_minutes": 30,
                "max_login_attempts": 3,
                "audit_logging": True,
            },
        }

        config = compliance_settings.get(
            compliance_level, compliance_settings["standard"]
        )

        # Adjust based on data sensitivity
        if data_sensitivity == "high":
            config["key_rotation_days"] = min(config["key_rotation_days"], 60)
            config["session_timeout_minutes"] = min(
                config["session_timeout_minutes"], 45
            )
            config["audit_logging"] = True

        # Force audit logging if required
        if audit_requirements:
            config["audit_logging"] = True

        return config

    def get_required_inputs(self) -> List[Dict[str, str]]:
        """Get required inputs for security template."""
        return [
            {
                "key": "compliance_level",
                "label": "Compliance Level",
                "type": "select",
                "options": ["basic", "standard", "strict"],
                "description": "Level of security controls required",
            },
            {
                "key": "data_sensitivity",
                "label": "Data Sensitivity",
                "type": "select",
                "options": ["low", "medium", "high"],
                "description": "Sensitivity level of data being processed",
            },
            {
                "key": "audit_requirements",
                "label": "Audit Logging Required",
                "type": "boolean",
                "description": "Whether detailed audit logging is required",
            },
        ]


class TemplateManager:
    """Manage configuration templates and smart defaults."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.templates = {
            "jira": JiraConfigTemplate(),
            "google": GoogleConfigTemplate(),
            "ai": AIConfigTemplate(),
            "security": SecurityConfigTemplate(),
        }

    def get_template(self, service: str) -> Optional[ConfigTemplate]:
        """Get template for a service."""
        return self.templates.get(service)

    def get_all_templates(self) -> Dict[str, ConfigTemplate]:
        """Get all available templates."""
        return self.templates.copy()

    def generate_full_config(
        self, user_inputs: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate full configuration from user inputs."""
        full_config = {}

        for service, inputs in user_inputs.items():
            template = self.get_template(service)
            if template:
                try:
                    service_config = template.generate_config(inputs)
                    full_config[service] = service_config
                except Exception as e:
                    self.logger.error(f"Failed to generate config for {service}: {e}")
                    # Use empty config as fallback
                    full_config[service] = {}

        return full_config

    def suggest_defaults_for_organization(
        self, org_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest defaults based on organization information."""
        org_size = org_info.get("size", "medium")  # small, medium, large
        industry = org_info.get("industry", "technology")
        security_requirements = org_info.get("security_requirements", "standard")

        suggestions = {}

        # Industry-specific defaults
        industry_defaults = {
            "finance": {
                "security_level": "strict",
                "audit_required": True,
                "data_retention": 2555,  # 7 years in days
            },
            "healthcare": {
                "security_level": "strict",
                "audit_required": True,
                "encryption_required": True,
            },
            "technology": {
                "security_level": "standard",
                "audit_required": False,
                "agile_focused": True,
            },
            "government": {
                "security_level": "strict",
                "audit_required": True,
                "compliance_framework": "FISMA",
            },
        }

        # Size-based defaults
        size_defaults = {
            "small": {
                "rate_limits": {"jira": 50, "google": 50, "ai": 30},
                "complexity": "simple",
            },
            "medium": {
                "rate_limits": {"jira": 100, "google": 100, "ai": 60},
                "complexity": "standard",
            },
            "large": {
                "rate_limits": {"jira": 200, "google": 200, "ai": 120},
                "complexity": "advanced",
            },
        }

        # Merge defaults
        if industry in industry_defaults:
            suggestions.update(industry_defaults[industry])

        if org_size in size_defaults:
            suggestions.update(size_defaults[org_size])

        return suggestions

    def export_template(self, service: str, file_path: Path) -> bool:
        """Export template configuration to file."""
        try:
            template = self.get_template(service)
            if not template:
                return False

            template_data = {
                "name": template.name,
                "description": template.description,
                "required_inputs": template.get_required_inputs(),
                "created_at": datetime.now().isoformat(),
            }

            with open(file_path, "w") as f:
                json.dump(template_data, f, indent=2)

            return True

        except Exception as e:
            self.logger.error(f"Failed to export template: {e}")
            return False

    def import_custom_template(self, file_path: Path) -> Optional[str]:
        """Import custom template from file."""
        try:
            with open(file_path, "r") as f:
                template_data = json.load(f)

            # Validate template structure
            required_fields = ["name", "description", "required_inputs"]
            if not all(field in template_data for field in required_fields):
                raise ValueError("Invalid template format")

            # Create custom template (would need to implement CustomTemplate class)
            # For now, just return the template name
            return template_data["name"]

        except Exception as e:
            self.logger.error(f"Failed to import template: {e}")
            return None


class SmartDefaults:
    """Provide smart defaults based on context and usage patterns."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def get_jira_query_suggestions(self, project_key: str, use_case: str) -> List[str]:
        """Get JQL query suggestions."""
        base_queries = {
            "executive_summary": [
                f"project = {project_key} AND updated >= -1w ORDER BY updated DESC",
                f"project = {project_key} AND status changed DURING (-1w, now()) ORDER BY updated DESC",
                f"project = {project_key} AND priority in (Highest, High) AND status != Done",
            ],
            "sprint_review": [
                f"project = {project_key} AND sprint in openSprints()",
                f"project = {project_key} AND sprint in closedSprints() AND sprint not in futureSprints() ORDER BY created DESC",
                f"project = {project_key} AND fixVersion in unreleasedVersions()",
            ],
            "team_performance": [
                f"project = {project_key} AND assignee in (currentUser())",
                f"project = {project_key} AND reporter = currentUser() AND created >= -2w",
                f"project = {project_key} AND component is not EMPTY ORDER BY component",
            ],
        }

        return base_queries.get(use_case, base_queries["executive_summary"])

    def get_rate_limit_recommendations(self, service: str, usage_pattern: str) -> int:
        """Get rate limit recommendations."""
        recommendations = {
            "jira": {
                "light": 25,  # Few users, occasional use
                "moderate": 100,  # Regular team usage
                "heavy": 200,  # Large team, frequent use
                "enterprise": 500,  # Very large organization
            },
            "google": {"light": 50, "moderate": 100, "heavy": 200, "enterprise": 500},
            "gemini": {"light": 30, "moderate": 60, "heavy": 120, "enterprise": 300},
        }

        return recommendations.get(service, {}).get(usage_pattern, 100)

    def suggest_optimal_timeouts(self, service: str, data_volume: str) -> int:
        """Suggest optimal timeout values."""
        timeout_matrix = {
            "jira": {
                "small": 15,  # < 100 issues
                "medium": 30,  # 100-1000 issues
                "large": 60,  # 1000-10000 issues
                "huge": 120,  # > 10000 issues
            },
            "google": {"small": 30, "medium": 60, "large": 120, "huge": 300},
            "gemini": {
                "small": 60,  # Short content
                "medium": 120,  # Medium content
                "large": 300,  # Long content
                "huge": 600,  # Very long content
            },
        }

        return timeout_matrix.get(service, {}).get(data_volume, 60)
