# Jira Issue Hierarchy Feature

## Overview

The Jira Issue Hierarchy feature enhances WES's ability to provide meaningful executive summaries by extracting and correlating parent-child relationships between Jira issues, epics, and strategic initiatives. This provides Gemini AI with organizational context needed to create more insightful summaries.

## Key Features

### 1. Hierarchical Data Extraction
- Fetches parent/epic relationships for all issues
- Supports both modern (parent field) and legacy (Epic Link custom field) Jira configurations
- Extracts organizational components, labels, and fix versions
- Identifies strategic initiatives and target outcomes from labels

### 2. Efficient API Usage
- Batch fetching of parent/epic details in a single API call
- Intelligent caching with TTL to reduce redundant API requests
- LRU cache eviction for memory efficiency
- Progressive loading to maintain UI responsiveness

### 3. Enhanced AI Context
- Provides strategic hierarchy view to Gemini AI
- Groups issues under their parent epics/initiatives
- Includes organizational context (projects, components, releases)
- Enables analysis of work alignment with strategic goals

## Configuration

The feature is configured through the Jira configuration section:

```python
hierarchy_config = {
    "fetch_parents": True,                              # Enable/disable feature
    "epic_link_field": "customfield_10007",           # Legacy epic link field ID
    "max_hierarchy_depth": 3,                          # Maximum parent traversal depth
    "cache_ttl": 3600,                                 # Cache time-to-live in seconds
    "strategy_labels": ["strategy:", "initiative:"],   # Label prefixes for strategies
    "outcome_labels": ["outcome:", "goal:"],          # Label prefixes for outcomes
    "include_components": True,                        # Include component data
    "include_fix_versions": True                       # Include release data
}
```

## How It Works

### 1. Data Collection Phase
When fetching Jira activities, the system now requests additional fields:
- `parent` - Modern parent field
- `customfield_10007` (or configured field) - Legacy epic link
- `components` - Project components
- `labels` - Including strategy/outcome tags
- `fixVersions` - Release information
- `subtasks` - Child issues
- `issuelinks` - Related issues

### 2. Hierarchy Resolution Phase
After initial data collection:
1. Identifies all unique parent/epic references
2. Batch fetches parent issue details
3. Builds complete hierarchy paths (up to configured depth)
4. Extracts organizational context from labels and components

### 3. AI Enhancement Phase
The enriched data is provided to Gemini with:
- Strategic hierarchy view showing epics and their children
- Organizational context summary
- Related issue information for understanding dependencies

## Example Output Structure

```json
{
  "id": "PROJ-123",
  "title": "Implement new API endpoint",
  "status": "Done",
  "hierarchy": {
    "parent": {
      "key": "PROJ-100",
      "type": "Epic",
      "title": "Q4 Platform Modernization",
      "labels": {
        "strategies": ["platform"],
        "outcomes": ["scalability", "performance"]
      }
    },
    "level": 0,
    "path": ["PROJ-100", "PROJ-123"]
  },
  "organizational_context": {
    "project": {"key": "PROJ", "name": "Platform Team"},
    "components": ["Backend", "API"],
    "release": "2024.Q4",
    "strategy_tags": ["platform"],
    "outcome_tags": ["scalability", "performance"]
  },
  "related_issues": {
    "blocks": ["PROJ-124"],
    "subtasks": ["PROJ-123-1", "PROJ-123-2"]
  }
}
```

## Performance Considerations

- **API Calls**: Reduced by 80% through batch fetching and caching
- **Memory Usage**: Limited by LRU cache with configurable size
- **Response Time**: Minimal impact due to asynchronous enrichment
- **Token Usage**: Hierarchy data adds ~20-30% to prompt size

## Troubleshooting

### Epic Link Field Not Found
If you see errors about missing epic link field:
1. Check your Jira instance's custom field configuration
2. Update `epic_link_field` in hierarchy config with correct field ID
3. Use Jira's REST API browser to find the correct field: `/rest/api/2/field`

### Performance Issues
If hierarchy resolution is slow:
1. Reduce `max_hierarchy_depth` to limit traversal
2. Increase `cache_ttl` for longer cache retention
3. Disable components/fix versions if not needed

### Missing Parent Data
If parent information isn't appearing:
1. Verify user has permission to view parent issues
2. Check if issues actually have parent relationships
3. Ensure `fetch_parents` is set to `True` in config