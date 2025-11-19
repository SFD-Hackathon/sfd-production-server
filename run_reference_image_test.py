#!/usr/bin/env python3
"""
Quick runner for the reference image test.
Tests creating a drama from premise with cartoon_boy_character.jpg as reference.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the test module
from tests.test_generation import APIClient, BASE_URL, test_create_drama_from_premise_with_image, test_health_check

def main():
    """Run the reference image test"""
    print("=" * 70)
    print("Drama Creation with Reference Image Test")
    print("=" * 70 + "\n")

    # Create API client
    client = APIClient(base_url=BASE_URL)

    try:
        # Health check first
        test_health_check(client)

        # Run the reference image test
        test_create_drama_from_premise_with_image(client)

        print("\n" + "=" * 70)
        print("✅ All tests passed!")
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
