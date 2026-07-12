# FINDING-06: No Rate Limiting on Authentication Endpoints

## Severity: MEDIUM

**CVSS 3.1 Estimate:** 6.5 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N)

## Status: CONFIRMED

## Location

- `extraction-service/app/auth_routes.py`, lines 51-57 (`/auth/login`)
- `extraction-service/app/auth_routes.py`, lines 60-79 (`/auth/refresh`)
- `extraction-service/app/ratelimit.py` (defines `upload_limit` and `chat_limit` only)

## Description

The authentication endpoints (`POST /auth/login` and `POST /auth/refresh`) have no rate limiting applied. The application's rate-limiting module only covers upload and chat endpoints. An attacker can attempt unlimited login attempts to brute-force user credentials, or flood the refresh endpoint to perform a denial-of-service.

## Proof / Reasoning

**Login endpoint has no rate limit dependency (auth_routes.py, line 51-57):**
```python
@router.post("/login")
def login(body: LoginIn, resp: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "invalid credentials")
    ...
```

**Compare with upload endpoint (api.py, line 93-98) which has rate limiting:**
```python
@app.post("/api/jobs")
async def create_job(file: UploadFile,
                     ...
                     _rl: None = Depends(upload_limit),  # rate limited
                     ...):
```

**The rate limit module (ratelimit.py) defines only two buckets:**
```python
def upload_limit(user: User = Depends(get_current_user)) -> None: ...
def chat_limit(user: User = Depends(get_current_user)) -> None: ...
```

No `login_limit` function exists.

## Impact

- **Credential brute-forcing:** An attacker can make thousands of login attempts per second against known email addresses (especially `admin@knowledgebook.local`).
- **Credential stuffing:** Automated testing of leaked credential databases.
- **Combined with FINDING-03:** The default admin email is known; the default password is 9 characters. Without rate limiting, a dictionary attack will find it in seconds.

## Exploit Scenario

```bash
# Brute-force the admin account (conceptual)
for pass in $(cat /usr/share/wordlists/rockyou.txt); do
  curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://target:8000/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"admin@knowledgebook.local\",\"password\":\"$pass\"}"
done
# No rate limit -- attacker can try thousands per second
```

## Remediation

1. **Add a login rate limiter** -- rate limit by IP (not user, since the user is not authenticated yet):
   ```python
   def login_limit(request: Request):
       ip = request.client.host
       _check(ip, "login", 10, 300)  # 10 attempts per 5 minutes per IP
   ```

2. **Add account lockout** after N failed attempts (e.g., 5 failures -> 15-minute lockout on the account).

3. **Add exponential backoff** on repeated failed logins for the same email.

4. Consider CAPTCHA or proof-of-work challenges after 3+ failed attempts.
