# FINDING-04: Cross-Tenant Privilege Escalation in Admin User Management

## Severity: HIGH

**CVSS 3.1 Estimate:** 7.6 (AV:N/AC:L/PR:H/UI:N/S:C/C:H/I:H/A:N)

## Status: CONFIRMED

## Location

- `extraction-service/app/admin_routes.py`, lines 33-34 (`list_users`), lines 54-72 (`update_user`)

## Description

The admin user management endpoints (`GET /admin/users` and `PATCH /admin/users/{user_id}`) lack tenant isolation. An admin of Organization A can list ALL users across ALL organizations and modify any user's role, password, or active status regardless of their organization. This breaks the multi-tenant isolation model.

## Proof / Reasoning

**`list_users` (line 33-34) -- no org_id filter:**
```python
@router.get("/users")
def list_users(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return [u.public() for u in db.scalars(select(User).order_by(User.created_at)).all()]
```

This queries ALL users in the database with no `WHERE org_id = admin.org_id` filter.

**`update_user` (lines 54-72) -- no org_id check:**
```python
@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UpdateUserIn,
                admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "user not found")
    # No check: user.org_id == admin.org_id
    if body.role is not None:
        ...
        user.role = body.role
    if body.password:
        user.password_hash = hash_password(body.password)
    ...
```

**Contrast with `admin_set_user_models` in api.py (lines 394-395) which DOES check:**
```python
target = db.get(User, user_id)
if not target or target.org_id != admin.org_id:
    raise HTTPException(404, "user not found in this organization")
```

The model-assignment endpoint correctly enforces tenant isolation, proving the pattern is known but was missed in the core user management routes.

## Impact

- **Cross-tenant data breach:** Admin A can set Admin B's users' roles to `admin`, then use those accounts to access Org B's documents, billing, and configuration.
- **Account takeover across tenants:** Admin A can change the password of any user in Org B.
- **Privilege escalation:** Admin A can promote any user (even across orgs) to admin or demote them.
- **Denial of service:** Admin A can deactivate users in Org B.

## Exploit Scenario

1. Attacker creates or obtains an admin account in their own organization.
2. Attacker calls `GET /admin/users` to enumerate ALL users across ALL orgs, including other tenants' users and their IDs.
3. Attacker calls `PATCH /admin/users/{target_user_id}` with `{"password": "hacked123"}` to change a target user's password in another org.
4. Attacker logs in as the target user and accesses all of that org's data.

## Remediation

1. **Add org_id filtering to `list_users`:**
   ```python
   return [u.public() for u in db.scalars(
       select(User).where(User.org_id == admin.org_id).order_by(User.created_at)).all()]
   ```

2. **Add org_id check to `update_user`:**
   ```python
   user = db.get(User, user_id)
   if not user or user.org_id != admin.org_id:
       raise HTTPException(404, "user not found")
   ```

3. Apply the same pattern (already used in `admin_set_user_models`) consistently to all admin endpoints that operate on users.
