# FINDING-02: Weak/Predictable JWT Secret Enables Token Forgery

## Severity: HIGH

**CVSS 3.1 Estimate:** 8.6 (AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:N)

## Status: CONFIRMED

## Location

- `extraction-service/app/config.py`, line 134
- `extraction-service/.env`, line 29

## Description

The JWT secret used to sign all authentication tokens (access, refresh, and stream tokens) has a predictable default value of `"dev-secret-change-me"` hardcoded in the application source code. The active `.env` file also uses the same weak value. Anyone who knows this secret can forge valid JWT tokens for any user, including administrators.

## Proof / Reasoning

**In config.py (line 134), the hardcoded default:**
```python
jwt_secret: str = field(default_factory=lambda: os.environ.get("JWT_SECRET", "dev-secret-change-me"))
```

**In the active .env (line 29):**
```
JWT_SECRET=dev-secret-change-me
```

**The secret is used for all token operations in security.py:**
```python
# security.py, line 35
return jwt.encode(payload, cfg.jwt_secret, algorithm=_ALG)

# security.py, line 41
return jwt.decode(token, cfg.jwt_secret, algorithms=[_ALG])
```

Three token types are signed with this secret:
- `access` tokens (line 44-47): carry user_id and role, used for API authentication
- `refresh` tokens (line 50-53): long-lived, stored in HttpOnly cookies
- `stream` tokens (line 56-59): used for SSE event streams

## Impact

- **Full authentication bypass:** An attacker can forge a valid access token with `{"sub": "<any_user_id>", "role": "admin", "type": "access"}` and gain admin access to the entire system.
- **Account takeover:** Forge tokens for any user without knowing their password.
- **Data exfiltration:** Access all documents, graphs, chat histories, and uploaded PDFs across all users and organizations.
- **Admin privilege escalation:** Create/modify/delete users, change billing, access all admin endpoints.

## Exploit Scenario

```python
# PoC: forge an admin token (conceptual)
from jose import jwt
from datetime import datetime, timedelta, timezone

secret = "dev-secret-change-me"  # known from source code
now = datetime.now(timezone.utc)
token = jwt.encode({
    "sub": "any-user-id-or-guess",
    "role": "admin",
    "type": "access",
    "iat": now,
    "exp": now + timedelta(hours=1)
}, secret, algorithm="HS256")

# Use this token: Authorization: Bearer <token>
# Now has full admin access to all API endpoints
```

## Remediation

1. **Generate a cryptographically strong secret** of at least 256 bits: `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
2. **Remove the hardcoded default** from `config.py` -- fail loudly on startup if `JWT_SECRET` is not set or is too short.
3. **Rotate the secret** in all environments immediately. All existing sessions will be invalidated (users must re-login).
4. Add a startup check that rejects known-weak secrets like `"dev-secret-change-me"`, `"change-me"`, `"secret"`, etc.
