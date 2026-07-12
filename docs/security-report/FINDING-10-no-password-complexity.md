# FINDING-10: No Password Complexity Requirements

## Severity: MEDIUM

**CVSS 3.1 Estimate:** 5.1 (AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N)

## Status: CONFIRMED

## Location

- `extraction-service/app/admin_routes.py`, lines 38-51 (`create_user`)
- `extraction-service/app/admin_routes.py`, lines 54-72 (`update_user`)

## Description

The user creation and password update endpoints accept any string as a password with no minimum length, complexity, or entropy requirements. Passwords as short as a single character are accepted. Combined with the lack of login rate limiting (FINDING-06), weak passwords are trivially brute-forced.

## Proof / Reasoning

**create_user (admin_routes.py, lines 38-51):**
```python
class CreateUserIn(BaseModel):
    email: str
    password: str  # No min-length, no complexity validation
    name: str = ""
    role: str = "analyst"

@router.post("/users")
def create_user(body: CreateUserIn, ...):
    ...
    user = User(..., password_hash=hash_password(body.password), ...)
```

**update_user (admin_routes.py, lines 69-70):**
```python
if body.password:
    user.password_hash = hash_password(body.password)
```

No validation is applied to `body.password` before hashing. A password of `"a"` or `""` (if body.password is truthy) is accepted.

## Impact

- Admins can create user accounts with trivially weak passwords.
- Users whose passwords are reset by admins may receive weak passwords.
- Combined with FINDING-06 (no rate limiting), short/weak passwords can be brute-forced in seconds.

## Remediation

1. **Enforce minimum password requirements** in a shared validation function:
   ```python
   def validate_password(password: str) -> None:
       if len(password) < 12:
           raise HTTPException(400, "password must be at least 12 characters")
       if password.lower() in COMMON_PASSWORDS:
           raise HTTPException(400, "password is too common")
   ```

2. Apply the validation in both `create_user` and `update_user`.

3. Consider checking against a list of common/breached passwords (e.g., the Have I Been Pwned password list).
