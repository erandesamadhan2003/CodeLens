import asyncio
import os
import main

async def run():
    main.DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/codelens")
    await main.init_pool()

    # first call — should be a cache miss, hits OSV, writes to cache
    print("Testing first call...")
    result1 = await main.lookup_vulnerabilities([("lodash", "4.17.11", "npm")])
    source1 = result1.get("lodash@4.17.11", {}).get("source")
    print("First call (OSV):", source1)
    assert source1 == "osv", f"Expected 'osv', got {source1}"

    # second call — should be a cache hit, no OSV call
    print("Testing second call...")
    result2 = await main.lookup_vulnerabilities([("lodash", "4.17.11", "npm")])
    source2 = result2.get("lodash@4.17.11", {}).get("source")
    print("Second call (cache):", source2)
    assert source2 == "cache", f"Expected 'cache', got {source2}"

    await main.close_pool()
    print("Cache integration test passed!")

if __name__ == "__main__":
    asyncio.run(run())
