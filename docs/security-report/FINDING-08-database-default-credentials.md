# FINDING-08: PostgreSQL Uses Default Weak Credentials

## Severity: MEDIUM

**CVSS 3.1 Estimate:** 5.7 (AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N)

## Status: CONFIRMED

## Location

- `extraction-service/docker-compose.yml`, lines 11-15
- `extraction-service/app/config.py`, lines 99-100

## Description

PostgreSQL is deployed with the username `kb` and password `kb` -- a trivially guessable single-character-repeated credential. While the database port is not exposed to the host by default (no `ports:` directive in docker-compose), any service on the Docker network can connect. The password is also hardcoded in the application's default `DATABASE_URL`.

## Proof / Reasoning

**docker-compose.yml (lines 11-15):**
```yaml
db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=kb
      - POSTGRES_PASSWORD=kb
      - POSTGRES_DB=kb
```

**config.py (lines 99-100) -- default DATABASE_URL:**
```python
database_url: str = field(default_factory=lambda: os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://kb:kb@db:5432/kb"))
```

**Also documented in the .env.example (line 60):**
```
# DATABASE_URL=postgresql+psycopg2://kb:kb@localhost:5432/kb
```

The database contains: user accounts (with bcrypt-hashed passwords), all uploaded PDFs (as binary blobs), extracted knowledge graphs, chat histories, billing/Stripe data, refresh tokens, and activation events.

## Impact

- Any container on the Docker network (or any host with network access to port 5432) can connect with `kb:kb`.
- Full read access to all application data: user records, documents, graphs, chat messages.
- Write access allows data tampering, privilege escalation (update `users.role` directly), or data destruction.

## Exploit Scenario

1. Attacker compromises any container on the same Docker network.
2. `psql -h db -U kb -d kb` connects with the password `kb`.
3. `UPDATE users SET role='admin' WHERE email='attacker@example.com';` -- instant admin access.
4. `SELECT data FROM document_files;` -- exfiltrate all uploaded documents.

## Remediation

1. **Use a strong, randomly generated password** for PostgreSQL. Generate with `openssl rand -base64 32`.
2. Pass the password through Docker secrets or environment variables from a secrets manager, not hardcoded in docker-compose.yml.
3. Consider adding `pg_hba.conf` rules to restrict connections to known application hosts.
4. Enable SSL/TLS for PostgreSQL connections within the Docker network.
