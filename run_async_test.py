#!/usr/bin/env python3
"""Run only the async mode drama creation test"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from tests.test_drama_create import TestDramaCreate

def main():
    """Run async mode test only"""
    print("=" * 70)
    print("POST /dramas Async Mode Test - Single Character")
    print("=" * 70 + "\n")

    tester = TestDramaCreate()

    try:
        # Health check
        tester.test_health()

        # Run async mode test only
        print("-" * 70)
        drama_id, drama = tester.test_create_drama_from_premise_single_character()
        print("-" * 70 + "\n")

        print("=" * 70)
        print(f"✅ Async test passed!")
        print(f"Generated Drama ID: {drama_id}")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
