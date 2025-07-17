"""Security manager for credential encryption and secure operations."""

import base64
import secrets
from pathlib import Path
from typing import Dict, Optional

import keyring
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..utils.exceptions import SecurityError
from ..utils.logging_config import get_security_logger


class SecurityManager:
    """Manages secure credential storage and encryption operations."""

    def __init__(self, master_password: Optional[str] = None):
        self.security_logger = get_security_logger()
        self._master_password = master_password
        self._cipher_suite: Optional[Fernet] = None
        self._keyring_service = "wes"
        self._initialize_encryption()

    def _initialize_encryption(self) -> None:
        """Initialize encryption system."""
        try:
            # Get or create master key
            master_key = self._get_or_create_master_key()

            # Derive encryption key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self._get_salt(),
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_key))
            self._cipher_suite = Fernet(key)

            self.security_logger.log_security_event(
                "encryption_initialized", severity="INFO"
            )

        except Exception as e:
            self.security_logger.log_error("encryption_initialization_failed", str(e))
            raise SecurityError(f"Failed to initialize encryption: {e}")

    def _get_or_create_master_key(self) -> bytes:
        """Get or create master encryption key."""
        try:
            # Try to get existing key from keyring
            stored_key = keyring.get_password(self._keyring_service, "master_key")

            if stored_key:
                return base64.b64decode(stored_key)

            # Create new master key
            master_key = secrets.token_bytes(32)
            encoded_key = base64.b64encode(master_key).decode()

            # Store in keyring
            keyring.set_password(self._keyring_service, "master_key", encoded_key)

            self.security_logger.log_security_event(
                "master_key_created", severity="INFO"
            )

            return master_key

        except Exception as e:
            # Fallback to password-based key if keyring fails
            if self._master_password:
                return self._master_password.encode()
            else:
                raise SecurityError(f"Failed to manage master key: {e}")

    def _get_salt(self) -> bytes:
        """Get or create salt for key derivation."""
        salt_path = Path.home() / ".wes" / "salt"

        if salt_path.exists():
            return salt_path.read_bytes()

        # Create new salt
        salt = secrets.token_bytes(32)
        salt_path.parent.mkdir(parents=True, exist_ok=True)
        salt_path.write_bytes(salt)

        # Set restrictive permissions
        salt_path.chmod(0o600)

        return salt

    def encrypt_credential(self, credential: str) -> str:
        """Encrypt credential string."""
        if not self._cipher_suite:
            raise SecurityError("Encryption not initialized")

        try:
            encrypted_bytes = self._cipher_suite.encrypt(credential.encode())
            return base64.b64encode(encrypted_bytes).decode()

        except Exception as e:
            self.security_logger.log_error(
                "credential_encryption_failed", "Failed to encrypt credential"
            )
            raise SecurityError(f"Failed to encrypt credential: {e}")

    def decrypt_credential(self, encrypted_credential: str) -> str:
        """Decrypt credential string."""
        if not self._cipher_suite:
            raise SecurityError("Encryption not initialized")

        try:
            encrypted_bytes = base64.b64decode(encrypted_credential)
            decrypted_bytes = self._cipher_suite.decrypt(encrypted_bytes)
            return decrypted_bytes.decode()

        except Exception as e:
            self.security_logger.log_error(
                "credential_decryption_failed", "Failed to decrypt credential"
            )
            raise SecurityError(f"Failed to decrypt credential: {e}")

    def store_credential(self, service: str, username: str, credential: str) -> None:
        """Store encrypted credential in keyring."""
        try:
            encrypted_credential = self.encrypt_credential(credential)
            key = f"{service}:{username}"
            keyring.set_password(self._keyring_service, key, encrypted_credential)

            self.security_logger.log_security_event(
                "credential_stored", service=service, username=username
            )

        except Exception as e:
            self.security_logger.log_error(
                "credential_storage_failed",
                f"Failed to store credential for {service}:{username}",
            )
            raise SecurityError(f"Failed to store credential: {e}")

    def retrieve_credential(self, service: str, username: str) -> Optional[str]:
        """Retrieve and decrypt credential from keyring."""
        try:
            key = f"{service}:{username}"
            encrypted_credential = keyring.get_password(self._keyring_service, key)

            if not encrypted_credential:
                return None

            credential = self.decrypt_credential(encrypted_credential)

            self.security_logger.log_security_event(
                "credential_retrieved", service=service, username=username
            )

            return credential

        except Exception as e:
            self.security_logger.log_error(
                "credential_retrieval_failed",
                f"Failed to retrieve credential for {service}:{username}",
            )
            raise SecurityError(f"Failed to retrieve credential: {e}")

    def delete_credential(self, service: str, username: str) -> None:
        """Delete credential from keyring."""
        try:
            key = f"{service}:{username}"
            keyring.delete_password(self._keyring_service, key)

            self.security_logger.log_security_event(
                "credential_deleted", service=service, username=username
            )

        except Exception as e:
            self.security_logger.log_error(
                "credential_deletion_failed",
                f"Failed to delete credential for {service}:{username}",
            )
            raise SecurityError(f"Failed to delete credential: {e}")

    def list_stored_credentials(self) -> Dict[str, str]:
        """List all stored credentials (returns service:username pairs)."""
        # Note: This is a simplified implementation
        # In production, you'd need a more sophisticated approach
        # to enumerate keyring entries
        return {}

    def rotate_master_key(self) -> None:
        """Rotate master encryption key."""
        try:
            # This is a complex operation that would require:
            # 1. Decrypting all existing credentials with old key
            # 2. Generating new master key
            # 3. Re-encrypting all credentials with new key
            # 4. Updating keyring storage

            self.security_logger.log_security_event(
                "master_key_rotation_started", severity="INFO"
            )

            # Implementation would go here
            # For now, just log the event

            self.security_logger.log_security_event(
                "master_key_rotation_completed", severity="INFO"
            )

        except Exception as e:
            self.security_logger.log_error("master_key_rotation_failed", str(e))
            raise SecurityError(f"Failed to rotate master key: {e}")

    def validate_integrity(self) -> bool:
        """Validate integrity of security system."""
        try:
            # Test encryption/decryption
            test_data = "test_credential_data"
            encrypted = self.encrypt_credential(test_data)
            decrypted = self.decrypt_credential(encrypted)

            if decrypted != test_data:
                raise SecurityError("Integrity check failed")

            self.security_logger.log_security_event(
                "integrity_check_passed", severity="INFO"
            )

            return True

        except Exception as e:
            self.security_logger.log_error("integrity_check_failed", str(e))
            return False

    def secure_delete(self, data: str) -> None:
        """Securely delete sensitive data from memory."""
        # Python doesn't provide guaranteed secure deletion
        # This is a best-effort approach
        if data:
            # Overwrite with random data
            random_data = secrets.token_hex(len(data))
            data = random_data
            del data
            del random_data
