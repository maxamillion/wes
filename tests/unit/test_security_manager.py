"""Unit tests for SecurityManager."""

import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path

from src.executive_summary_tool.core.security_manager import SecurityManager
from src.executive_summary_tool.utils.exceptions import SecurityError


class TestSecurityManager:
    """Test cases for SecurityManager class."""
    
    @pytest.fixture
    def mock_keyring(self):
        """Mock keyring module."""
        with patch('src.executive_summary_tool.core.security_manager.keyring') as mock:
            mock.get_password.return_value = None
            mock.set_password.return_value = None
            mock.delete_password.return_value = None
            yield mock
    
    @pytest.fixture
    def mock_home_path(self, tmp_path):
        """Mock Path.home() to return temporary directory."""
        with patch('pathlib.Path.home') as mock:
            mock.return_value = tmp_path
            yield tmp_path
    
    def test_security_manager_initialization(self, mock_keyring, mock_home_path):
        """Test SecurityManager initialization."""
        manager = SecurityManager()
        
        assert manager._keyring_service == "executive-summary-tool"
        assert manager._cipher_suite is not None
    
    def test_encrypt_decrypt_credential(self, mock_keyring, mock_home_path):
        """Test credential encryption and decryption."""
        manager = SecurityManager()
        
        test_credential = "test_api_key_12345"
        
        # Test encryption
        encrypted = manager.encrypt_credential(test_credential)
        assert encrypted != test_credential
        assert isinstance(encrypted, str)
        
        # Test decryption
        decrypted = manager.decrypt_credential(encrypted)
        assert decrypted == test_credential
    
    def test_store_retrieve_credential(self, mock_keyring, mock_home_path):
        """Test storing and retrieving credentials."""
        manager = SecurityManager()
        
        service = "test_service"
        username = "test_user"
        credential = "test_password_123"
        
        # Test store credential
        manager.store_credential(service, username, credential)
        
        # Verify keyring was called
        mock_keyring.set_password.assert_called_once()
        
        # Mock keyring to return encrypted credential
        encrypted_cred = manager.encrypt_credential(credential)
        mock_keyring.get_password.return_value = encrypted_cred
        
        # Test retrieve credential
        retrieved = manager.retrieve_credential(service, username)
        assert retrieved == credential
    
    def test_retrieve_nonexistent_credential(self, mock_keyring, mock_home_path):
        """Test retrieving a credential that doesn't exist."""
        manager = SecurityManager()
        mock_keyring.get_password.return_value = None
        
        result = manager.retrieve_credential("nonexistent", "user")
        assert result is None
    
    def test_delete_credential(self, mock_keyring, mock_home_path):
        """Test deleting a credential."""
        manager = SecurityManager()
        
        manager.delete_credential("test_service", "test_user")
        
        # Verify keyring delete was called
        mock_keyring.delete_password.assert_called_once()
    
    def test_validate_integrity(self, mock_keyring, mock_home_path):
        """Test integrity validation."""
        manager = SecurityManager()
        
        # Should return True for successful validation
        assert manager.validate_integrity() is True
    
    def test_encryption_without_initialization(self, mock_keyring, mock_home_path):
        """Test encryption when not properly initialized."""
        manager = SecurityManager()
        manager._cipher_suite = None
        
        with pytest.raises(SecurityError, match="Encryption not initialized"):
            manager.encrypt_credential("test")
    
    def test_decryption_without_initialization(self, mock_keyring, mock_home_path):
        """Test decryption when not properly initialized."""
        manager = SecurityManager()
        manager._cipher_suite = None
        
        with pytest.raises(SecurityError, match="Encryption not initialized"):
            manager.decrypt_credential("test")
    
    def test_invalid_encrypted_credential(self, mock_keyring, mock_home_path):
        """Test decryption with invalid encrypted data."""
        manager = SecurityManager()
        
        with pytest.raises(SecurityError, match="Failed to decrypt credential"):
            manager.decrypt_credential("invalid_encrypted_data")
    
    @patch('src.executive_summary_tool.core.security_manager.secrets.token_bytes')
    def test_salt_creation(self, mock_token_bytes, mock_keyring, mock_home_path):
        """Test salt file creation."""
        mock_token_bytes.return_value = b'test_salt_32_bytes_long_exactly'
        
        manager = SecurityManager()
        salt_path = mock_home_path / ".executive-summary-tool" / "salt"
        
        # Verify salt file was created
        assert salt_path.exists()
        assert len(salt_path.read_bytes()) == 32
    
    def test_salt_reuse(self, mock_keyring, mock_home_path):
        """Test that existing salt is reused."""
        # Create salt file first
        salt_dir = mock_home_path / ".executive-summary-tool"
        salt_dir.mkdir(parents=True)
        salt_path = salt_dir / "salt"
        original_salt = b'existing_salt_32_bytes_long_test'
        salt_path.write_bytes(original_salt)
        
        manager = SecurityManager()
        
        # Verify same salt is used
        assert salt_path.read_bytes() == original_salt
    
    def test_master_key_creation(self, mock_keyring, mock_home_path):
        """Test master key creation when none exists."""
        # Mock keyring to return None for existing key
        mock_keyring.get_password.return_value = None
        
        manager = SecurityManager()
        
        # Verify keyring set_password was called to store new key
        mock_keyring.set_password.assert_called()
        
        # Verify the call was for master_key
        args, kwargs = mock_keyring.set_password.call_args
        assert args[0] == "executive-summary-tool"
        assert args[1] == "master_key"
        assert isinstance(args[2], str)  # Base64 encoded key
    
    def test_master_key_retrieval(self, mock_keyring, mock_home_path):
        """Test master key retrieval when it exists."""
        import base64
        
        # Mock existing master key
        test_key = base64.b64encode(b'test_master_key_32_bytes_long!!').decode()
        mock_keyring.get_password.return_value = test_key
        
        manager = SecurityManager()
        
        # Verify existing key was retrieved, not created
        mock_keyring.get_password.assert_called_with("executive-summary-tool", "master_key")
    
    def test_secure_delete(self, mock_keyring, mock_home_path):
        """Test secure deletion of sensitive data."""
        manager = SecurityManager()
        
        # This should not raise an exception
        manager.secure_delete("sensitive_data")
        manager.secure_delete("")
        manager.secure_delete(None)
    
    @patch('src.executive_summary_tool.core.security_manager.keyring')
    def test_keyring_failure_fallback(self, mock_keyring, mock_home_path):
        """Test fallback when keyring operations fail."""
        # Mock keyring to raise exception
        mock_keyring.get_password.side_effect = Exception("Keyring not available")
        mock_keyring.set_password.side_effect = Exception("Keyring not available")
        
        # Should not raise exception if master password is provided
        manager = SecurityManager(master_password="test_password")
        
        # Should still be able to encrypt/decrypt
        test_data = "test_credential"
        encrypted = manager.encrypt_credential(test_data)
        decrypted = manager.decrypt_credential(encrypted)
        assert decrypted == test_data
    
    def test_initialization_failure(self, mock_keyring, mock_home_path):
        """Test handling of initialization failures."""
        with patch('src.executive_summary_tool.core.security_manager.PBKDF2HMAC') as mock_kdf:
            mock_kdf.side_effect = Exception("Crypto initialization failed")
            
            with pytest.raises(SecurityError, match="Failed to initialize encryption"):
                SecurityManager()


