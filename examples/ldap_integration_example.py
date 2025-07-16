#!/usr/bin/env python3
"""Example script demonstrating Red Hat LDAP integration for Jira queries.

This script shows how to:
1. Configure LDAP settings
2. Query organizational hierarchy
3. Fetch Jira activities for an entire team
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.wes.core.config_manager import ConfigManager
from src.wes.core.orchestrator import WorkflowOrchestrator
from src.wes.integrations.redhat_ldap_client import RedHatLDAPClient
from src.wes.integrations.redhat_jira_ldap_integration import RedHatJiraLDAPIntegration


async def test_ldap_connection():
    """Test basic LDAP connectivity."""
    print("\n=== Testing LDAP Connection ===")
    
    client = RedHatLDAPClient()
    
    try:
        await client.connect()
        print("✅ Successfully connected to LDAP server")
        
        # Test validation
        valid = await client.validate_connection()
        print(f"✅ Connection validation: {'Passed' if valid else 'Failed'}")
        
        # Get connection info
        info = client.get_connection_info()
        print(f"Server: {info['server_url']}")
        print(f"Base DN: {info['base_dn']}")
        
        await client.disconnect()
        
    except Exception as e:
        print(f"❌ LDAP connection failed: {e}")
        return False
    
    return True


async def test_user_lookup(email: str):
    """Test looking up a user by email."""
    print(f"\n=== Looking up user: {email} ===")
    
    client = RedHatLDAPClient()
    
    try:
        await client.connect()
        
        # Search by email
        user = await client.search_user_by_email(email)
        
        if user:
            print(f"✅ Found user:")
            print(f"  UID: {user.uid}")
            print(f"  Name: {user.display_name}")
            print(f"  Email: {user.email}")
            print(f"  Title: {user.title}")
            print(f"  Department: {user.department}")
        else:
            print(f"❌ User not found")
        
        await client.disconnect()
        return user
        
    except Exception as e:
        print(f"❌ User lookup failed: {e}")
        return None


async def test_organizational_hierarchy(manager_email: str):
    """Test fetching organizational hierarchy."""
    print(f"\n=== Fetching organizational hierarchy for: {manager_email} ===")
    
    client = RedHatLDAPClient()
    
    try:
        await client.connect()
        
        # Get hierarchy
        hierarchy = await client.get_organizational_hierarchy(manager_email, max_depth=2)
        
        # Print hierarchy
        def print_hierarchy(node, level=0):
            indent = "  " * level
            print(f"{indent}👤 {node['display_name']} ({node['uid']})")
            if node.get('title'):
                print(f"{indent}   📋 {node['title']}")
            if node.get('direct_reports'):
                print(f"{indent}   👥 {len(node['direct_reports'])} direct reports")
                for report in node['direct_reports']:
                    print_hierarchy(report, level + 1)
        
        print_hierarchy(hierarchy)
        
        # Extract all emails
        emails = await client.extract_emails_from_hierarchy(hierarchy)
        print(f"\n📧 Total emails in hierarchy: {len(emails)}")
        
        # Map to Jira usernames
        username_map = await client.map_emails_to_jira_usernames(emails)
        print(f"🔗 Mapped to {len(username_map)} Jira usernames")
        
        await client.disconnect()
        return hierarchy
        
    except Exception as e:
        print(f"❌ Hierarchy fetch failed: {e}")
        return None


async def test_jira_ldap_integration(manager_email: str):
    """Test full Jira-LDAP integration."""
    print(f"\n=== Testing Jira-LDAP Integration for: {manager_email} ===")
    
    # Create config manager
    config_manager = ConfigManager()
    
    # Enable LDAP in config
    config_manager.update_ldap_config(
        enabled=True,
        server_url="ldaps://ldap.corp.redhat.com",
        base_dn="ou=users,dc=redhat,dc=com",
        max_hierarchy_depth=2,
        cache_ttl_minutes=60
    )
    
    # Create integration
    integration = RedHatJiraLDAPIntegration(config_manager)
    
    try:
        await integration.initialize()
        print("✅ Integration initialized successfully")
        
        # Set date range (last 7 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        # Get team activities
        print(f"\n📊 Fetching activities from {start_date.date()} to {end_date.date()}")
        
        activities, hierarchy = await integration.get_manager_team_activities(
            manager_identifier=manager_email,
            start_date=start_date,
            end_date=end_date,
            max_results=100
        )
        
        print(f"\n✅ Found {len(activities)} activities")
        
        # Print summary by user
        user_activities = {}
        for activity in activities:
            user = activity.get('assignee', 'Unassigned')
            if user not in user_activities:
                user_activities[user] = []
            user_activities[user].append(activity)
        
        print("\n📋 Activities by user:")
        for user, user_acts in sorted(user_activities.items()):
            print(f"  👤 {user}: {len(user_acts)} activities")
        
        await integration.close()
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")


async def test_workflow_with_ldap(manager_email: str):
    """Test complete workflow with LDAP integration."""
    print(f"\n=== Testing Complete Workflow with LDAP ===")
    
    # Create config manager
    config_manager = ConfigManager()
    
    # Enable LDAP
    config_manager.update_ldap_config(enabled=True)
    
    # Create orchestrator
    orchestrator = WorkflowOrchestrator(config_manager)
    
    try:
        # Set date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        # Execute workflow for manager's team
        result = await orchestrator.execute_manager_team_workflow(
            manager_identifier=manager_email,
            start_date=start_date,
            end_date=end_date,
            custom_prompt="Focus on key achievements and blockers"
        )
        
        print(f"\n✅ Workflow completed: {result.status.value}")
        print(f"📊 Activities processed: {result.activity_count}")
        print(f"⏱️ Execution time: {result.execution_time:.2f}s")
        
        if result.summary_content:
            print("\n📝 Summary preview:")
            print(result.summary_content[:500] + "...")
        
    except Exception as e:
        print(f"❌ Workflow failed: {e}")


async def main():
    """Main function to run examples."""
    print("Red Hat LDAP Integration Examples")
    print("=" * 50)
    
    # Example manager email (replace with actual email)
    manager_email = "manager@redhat.com"
    
    # Run tests
    if await test_ldap_connection():
        await test_user_lookup(manager_email)
        await test_organizational_hierarchy(manager_email)
        await test_jira_ldap_integration(manager_email)
        
        # Uncomment to test full workflow (requires valid Jira and Gemini credentials)
        # await test_workflow_with_ldap(manager_email)


if __name__ == "__main__":
    # Note: Replace manager@redhat.com with an actual Red Hat manager email
    print("\n⚠️  Note: This example requires:")
    print("1. Access to Red Hat's LDAP server (ldaps://ldap.corp.redhat.com)")
    print("2. Valid Red Hat Jira credentials configured")
    print("3. A valid manager email address to query")
    print("\nUpdate the manager_email variable with a real email address to test.\n")
    
    asyncio.run(main())