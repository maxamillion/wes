# LDAP to Jira User Mapping Design

## Overview

After querying LDAP to establish a manager's organizational hierarchy, we collect email addresses for all team members. However, Jira usernames often don't match the email prefix (the part before '@'). This design document outlines a solution to accurately map LDAP email addresses to Jira usernames.

## Current Implementation Issues

The current implementation in `redhat_ldap_client.py` assumes:
```python
# Extract username from email
if "@" in email:
    username = email.split("@")[0]
```

This assumption fails when:
- Jira username differs from email prefix
- Users have changed their email but kept their Jira username
- Organization uses different naming conventions for email vs Jira

## Proposed Solution

### 1. Jira User Search API Integration

Add a new method to query Jira's user search API to find users by email address:

```python
async def search_jira_users_by_email(self, emails: List[str]) -> Dict[str, Dict[str, Any]]:
    """Search for Jira users by their email addresses.
    
    Args:
        emails: List of email addresses to search
        
    Returns:
        Dictionary mapping email to user info (accountId, displayName, etc.)
    """
```

### 2. Enhanced Mapping Process

```python
async def map_emails_to_jira_users(self, emails: List[str]) -> Dict[str, str]:
    """Map email addresses to Jira usernames using Jira API.
    
    Process:
    1. Batch emails into groups (max 50 per request)
    2. Query Jira user search API
    3. Cache results for performance
    4. Handle missing users gracefully
    
    Returns:
        Dictionary mapping email -> Jira username
    """
```

### 3. Caching Strategy

Implement a two-tier cache:
- **Memory Cache**: Short-lived (5 minutes) for current session
- **Persistent Cache**: Longer-lived (24 hours) stored in config directory

```python
class UserMappingCache:
    def __init__(self, ttl_minutes: int = 60):
        self.memory_cache: Dict[str, Tuple[str, float]] = {}
        self.cache_file = Path.home() / ".wes" / "cache" / "user_mappings.json"
        self.ttl = ttl_minutes * 60
```

### 4. Integration Points

#### A. Modify RedHatJiraLDAPIntegration

```python
async def get_manager_team_activities(self, manager_identifier: str, ...):
    # Step 1: Get organizational hierarchy from LDAP
    hierarchy = await self.ldap_client.get_organizational_hierarchy(...)
    
    # Step 2: Extract emails
    emails = await self.ldap_client.extract_emails_from_hierarchy(hierarchy)
    
    # Step 3: NEW - Map emails to Jira users via API
    email_to_jira_user = await self.jira_client.search_users_by_emails(emails)
    
    # Step 4: Get activities using correct Jira usernames
    jira_usernames = list(email_to_jira_user.values())
    activities = await self.jira_client.get_user_activities(users=jira_usernames, ...)
```

#### B. Add to JiraClient

```python
async def search_users_by_emails(self, emails: List[str]) -> Dict[str, str]:
    """Search for Jira users by email addresses.
    
    Uses Jira REST API v3: GET /rest/api/3/user/search
    """
    mapping = {}
    
    # Check cache first
    uncached_emails = []
    for email in emails:
        cached_user = self.cache.get(email)
        if cached_user:
            mapping[email] = cached_user
        else:
            uncached_emails.append(email)
    
    # Batch API requests for uncached emails
    for batch in chunks(uncached_emails, 50):
        users = await self._search_users_batch(batch)
        for email, username in users.items():
            mapping[email] = username
            self.cache.set(email, username)
    
    return mapping
```

### 5. Error Handling

Handle various edge cases:
- **User not found**: Log warning, skip user
- **Multiple matches**: Use primary email or most recently active
- **API errors**: Fall back to email prefix method
- **Rate limiting**: Implement exponential backoff

### 6. Configuration

Add configuration options:
```python
@dataclass
class LDAPConfig:
    # ... existing fields ...
    user_mapping_cache_ttl: int = 1440  # 24 hours
    fallback_to_email_prefix: bool = True
    batch_size: int = 50
```

## Implementation Plan

1. **Phase 1**: Implement Jira user search API wrapper
2. **Phase 2**: Add caching layer
3. **Phase 3**: Integrate with LDAP workflow
4. **Phase 4**: Add comprehensive error handling
5. **Phase 5**: Performance testing and optimization

## API Reference

### Jira REST API v3 - User Search

**Endpoint**: `GET /rest/api/3/user/search`

**Parameters**:
- `query`: Search string (can be email)
- `maxResults`: Maximum number of results (default 50)
- `startAt`: Pagination offset

**Response**:
```json
[
  {
    "accountId": "5b10a2844c20165700ede21g",
    "emailAddress": "user@example.com",
    "displayName": "User Name",
    "active": true
  }
]
```

## Performance Considerations

1. **Batch Processing**: Group emails in batches of 50
2. **Parallel Requests**: Use asyncio for concurrent API calls
3. **Caching**: Reduce API calls by 80%+ with effective caching
4. **Rate Limiting**: Respect Jira's rate limits (100 requests/minute)

## Security Considerations

1. **Data Privacy**: Don't log full email addresses
2. **Cache Security**: Encrypt persistent cache
3. **API Token**: Use secure storage for credentials
4. **Audit Logging**: Track user lookups for compliance