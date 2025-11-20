"""
Pytest configuration and fixtures for all tests.
"""

import os
import sys
from pathlib import Path
import pytest
from dotenv import load_dotenv

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file (override any existing vars)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"✓ Loaded environment from {env_path} (with override)")
else:
    print("⚠️ Warning: .env file not found")

# Verify critical environment variables are set
required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
    print("   Please ensure .env file contains these variables.")
else:
    print(f"✓ All required environment variables are set")


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment before running tests."""
    print("\n" + "=" * 60)
    print("STARTING TEST SUITE")
    print("=" * 60)
    print(f"SUPABASE_URL: {os.getenv('SUPABASE_URL')}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print("=" * 60 + "\n")

    yield

    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60 + "\n")


@pytest.fixture(scope="function")
def reset_supabase_client():
    """Reset Supabase client between tests."""
    from app.dal.supabase_client import SupabaseClient

    # Close existing client if any
    try:
        SupabaseClient.close()
    except:
        pass

    yield

    # Cleanup after test
    try:
        SupabaseClient.close()
    except:
        pass