@pytest.mark.security
class TestSecurityManagerSecurity:
    """Security-focused tests for SecurityManager."""
    
    def test_credential_not_stored_in_plaintext(self, mock_keyring, tmp_path):
        """Test that credentials are never stored in plaintext."""
        with patch('pathlib.Path.home', return_value=tmp_path):
            manager = SecurityManager()
            
            secret_credential = "super_secret_api_key_12345"
            manager.store_credential("test_service", "test_user", secret_credential)
            
            # Check that the credential doesn't appear in any stored files
            for file_path in tmp_path.rglob("*"):
                if file_path.is_file():
                    try:
                        content = file_path.read_text()
                        assert secret_credential not in content
                    except (UnicodeDecodeError, PermissionError):
                        # Binary files or permission issues - check bytes
                        try:
                            content = file_path.read_bytes()
                            assert secret_credential.encode() not in content
                        except PermissionError:
                            pass  # Skip files we can't read
    
    def test_encryption_key_rotation(self, mock_keyring, tmp_path):
        """Test key rotation functionality."""
        with patch('pathlib.Path.home', return_value=tmp_path):
            manager = SecurityManager()
            
            # This would be a complex test requiring the actual implementation
            # For now, just test that the method doesn't raise an exception
            manager.rotate_master_key()
    
    def test_different_instances_different_keys(self, mock_keyring, tmp_path):
        """Test that different instances create different encryption keys."""
        with patch('pathlib.Path.home', return_value=tmp_path):
            # Reset keyring mock for each instance
            mock_keyring.get_password.return_value = None
            
            manager1 = SecurityManager()
            manager2 = SecurityManager()
            
            test_data = "test_credential"
            
            # Encrypt same data with both managers
            encrypted1 = manager1.encrypt_credential(test_data)
            encrypted2 = manager2.encrypt_credential(test_data)
            
            # Encrypted data should be different (different keys/nonces)
            assert encrypted1 != encrypted2
            
            # But both should decrypt to the same original data
            assert manager1.decrypt_credential(encrypted1) == test_data
            assert manager2.decrypt_credential(encrypted2) == test_data