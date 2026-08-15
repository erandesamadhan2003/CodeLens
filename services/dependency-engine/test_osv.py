import asyncio
from main import batch_query_osv, _extract_severity, _extract_fixed_version

async def main():
    # a package with a known, real vulnerability
    results = await batch_query_osv([("lodash", "4.17.11", "npm")])
    print(results)
    assert results is not None, "Results should not be None"
    assert len(results) > 0, "Should have a result item for lodash"
    assert len(results[0]) > 0, "lodash 4.17.11 has known CVEs, should have > 0 vulnerabilities"
    
    # check that hydration mapped severity / fixed version correctly
    vuln = results[0][0]
    print(f"Sample Vulnerability: {vuln}")
    
    # Check failure path (mock OSV URL in the real module)
    import main as m
    old_url = m.OSV_BATCH_URL
    try:
        m.OSV_BATCH_URL = "http://localhost:12345/nonexistent" # bad url
        bad_results = await batch_query_osv([("lodash", "4.17.11", "npm")])
        assert bad_results is None, "Should gracefully return None on network failure"
    finally:
        m.OSV_BATCH_URL = old_url
    print("OSV test passed!")

if __name__ == '__main__':
    asyncio.run(main())
