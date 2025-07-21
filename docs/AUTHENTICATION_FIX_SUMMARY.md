# Red Hat Jira Authentication Fix Summary

## Problem
The Red Hat Jira integration was receiving HTML login pages instead of JSON API responses, indicating authentication failures. The logs showed:
- Non-JSON response warnings with Content-Type: text/html
- HTML content containing "You are already logged in - Red Hat Issue Tracker"
- Status code 200 (not an error) but with login page content

## Root Cause
The python-jira library's `token_auth` parameter doesn't properly handle Bearer token authentication required by Red Hat Jira. When we passed the token to the JIRA constructor, it wasn't being used correctly for API calls.

## Solution
Modified the client initialization to:
1. Create JIRA client WITHOUT passing `token_auth` parameter
2. Set up a custom session with Bearer token in headers
3. Override the JIRA client's internal session with our custom session

### Changes Made

#### File: `src/wes/integrations/redhat_jira_client.py`

1. **Updated `_initialize_standard_jira_client` method (lines 216-224)**:
   - Removed `token_auth` parameter from JIRA constructor
   - Added comment explaining why we don't use token_auth
   - Rely on custom session with Bearer token headers

2. **Updated `_initialize_rhjira_client` method (lines 141-187)**:
   - Removed `token_auth` parameter from all JIRA/RHJIRA constructors
   - Added session setup with Bearer token headers
   - Override client session after initialization

3. **Enhanced `_make_request` method (lines 773-857)**:
   - Ensures Bearer token is added to headers if not present
   - Added authentication error detection for login page responses
   - Provides helpful error messages about PAT configuration

## Result
- All API calls now properly use Bearer token authentication
- No more HTML login page responses
- Proper JSON responses from Red Hat Jira API
- All unit tests pass successfully

## Testing
Run the following tests to verify the fix:
```bash
uv run pytest tests/unit/test_redhat_jira_client.py -k "initialization or authentication" -xvs
uv run pytest tests/unit/test_jira_user_mapper.py::TestJiraUserMapper::test_search_redhat_user_with_correct_endpoint -xvs
```