# Red Hat Jira Integration

This document explains how to set up and use the Red Hat Jira integration features in the Executive Summary Tool.

## Overview

The Executive Summary Tool provides enhanced support for Red Hat Jira instances with:

- ✅ **Automatic Detection**: Recognizes Red Hat Jira domains (redhat.com, jira.redhat.com, etc.)
- ✅ **Enhanced Authentication**: Red Hat-specific username validation and guidance  
- ✅ **Optimized Performance**: Enterprise-grade rate limiting and retry strategies
- ✅ **rhjira Library Support**: Uses the specialized rhjira Python library when available
- ✅ **Fallback Compatibility**: Gracefully falls back to standard Jira library

## Installation

### Standard Installation

The base application works with Red Hat Jira instances using the standard Jira library:

```bash
pip install wes
```

### Enhanced Red Hat Integration (Optional)

For optimal Red Hat Jira performance, install with Red Hat-specific enhancements:

```bash
# Install with Red Hat Jira optimization
pip install wes[redhat]
```

This will install the specialized `rhjira` library from the official Red Hat repository.

### Manual rhjira Installation

You can also install the rhjira library separately:

```bash
# Install rhjira library directly
pip install git+https://gitlab.com/prarit/rhjira-python.git
```

## Usage

### Automatic Detection

The application automatically detects Red Hat Jira instances based on URL patterns:

**Detected Red Hat Domains:**
- `*.redhat.com`
- `jira.redhat.com`
- `issues.redhat.com`
- `bugzilla.redhat.com`

### Setup Wizard

When you enter a Red Hat Jira URL in the setup wizard, you'll see:

1. **🔴 Red Hat Jira instance detected** - Visual confirmation
2. **Red Hat Username:** - Specific field labeling
3. **Enhanced validation** - Red Hat username format checking
4. **Contextual help** - Red Hat-specific authentication guidance

### Username Requirements

**Red Hat Jira Username Format:**
- Minimum 3 characters
- Alphanumeric characters, dots, underscores, and hyphens allowed
- Typically your Red Hat employee ID or LDAP username
- Example: `jdoe`, `john.doe`, `j-doe`

**Not accepted for Red Hat Jira:**
- Email addresses (use your username instead)
- Special characters except `.`, `_`, `-`
- Spaces or other whitespace

### Authentication

**⚠️ IMPORTANT: Red Hat Jira instances require OAuth authentication, not API tokens.**

Red Hat Jira instances use OAuth 1.0a authentication instead of API tokens:

1. **OAuth Setup Required:**
   - Red Hat Jira instances do not support API token authentication
   - OAuth 1.0a authentication must be configured by your Red Hat administrator
   - Contact your Red Hat IT administrator for OAuth setup

2. **Alternative Authentication Methods:**
   - **Red Hat SSO**: Use your Red Hat Single Sign-On credentials
   - **OAuth Consumer**: Requires consumer key/secret setup by administrator
   - **Kerberos**: For corporate network environments

3. **Current Limitation:**
   - This application currently supports API token authentication only
   - Red Hat Jira integration requires additional OAuth implementation
   - Contact support for OAuth-enabled version

## Features

### Enhanced Performance

When `rhjira` is installed, you get:

- **Optimized Queries**: Red Hat-specific JQL optimizations
- **Better Error Handling**: Red Hat-aware error parsing
- **Enterprise Reliability**: Enhanced retry strategies for corporate networks
- **Custom Fields**: Support for Red Hat-specific custom fields

### Fallback Behavior

If `rhjira` is not installed:

- **Graceful Degradation**: Uses standard `jira` library
- **Red Hat Optimizations**: Still applies Red Hat-specific configurations
- **Full Functionality**: All features work with standard library
- **Performance**: Slightly reduced optimization but full compatibility

### Logging

Red Hat Jira operations are logged with specific identifiers:

```python
# Log entries will show:
service="redhat_jira"
client_type="rhjira" or "jira" 
```

## Configuration Examples

### Red Hat Employee Setup

```yaml
jira:
  url: "https://issues.redhat.com"
  username: "jdoe"  # Your Red Hat username
  api_token: "your-api-token"
```

### Red Hat Partner/Contractor Setup

```yaml
jira:
  url: "https://jira.redhat.com"
  username: "contractor-id"
  api_token: "your-api-token"
```

## Troubleshooting

### Common Issues

**Q: I get "Red Hat Jira requires OAuth authentication" error**

A: Red Hat Jira instances require OAuth authentication instead of API tokens. This is by design for security. Contact your Red Hat administrator to:
- Set up OAuth consumer credentials
- Configure OAuth access for your application
- Provide alternative access methods

**Q: "Client must be authenticated to access this resource" (HTTP 401)**

A: This error indicates that Red Hat Jira rejected your API token authentication. Red Hat Jira requires OAuth. See above for OAuth setup.

**Q: Connection fails with SSL errors**

A: Red Hat corporate networks may require specific SSL configuration. The application automatically handles common SSL scenarios for Red Hat domains.

**Q: Can I use my email address as username?**

A: Username format is less relevant since OAuth is required. However, Red Hat typically uses employee IDs or LDAP usernames.

### Performance Optimization

For best performance with Red Hat Jira:

1. **Install rhjira**: `pip install wes[redhat]`
2. **Use VPN**: Connect to Red Hat VPN for optimal network performance
3. **Check Rate Limits**: Red Hat may have specific rate limiting policies

### Getting Help

**Red Hat-specific Issues:**
- Check with your Red Hat IT administrator for username format
- Verify API token permissions in Red Hat Jira settings
- Ensure you have access to the specific Red Hat Jira instance

**Application Issues:**
- Review application logs for `redhat_jira` entries
- Check connection info in the application settings
- Verify the rhjira library installation status

## Development

### Testing Red Hat Integration

```python
from wes.integrations.redhat_jira_client import is_redhat_jira, RedHatJiraClient

# Test URL detection
assert is_redhat_jira("https://issues.redhat.com") == True
assert is_redhat_jira("https://company.atlassian.net") == False

# Test client creation
client = RedHatJiraClient(
    url="https://issues.redhat.com",
    username="testuser", 
    api_token="test-token"
)
```

### Contributing

When contributing Red Hat Jira improvements:

1. Test with both `rhjira` installed and uninstalled
2. Ensure graceful fallback behavior
3. Add appropriate logging with `redhat_jira` service identifier
4. Follow Red Hat username validation patterns

## Security Notes

- **API Tokens**: Never commit API tokens to version control
- **Username Privacy**: Red Hat usernames may be considered internal information
- **Network Security**: Red Hat integration respects corporate network policies
- **Audit Logging**: All Red Hat Jira operations are logged for security compliance

---

For more information about the rhjira library, visit: https://gitlab.com/prarit/rhjira-python/