import asyncio
import uuid
from bullmq import Queue

async def push(payload):
    q = Queue('documentation-engine', {'connection': {'host': 'redis', 'port': 6379}})
    job = await q.add('integration', payload)
    jid = job.id
    await q.close()
    return jid

async def main():
    jobs = []
    jobs.append(await push({'repoUrl': 'https://github.com/expressjs/express', 'scanId': 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'triggeredBy': 'phase7'}))
    jobs.append(await push({'repoUrl': 'https://github.com/expressjs/express', 'scanId': 'ffffffff-ffff-ffff-ffff-ffffffffffff', 'triggeredBy': 'phase8-orphan'}))
    jobs.append(await push({'repoUrl': 'not-a-valid-url', 'scanId': '11111111-1111-1111-1111-111111111111', 'triggeredBy': 'phase8-bad-url'}))
    jobs.append(await push({'repoUrl': 'https://github.com/octocat/Hello-World', 'scanId': '22222222-2222-2222-2222-222222222222', 'triggeredBy': 'phase8-readme-only'}))
    # concurrent
    jobs.append(await push({'repoUrl': 'https://github.com/lodash/lodash', 'scanId': '33333333-3333-3333-3333-333333333333', 'triggeredBy': 'phase8-concurrent'}))
    jobs.append(await push({'repoUrl': 'https://github.com/chalk/chalk', 'scanId': '44444444-4444-4444-4444-444444444444', 'triggeredBy': 'phase8-concurrent'}))
    jobs.append(await push({'repoUrl': 'https://github.com/sindresorhus/is', 'scanId': '55555555-5555-5555-5555-555555555555', 'triggeredBy': 'phase8-concurrent'}))
    # recovery job after orphan test
    jobs.append(await push({'repoUrl': 'https://github.com/expressjs/express', 'scanId': '66666666-6666-6666-6666-666666666666', 'triggeredBy': 'phase8-recovery'}))
    print('enqueued', jobs)

asyncio.run(main())
