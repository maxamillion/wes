"""Red Hat LDAP integration client for organizational hierarchy queries."""

import asyncio
import os
import ssl
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import ldap3
from ldap3 import ALL, Connection, Server, Tls
from ldap3.core.exceptions import LDAPBindError

from ..utils.exceptions import AuthenticationError, WesError
from ..utils.logging_config import get_logger, get_security_logger
from ..utils.validators import InputValidator


class LDAPIntegrationError(WesError):
    """Raised when LDAP integration fails."""


@dataclass
class LDAPUser:
    """Represents an LDAP user with relevant attributes."""

    uid: str
    email: str
    display_name: str
    manager_dn: Optional[str] = None
    direct_reports: List[str] = None
    title: Optional[str] = None
    department: Optional[str] = None

    def __post_init__(self):
        if self.direct_reports is None:
            self.direct_reports = []


class RedHatLDAPClient:
    """Client for querying Red Hat's LDAP server for organizational data."""

    # Red Hat LDAP configuration
    LDAP_SERVER = "ldaps://ldap.corp.redhat.com"
    LDAP_PORT = 636
    LDAP_BASE_DN = "ou=users,dc=redhat,dc=com"
    LDAP_TIMEOUT = 30

    # LDAP attributes to retrieve
    USER_ATTRIBUTES = [
        "uid",
        "mail",
        "displayName",
        "cn",
        "manager",
        "title",
        "departmentNumber",
        "rhatCostCenter",
    ]

    def __init__(
        self,
        server_url: Optional[str] = None,
        base_dn: Optional[str] = None,
        timeout: int = 30,
        use_ssl: bool = True,
        validate_certs: bool = True,
    ):
        """Initialize Red Hat LDAP client.

        Args:
            server_url: LDAP server URL (defaults to Red Hat LDAP)
            base_dn: Base DN for searches (defaults to Red Hat users)
            timeout: Connection timeout in seconds
            use_ssl: Whether to use SSL/TLS
            validate_certs: Whether to validate SSL certificates
        """
        self.logger = get_logger(__name__)
        self.security_logger = get_security_logger()

        self.server_url = server_url or self.LDAP_SERVER
        self.base_dn = base_dn or self.LDAP_BASE_DN
        self.timeout = timeout or self.LDAP_TIMEOUT
        self.use_ssl = use_ssl

        # Allow environment variable override for certificate validation
        # This is a temporary workaround for SSL certificate issues
        if os.environ.get("WES_LDAP_SKIP_CERT_VERIFY", "").lower() in (
            "true",
            "1",
            "yes",
        ):
            self.logger.warning(
                "SSL certificate verification disabled via environment variable"
            )
            self.validate_certs = False
        else:
            self.validate_certs = validate_certs

        self._connection: Optional[Connection] = None
        self._server: Optional[Server] = None

    def _create_tls_configuration(self) -> Tls:
        """Create TLS configuration for secure LDAP connection."""
        if self.validate_certs:
            return Tls(validate=ssl.CERT_REQUIRED, version=ssl.PROTOCOL_TLS)
        else:
            # Create a custom SSL context that doesn't verify certificates
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return Tls(
                validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLS, ssl_context=ctx
            )

    def _initialize_connection(self) -> None:
        """Initialize LDAP connection to Red Hat server."""
        try:
            # Create TLS configuration
            tls_config = self._create_tls_configuration() if self.use_ssl else None

            # Create server object
            # For ldaps:// URLs, ldap3 will use SSL even without use_ssl=True
            # The tls parameter is used for STARTTLS or to configure SSL behavior
            self._server = Server(
                self.server_url,
                use_ssl=self.use_ssl,
                tls=tls_config,
                get_info=ALL,
                connect_timeout=self.timeout,
            )

            # Create connection (anonymous bind for Red Hat LDAP)
            self._connection = Connection(
                self._server,
                auto_bind=True,
                client_strategy=ldap3.RESTARTABLE,
                raise_exceptions=True,
            )

            self.logger.info(
                f"Connected to LDAP server: {self.server_url} (validate_certs={self.validate_certs})"
            )
            self.security_logger.log_authentication_attempt(
                service="redhat_ldap",
                username="anonymous",
                success=True,
                details="Anonymous bind to Red Hat LDAP",
            )

        except LDAPBindError as e:
            self.security_logger.log_authentication_attempt(
                service="redhat_ldap",
                username="anonymous",
                success=False,
                error=str(e),
            )
            raise AuthenticationError(f"LDAP bind failed: {e}")
        except Exception as e:
            self.logger.error(f"Failed to initialize LDAP connection: {e}")
            raise LDAPIntegrationError(f"LDAP connection failed: {e}")

    async def connect(self) -> None:
        """Establish connection to LDAP server."""
        if not self._connection or not self._connection.bound:
            await asyncio.get_event_loop().run_in_executor(
                None, self._initialize_connection
            )

    async def disconnect(self) -> None:
        """Close LDAP connection."""
        if self._connection and self._connection.bound:
            try:
                self._connection.unbind()
                self.logger.info("Disconnected from LDAP server")
            except Exception as e:
                self.logger.error(f"Error disconnecting from LDAP: {e}")

    def _parse_user_entry(self, entry: Any) -> LDAPUser:
        """Parse LDAP entry into LDAPUser object."""
        attributes = entry.entry_attributes_as_dict

        # Extract attributes with safe defaults
        uid = attributes.get("uid", [None])[0]
        mail = attributes.get("mail", [None])[0]
        display_name = attributes.get("displayName", [None])[0]
        cn = attributes.get("cn", [None])[0]
        manager = attributes.get("manager", [None])[0]
        title = attributes.get("title", [None])[0]
        department = attributes.get("departmentNumber", [None])[0]

        # Use display name or cn as fallback
        name = display_name or cn or uid

        return LDAPUser(
            uid=uid,
            email=mail,
            display_name=name,
            manager_dn=manager,
            title=title,
            department=department,
        )

    async def search_user_by_email(self, email: str) -> Optional[LDAPUser]:
        """Search for a user by email address.

        Args:
            email: Email address to search for

        Returns:
            LDAPUser object if found, None otherwise
        """
        try:
            # Validate email
            InputValidator.validate_email(email)

            # Ensure connection
            await self.connect()

            # Build search filter
            search_filter = f"(mail={email})"

            # Execute search
            search_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._connection.search(
                    search_base=self.base_dn,
                    search_filter=search_filter,
                    attributes=self.USER_ATTRIBUTES,
                    size_limit=1,
                ),
            )

            if not search_result or not self._connection.entries:
                self.logger.warning(f"No user found with email: {email}")
                return None

            # Parse first result
            entry = self._connection.entries[0]
            user = self._parse_user_entry(entry)

            self.logger.info(f"Found user: {user.uid} ({user.email})")
            return user

        except Exception as e:
            self.logger.error(f"Failed to search user by email {email}: {e}")
            raise LDAPIntegrationError(f"User search failed: {e}")

    async def search_user_by_uid(self, uid: str) -> Optional[LDAPUser]:
        """Search for a user by UID (username).

        Args:
            uid: Username to search for

        Returns:
            LDAPUser object if found, None otherwise
        """
        try:
            # Validate username
            InputValidator.validate_user_identifier(uid)

            # Ensure connection
            await self.connect()

            # Build search filter
            search_filter = f"(uid={uid})"

            # Execute search
            search_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._connection.search(
                    search_base=self.base_dn,
                    search_filter=search_filter,
                    attributes=self.USER_ATTRIBUTES,
                    size_limit=1,
                ),
            )

            if not search_result or not self._connection.entries:
                self.logger.warning(f"No user found with uid: {uid}")
                return None

            # Parse first result
            entry = self._connection.entries[0]
            user = self._parse_user_entry(entry)

            self.logger.info(f"Found user: {user.uid} ({user.email})")
            return user

        except Exception as e:
            self.logger.error(f"Failed to search user by uid {uid}: {e}")
            raise LDAPIntegrationError(f"User search failed: {e}")

    async def get_direct_reports(self, manager_dn: str) -> List[LDAPUser]:
        """Get direct reports for a manager.

        Args:
            manager_dn: Distinguished name of the manager

        Returns:
            List of LDAPUser objects for direct reports
        """
        try:
            # Ensure connection
            await self.connect()

            # Build search filter for direct reports
            search_filter = f"(manager={manager_dn})"

            # Execute search
            search_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._connection.search(
                    search_base=self.base_dn,
                    search_filter=search_filter,
                    attributes=self.USER_ATTRIBUTES,
                    size_limit=1000,  # Reasonable limit for direct reports
                ),
            )

            if not search_result:
                return []

            # Parse results
            direct_reports = []
            for entry in self._connection.entries:
                user = self._parse_user_entry(entry)
                direct_reports.append(user)

            self.logger.info(
                f"Found {len(direct_reports)} direct reports for {manager_dn}"
            )
            return direct_reports

        except Exception as e:
            self.logger.error(f"Failed to get direct reports for {manager_dn}: {e}")
            raise LDAPIntegrationError(f"Direct reports query failed: {e}")

    async def get_organizational_hierarchy(
        self, manager_email: str, max_depth: int = 3
    ) -> Dict[str, Any]:
        """Get complete organizational hierarchy for a manager.

        Args:
            manager_email: Email address of the manager
            max_depth: Maximum depth to traverse (default 3)

        Returns:
            Dictionary containing organizational hierarchy
        """
        try:
            # Find the manager
            manager = await self.search_user_by_email(manager_email)
            if not manager:
                raise LDAPIntegrationError(f"Manager not found: {manager_email}")

            # Get the manager's DN
            manager_dn = f"uid={manager.uid},{self.base_dn}"

            # Build hierarchy recursively
            hierarchy = await self._build_hierarchy(manager, manager_dn, max_depth)

            self.logger.info(
                f"Built organizational hierarchy for {manager_email} "
                f"with {self._count_members(hierarchy)} total members"
            )

            return hierarchy

        except Exception as e:
            self.logger.error(
                f"Failed to get organizational hierarchy for {manager_email}: {e}"
            )
            raise LDAPIntegrationError(f"Hierarchy query failed: {e}")

    async def _build_hierarchy(
        self, user: LDAPUser, user_dn: str, max_depth: int, current_depth: int = 0
    ) -> Dict[str, Any]:
        """Recursively build organizational hierarchy.

        Args:
            user: LDAPUser object for current user
            user_dn: Distinguished name of current user
            max_depth: Maximum depth to traverse
            current_depth: Current recursion depth

        Returns:
            Dictionary representing the hierarchy
        """
        hierarchy = {
            "uid": user.uid,
            "email": user.email,
            "display_name": user.display_name,
            "title": user.title,
            "department": user.department,
            "direct_reports": [],
        }

        # Stop if we've reached max depth
        if current_depth >= max_depth:
            return hierarchy

        # Get direct reports
        direct_reports = await self.get_direct_reports(user_dn)

        # Recursively build hierarchy for each direct report
        for report in direct_reports:
            report_dn = f"uid={report.uid},{self.base_dn}"
            report_hierarchy = await self._build_hierarchy(
                report, report_dn, max_depth, current_depth + 1
            )
            hierarchy["direct_reports"].append(report_hierarchy)

        return hierarchy

    def _count_members(self, hierarchy: Dict[str, Any]) -> int:
        """Count total members in hierarchy."""
        count = 1  # Count self
        for report in hierarchy.get("direct_reports", []):
            count += self._count_members(report)
        return count

    async def extract_emails_from_hierarchy(
        self, hierarchy: Dict[str, Any]
    ) -> List[str]:
        """Extract all email addresses from organizational hierarchy.

        Args:
            hierarchy: Organizational hierarchy dictionary

        Returns:
            List of email addresses
        """
        emails = []

        def _extract_emails(node: Dict[str, Any]) -> None:
            if node.get("email"):
                emails.append(node["email"])
            for report in node.get("direct_reports", []):
                _extract_emails(report)

        _extract_emails(hierarchy)
        return emails

    async def map_emails_to_jira_usernames(self, emails: List[str]) -> Dict[str, str]:
        """Map email addresses to Jira usernames.

        For Red Hat, the mapping is typically:
        - Email: user@redhat.com
        - Jira username: user

        Args:
            emails: List of email addresses

        Returns:
            Dictionary mapping emails to Jira usernames
        """
        mapping = {}

        for email in emails:
            # Validate email
            try:
                InputValidator.validate_email(email)
            except Exception:
                self.logger.warning(f"Invalid email format: {email}")
                continue

            # Extract username from email
            if "@" in email:
                username = email.split("@")[0]
                mapping[email] = username
            else:
                # If no @ symbol, assume it's already a username
                mapping[email] = email

        self.logger.info(f"Mapped {len(mapping)} emails to Jira usernames")
        return mapping

    async def get_team_members_for_manager(
        self, manager_identifier: str, max_depth: int = 3
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Get all team members (Jira usernames) for a manager.

        This is a convenience method that combines hierarchy extraction
        and email-to-username mapping.

        Args:
            manager_identifier: Manager's email or username
            max_depth: Maximum depth to traverse

        Returns:
            Tuple of (list of Jira usernames, organizational hierarchy)
        """
        try:
            # Determine if identifier is email or username
            if "@" in manager_identifier:
                manager = await self.search_user_by_email(manager_identifier)
            else:
                manager = await self.search_user_by_uid(manager_identifier)

            if not manager:
                raise LDAPIntegrationError(f"Manager not found: {manager_identifier}")

            # Get organizational hierarchy
            hierarchy = await self.get_organizational_hierarchy(
                manager.email, max_depth
            )

            # Extract emails
            emails = await self.extract_emails_from_hierarchy(hierarchy)

            # Map to Jira usernames
            email_to_username = await self.map_emails_to_jira_usernames(emails)

            # Get unique usernames
            usernames = list(set(email_to_username.values()))

            self.logger.info(
                f"Found {len(usernames)} team members for {manager_identifier}"
            )

            return usernames, hierarchy

        except Exception as e:
            self.logger.error(
                f"Failed to get team members for {manager_identifier}: {e}"
            )
            raise LDAPIntegrationError(f"Team member query failed: {e}")

    async def validate_connection(self) -> bool:
        """Validate LDAP connection.

        Returns:
            True if connection is valid
        """
        try:
            await self.connect()

            # Test with a simple search
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._connection.search(
                    search_base=self.base_dn,
                    search_filter="(uid=nobody)",  # Unlikely to exist
                    attributes=["uid"],
                    size_limit=1,
                ),
            )

            # If we can execute a search, connection is valid
            self.logger.info("LDAP connection validated successfully")
            return True

        except Exception as e:
            self.logger.error(f"LDAP connection validation failed: {e}")
            return False

    def get_connection_info(self) -> Dict[str, Any]:
        """Get LDAP connection information."""
        info = {
            "server_url": self.server_url,
            "base_dn": self.base_dn,
            "connected": bool(self._connection and self._connection.bound),
            "use_ssl": self.use_ssl,
            "validate_certs": self.validate_certs,
        }

        if self._server:
            try:
                info["server_info"] = {
                    "host": self._server.host,
                    "port": self._server.port,
                    "ssl": self._server.ssl,
                }
            except Exception as e:
                self.logger.warning(f"Could not get server info: {e}")

        return info

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
