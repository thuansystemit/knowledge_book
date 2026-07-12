# FINDING-07: Redis Deployed Without Authentication

## Severity: MEDIUM

**CVSS 3.1 Estimate:** 6.2 (AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:L/A:N)

## Status: CONFIRMED

## Location

- `extraction-service/docker-compose.yml`, lines 26-35
- `extraction-service/app/config.py`, lines 102-103
- `extraction-service/app/redis_client.py`

## Description

Redis is deployed without any authentication (no `requirepass`). The Redis URL in the configuration does not include a password. Redis stores sensitive operational data including Celery job queues, SSE event streams, chunk extraction cache, and rate-limit counters. Any host with network access to the Redis port can read, write, or flush all data.

## Proof / Reasoning

**docker-compose.yml (lines 26-35) -- no password set:**
```yaml
redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    # No --requirepass
    volumes:
      - kb_redisdata:/data
```

**config.py (lines 102-103) -- no password in URL:**
```python
redis_url: str = field(default_factory=lambda: os.environ.get(
    "REDIS_URL", "redis://redis:6379/0"))
```

**redis_client.py -- connects without credentials:**
```python
def get_redis() -> "redis.Redis":
    cfg = get_settings()
    return redis.Redis.from_url(cfg.redis_url, decode_responses=True)
```

## Impact

- **Data leakage:** An attacker on the same network can read cached chunk extractions (document content), job event history, and rate-limit state.
- **Cache poisoning:** An attacker can write malicious data to the chunk cache (`chunkcache:*` keys), which would be served to users as extracted knowledge.
- **Job manipulation:** An attacker can inject or modify Celery tasks in the broker queue.
- **Rate limit bypass:** An attacker can delete rate-limit keys to bypass upload/chat throttling.
- **Denial of service:** `FLUSHALL` wipes the cache, all job events, and rate-limit state.

## Exploit Scenario

1. Attacker gains access to the Docker network (e.g., compromised container, adjacent service, or exposed port).
2. `redis-cli -h redis -p 6379` connects without authentication.
3. `KEYS chunkcache:*` lists all cached extraction results.
4. `GET chunkcache:<key>` reads extracted document content.
5. `SET chunkcache:<key> '{"nodes":[{"name":"HACKED",...}]}'` poisons the cache.

## Remediation

1. **Set a Redis password:**
   ```yaml
   redis:
     command: ["redis-server", "--appendonly", "yes", "--requirepass", "${REDIS_PASSWORD}"]
   ```
2. Update `REDIS_URL` to include the password: `redis://:${REDIS_PASSWORD}@redis:6379/0`.
3. Consider enabling Redis TLS for in-transit encryption if the network is not fully trusted.
4. Restrict network access to Redis using Docker network policies.
