# Unified Configuration UI Mockup

## Adaptive Mode Examples

### Mode 1: First-Time User (Wizard Mode)
```
┌─────────────────────────────────────────────────────────────────┐
│ Welcome to WES Setup                                      [X] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    Welcome to WES!                       │  │
│  │                                                          │  │
│  │  Let's set up your executive summary automation tool.   │  │
│  │  This wizard will guide you through:                    │  │
│  │                                                          │  │
│  │  • Connecting to your Jira instance                     │  │
│  │  • Setting up Google Docs integration                   │  │
│  │  • Configuring Gemini AI                               │  │
│  │                                                          │  │
│  │  The setup takes about 5 minutes.                       │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Progress: [■□□□□] Step 1 of 5                                 │
│                                                                 │
│  [Skip Wizard]                          [Cancel] [Next →]      │
└─────────────────────────────────────────────────────────────────┘
```

### Mode 2: Returning User (Direct Mode)
```
┌─────────────────────────────────────────────────────────────────┐
│ Settings                                                  [X] │
├───────────┬─────────────────────────────────────────────────────┤
│ ▼ Jira    │  Jira Configuration                               │
│   Google  │ ┌─────────────────────────────────────────────┐  │
│   Gemini  │ │ Connection Details                          │  │
│   App     │ │                                             │  │
│   Security│ │ Instance Type: [Cloud Jira         ▼]      │  │
│           │ │                                             │  │
│           │ │ Jira URL:     [https://company.atlassian.net]│  │
│           │ │ Username:     [user@company.com           ] │  │
│           │ │ API Token:    [••••••••••••••••          ] │  │
│           │ │                                             │  │
│           │ │ [Test Connection]  ✓ Connected              │  │
│           │ └─────────────────────────────────────────────┘  │
│           │                                                    │
│           │ ▼ Advanced Settings                               │
│           │ ┌─────────────────────────────────────────────┐  │
│           │ │ □ Verify SSL Certificates                   │  │
│           │ │ Timeout (sec): [30    ]                     │  │
│           │ │ Max Results:   [100   ]                     │  │
│           │ └─────────────────────────────────────────────┘  │
│           │                                                    │
│           │              [Apply] [Save] [Cancel]              │
└───────────┴─────────────────────────────────────────────────────┘
```

### Mode 3: Incomplete Config (Guided Mode)
```
┌─────────────────────────────────────────────────────────────────┐
│ Complete Your Setup                                       [X] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ⚠️  Your configuration is incomplete. Let's finish setup:      │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Status Overview                                        │  │
│  │                                                          │  │
│  │  ✓ Jira:        Connected to company.atlassian.net     │  │
│  │  ⚠️ Google Docs: OAuth setup required                   │  │
│  │  ✗ Gemini AI:   API key missing                        │  │
│  │                                                          │  │
│  │  Click on any incomplete service to set it up.         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│  [➤ Setup Google Docs]  [➤ Setup Gemini AI]                   │
│                                                                 │
│  [Complete Later]                    [Help] [Continue Setup]   │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### Unified Connection Tester Component
```
┌─────────────────────────────────────────────────────────┐
│ Connection Test                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Service: Jira Cloud                                    │
│  Status:  ⟳ Testing connection...                      │
│                                                         │
│  [████████████░░░░░░] 60%                             │
│                                                         │
│  Details:                                               │
│  ✓ URL is reachable                                   │
│  ✓ Credentials are valid                               │
│  ⟳ Checking permissions...                             │
│                                                         │
│                                          [Cancel]      │
└─────────────────────────────────────────────────────────┘
```

### Smart Service Selector
```
┌─────────────────────────────────────────────────────────┐
│ Select Your Jira Type                                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ◉ Cloud Jira (Atlassian Cloud)                       │
│     Most common for modern teams                        │
│     Example: company.atlassian.net                     │
│                                                         │
│  ○ Server/Data Center                                  │
│     Self-hosted Jira instances                         │
│     Example: jira.company.com                          │
│                                                         │
│  ○ Red Hat Jira                                       │
│     For Red Hat employees                              │
│     Uses Kerberos authentication                       │
│                                                         │
│  [Auto-Detect from URL]            [Help] [Continue]   │
└─────────────────────────────────────────────────────────┘
```

### Progressive Disclosure Example
```
┌─────────────────────────────────────────────────────────┐
│ Google Configuration                                    │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────┐   │
│ │ Basic Settings                                   │   │
│ │                                                  │   │
│ │ Authentication Method:                           │   │
│ │ ◉ OAuth 2.0 (Recommended)                       │   │
│ │ ○ Service Account                               │   │
│ │                                                  │   │
│ │ [Configure OAuth]  ✓ Authenticated as:          │   │
│ │                    user@company.com             │   │
│ └─────────────────────────────────────────────────┘   │
│                                                         │
│ ▶ Show Advanced Settings                               │
│                                                         │
│ When expanded:                                          │
│ ┌─────────────────────────────────────────────────┐   │
│ │ Advanced Settings                                │   │
│ │                                                  │   │
│ │ OAuth Scopes:                                    │   │
│ │ ☑ Google Docs (read/write)                      │   │
│ │ ☑ Google Drive (create)                         │   │
│ │ □ Google Sheets (optional)                      │   │
│ │                                                  │   │
│ │ Token Storage:                                   │   │
│ │ ◉ Encrypted local storage                       │   │
│ │ ○ System keychain                               │   │
│ │                                                  │   │
│ │ Retry Attempts: [3    ]                         │   │
│ │ Request Timeout: [30   ] seconds                │   │
│ └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Navigation Patterns

### Breadcrumb Navigation (Wizard Mode)
```
Setup > Jira Configuration > Connection Test
[←Back]                                [Next→]
```

### Tab with Status Indicators (Direct Mode)
```
┌──────────┬────────────┬─────────────┬───────┬──────────┐
│ ✓ Jira   │ ⚠️ Google  │ ✗ Gemini   │  App  │ Security │
└──────────┴────────────┴─────────────┴───────┴──────────┘
```

### Quick Jump Sidebar (All Modes)
```
├───────────┐
│ Quick Jump│
├───────────┤
│ › Jira    │
│   • URL   │
│   • Auth  │
│   • Test  │
│ › Google  │
│   • OAuth │
│   • Scope │
│ › Gemini  │
│   • API   │
│   • Model │
└───────────┘
```

## Responsive Behavior

### Validation Indicators
- **Real-time**: Green checkmark appears as valid input detected
- **Warning**: Orange icon with tooltip for non-critical issues  
- **Error**: Red icon with clear error message
- **Loading**: Spinner during async validation

### Connection Test States
1. **Idle**: "Test Connection" button enabled
2. **Testing**: Progress bar with current step
3. **Success**: Green checkmark with "Connected"
4. **Failed**: Red X with specific error and fix suggestion
5. **Cached**: "✓ Connected (verified 2 min ago)"

### Save Behavior
- **Auto-save**: Draft changes saved locally
- **Apply**: Saves to config without closing dialog
- **Save**: Saves and closes dialog
- **Cancel**: Discards changes with confirmation if dirty

## Accessibility Features
- **Keyboard Navigation**: Full tab order support
- **Screen Reader**: ARIA labels and live regions
- **High Contrast**: Respects system theme
- **Focus Indicators**: Clear visual focus states
- **Error Announcements**: Screen reader announces validation errors