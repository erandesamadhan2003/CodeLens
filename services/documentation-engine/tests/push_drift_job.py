import asyncio
from bullmq import Queue

PAYLOAD = {
    "repoUrl": "https://github.com/expressjs/express",
    "scanId": "aaaa1111-1111-1111-1111-111111111111",
    "triggeredBy": "webhook",
    "commitSha": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    "repoFullName": "expressjs/express",
    "githubToken": "invalid_token_for_check_run_test",
    "changedFiles": ["src/pricing.ts", "routes/users.js"],
    "diffs": [
        {
            "filename": "src/pricing.ts",
            "status": "modified",
            "patch": "@@ -0,0 +1,3 @@\n+export function calculateDiscount() {\n+  return 1;\n+}\n",
        },
        {
            "filename": "routes/users.js",
            "status": "modified",
            "patch": '@@ -1 +1 @@\n+router.get("/users", handler);\n',
        },
    ],
}

CLEAN_PAYLOAD = {
    "repoUrl": "https://github.com/expressjs/express",
    "scanId": "bbbb1111-1111-1111-1111-111111111111",
    "triggeredBy": "webhook",
    "commitSha": "cafebabecafebabecafebabecafebabecafebabe",
    "repoFullName": "expressjs/express",
    "githubToken": "invalid_token",
    "changedFiles": ["README.md"],
    "diffs": [
        {
            "filename": "README.md",
            "status": "modified",
            "patch": "@@ -1 +1 @@\n-typo\n+fixed typo\n",
        },
    ],
}

async def main():
    q = Queue("documentation-engine", {"connection": {"host": "redis", "port": 6379}})
    await q.add("manual-integration-test", {
        "repoUrl": "https://github.com/expressjs/express",
        "scanId": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        "triggeredBy": "manual",
    })
    await q.add("drift-webhook-test", PAYLOAD)
    await q.add("clean-webhook-test", CLEAN_PAYLOAD)
    print("enqueued manual + drift + clean tests")
    await q.close()

if __name__ == "__main__":
    asyncio.run(main())
