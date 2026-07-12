# FINDING-03: Default Admin Credentials Are Weak and Predictable

## Severity: HIGH

**CVSS 3.1 Estimate:** 8.1 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N)

## Status: CONFIRMED

## Location

- `extraction-service/app/config.py`, lines 142-143
- `extraction-service/.env`, lines 35-36
- `extraction-service/app/api.py`, lines 81-90 (bootstrap function)

## Description

The application seeds an administrator account on first startup using credentials from environment variables, with hardcoded defaults of `admin@knowledgebook.local` / `admin12345`. These credentials are trivially guessable and documented in both the `.env` and `.env.example` files. Any fresh deployment that does not override these values starts with a fully privileged admin account protected by a weak password.

## Proof / Reasoning

**config.py defaults (lines 142-143):**
```python
admin_email: str = field(default_factory=lambda: os.environ.get("ADMIN_EMAIL", "admin@knowledgebook.local"))
admin_password: str = field(default_factory=lambda: os.environ.get("ADMIN_PASSWORD", "admin12345"))
```

**Bootstrap function in api.py (lines 81-90):**
```python
def _bootstrap_admin(org_id: str) -> None:
    """Seed the first admin from env vars iff the users table is empty."""
    cfg = get_settings()
    with session_scope() as db:
        if db.scalar(select(User).limit(1)) is not None:
            return
        db.add(User(org_id=org_id, email=cfg.admin_email,
                    password_hash=hash_password(cfg.admin_password),
                    name="Administrator", role="admin"))
```

**The active .env file (lines 35-36):**
```
ADMIN_EMAIL=admin@knowledgebook.local
ADMIN_PASSWORD=admin12345
```

## Impact

- An attacker can log in as admin on any fresh or default deployment.
- Admin access grants: user management (create/modify/delete accounts), access to all documents across all users, cost dashboards, model configuration, category management, and billing operations.
- Combined with FINDING-02 (known JWT secret), even if the admin password is changed after bootstrap, the attacker can still forge admin tokens.

## Exploit Scenario

1. Attacker discovers a KnowledgeBook deployment (e.g., exposed API on port 8000).
2. Attacker sends `POST /auth/login` with `{"email": "admin@knowledgebook.local", "password": "admin12345"}`.
3. Receives a valid admin access token.
4. Uses admin API to list all users, access all documents, modify user accounts.

## Remediation

1. **Force password change** on first login for the bootstrapped admin account.
2. **Require** `ADMIN_PASSWORD` to be explicitly set and meet complexity requirements -- refuse to bootstrap with the default.
3. Add a startup warning (or hard failure) if the admin password matches known defaults.
4. Consider an interactive setup flow or a one-time setup token instead of environment-variable seeding.
