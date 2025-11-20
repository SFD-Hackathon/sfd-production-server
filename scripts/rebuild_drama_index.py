#!/usr/bin/env python
"""
Rebuild drama index in R2 storage

This script scans all existing dramas in R2 and rebuilds the index.json file.
Run this once to migrate from the old scanning-based list_dramas to the new index-based approach.

Usage:
    python scripts/rebuild_drama_index.py
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage import storage


async def main():
    """Rebuild the drama index"""
    print("="*60)
    print("Drama Index Rebuild Utility")
    print("="*60)
    print()

    try:
        stats = await storage.rebuild_index()

        print()
        print("="*60)
        print("REBUILD COMPLETE")
        print("="*60)
        print(f"Total dramas scanned: {stats['total_scanned']}")
        print(f"Total dramas indexed: {stats['total_indexed']}")
        print(f"Total errors: {stats['total_errors']}")
        print()

        if stats['total_errors'] > 0:
            print("⚠️  Some dramas had errors. Check the logs above.")
            sys.exit(1)
        else:
            print("✅ All dramas successfully indexed!")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
