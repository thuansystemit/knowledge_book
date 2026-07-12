# KnowledgeBook Security Assessment Report

**Date:** 2026-07-07
**Assessor:** Automated security research (grey-hat methodology)
**Target:** `knowledge_book` repository, branch `master`, commit `f69f161`
**Scope:** Full codebase -- backend (FastAPI/Python), frontend (React/TypeScript), infrastructure (Docker Compose), and operational scripts.

---

## Executive Summary

This assessment identified **14 findings** across the KnowledgeBook extraction and knowledge-graph platform. The application is a multi-tenant SaaS with user authentication, file upload/processing, LLM-powered extraction, chat, Stripe billing, and an admin dashboard.

The most critical findings involve **hardcoded secrets** (a live API key on disk and a predictable JWT signing secret), which together allow complete authentication bypass and unauthorized API usage. A **cross-tenant privilege escalation** in the admin routes breaks multi-tenant isolation. A **stored XSS vector** through unvalidated Content-Type on file uploads could allow session hijacking.

The codebase demonstrates solid security practices in several areas -- bcrypt password hashing, HttpOnly refresh cookies, RBAC with category-scoped ACLs, Stripe webhook signature verification, and token rotation. The issues found are primarily configuration/deployment hardening gaps and a few missing input validation checks.

---

## Methodology

1. **Architecture reconnaissance:** Mapped all source files, frameworks, entry points, auth flows, data stores, and external integrations.
2. **Static analysis:** Read all backend Python modules, frontend TypeScript, Docker/infrastructure configs, and shell scripts.
3. **Threat modeling:** Identified attack surfaces: authentication, authorization (RBAC + multi-tenancy), file upload/serving, LLM prompt pipeline, database access, Redis, CORS, SSE streams, Stripe webhooks, and operational scripts.
4. **Vulnerability hunting:** Traced data flows from user input to storage/execution, checked for injection points, authorization gaps, secret exposure, and insecure defaults.
5. **Verification:** Each finding includes the exact file and line number with quoted code. No fabricated findings.

---

## Findings Summary

| ID | Title | Severity | Location | Status |
|----|-------|----------|----------|--------|
| [01](FINDING-01-hardcoded-api-key.md) | Live API Key Hardcoded in .env File | **CRITICAL** | `extraction-service/.env:39-41` | CONFIRMED |
| [02](FINDING-02-weak-jwt-secret.md) | Weak/Predictable JWT Secret Enables Token Forgery | **HIGH** | `app/config.py:134`, `.env:29` | CONFIRMED |
| [03](FINDING-03-default-admin-credentials.md) | Default Admin Credentials Are Weak and Predictable | **HIGH** | `app/config.py:142-143`, `.env:35-36` | CONFIRMED |
| [04](FINDING-04-cross-tenant-admin-escalation.md) | Cross-Tenant Privilege Escalation in Admin Routes | **HIGH** | `app/admin_routes.py:33-34,54-72` | CONFIRMED |
| [05](FINDING-05-stored-xss-content-type.md) | Stored XSS via Unvalidated Content-Type on File Upload | **HIGH** | `app/api.py:133-134,195-202` | CONFIRMED |
| [06](FINDING-06-no-login-rate-limit.md) | No Rate Limiting on Authentication Endpoints | **MEDIUM** | `app/auth_routes.py:51-57` | CONFIRMED |
| [07](FINDING-07-redis-no-auth.md) | Redis Deployed Without Authentication | **MEDIUM** | `docker-compose.yml:26-35` | CONFIRMED |
| [08](FINDING-08-database-default-credentials.md) | PostgreSQL Uses Default Weak Credentials | **MEDIUM** | `docker-compose.yml:11-15` | CONFIRMED |
| [09](FINDING-09-content-disposition-injection.md) | Content-Disposition Header Injection via Filename | **MEDIUM** | `app/api.py:202` | CONFIRMED |
| [10](FINDING-10-no-password-complexity.md) | No Password Complexity Requirements | **MEDIUM** | `app/admin_routes.py:38-51,69-70` | CONFIRMED |
| [11](FINDING-11-llm-prompt-injection.md) | LLM Prompt Injection via Malicious Document Content | **LOW** | `app/pipeline.py:214-218` | PLAUSIBLE |
| [12](FINDING-12-error-message-leakage.md) | Error Messages Leak Internal Implementation Details | **LOW** | `app/chat_routes.py:166-169` | CONFIRMED |
| [13](FINDING-13-unencrypted-db-dumps.md) | Database Dumps Without Encryption | **LOW** | `scripts/db-dump.sh` | CONFIRMED |
| [14](FINDING-14-cors-dev-only.md) | CORS Configuration Limited to Dev Origins | **INFO** | `app/api.py:52-58` | CONFIRMED |

### By Severity

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 4 |
| MEDIUM | 5 |
| LOW | 3 |
| INFO | 1 |
| **Total** | **14** |

---

## Vulnerability Chains

### Chain 1: Default Credentials + JWT Secret = Instant Full Compromise
**FINDING-02 + FINDING-03 -> CRITICAL**

A fresh deployment starts with the admin password `admin12345` and JWT secret `dev-secret-change-me`. An attacker can either:
- Log in directly with the default admin credentials, OR
- Forge a valid admin JWT token using the known secret (no login needed).

Either path gives full admin access: all user data, all documents, billing, user management.

### Chain 2: Upload XSS + Cross-Tenant Admin = Multi-Org Breach
**FINDING-05 + FINDING-04 -> CRITICAL**

1. Analyst uploads malicious HTML (stored XSS via Content-Type).
2. Admin views the document, triggering JS execution.
3. XSS steals admin session, calls `GET /admin/users` to list ALL users across ALL orgs.
4. Changes passwords of users in other organizations.
5. Full multi-tenant compromise.

### Chain 3: No Login Rate Limit + Weak Passwords = Credential Stuffing
**FINDING-06 + FINDING-10 + FINDING-03 -> HIGH**

Without rate limiting on `/auth/login` and no password complexity enforcement, an attacker can brute-force any account. The default admin password (`admin12345`) falls to a dictionary attack in seconds.

---

## Positive Security Observations

- **Password hashing:** bcrypt via passlib (OWASP-recommended).
- **Token architecture:** Access tokens in memory only (not localStorage), refresh tokens in HttpOnly cookies with rotation and revocation.
- **RBAC:** Role-based access control (admin/analyst/viewer) with category-scoped ACLs (view/upload/manage).
- **Stripe webhook verification:** Webhook signature is validated before processing billing events.
- **Rate limiting infrastructure:** Redis-backed, fail-open rate limiting exists (just needs to cover auth endpoints).
- **Input validation:** File size limits, page limits, plan quotas, and cost caps are enforced.
- **SameSite cookies:** Refresh cookie uses `samesite=lax` by default.
- **Gitignore:** `.env` files are correctly excluded from version control.

---

## Priority Remediation Roadmap

### Immediate (this week)
1. **Rotate the NVIDIA API key** (FINDING-01).
2. **Generate and deploy a strong JWT secret** (FINDING-02).
3. **Change the admin password** and add startup validation rejecting defaults (FINDING-03).

### Short-term (next sprint)
4. **Add org_id filtering** to `list_users` and `update_user` (FINDING-04).
5. **Validate Content-Type** on upload; serve files with safe media types (FINDING-05).
6. **Add login rate limiting** by IP (FINDING-06).

### Medium-term (next 2 sprints)
7. **Set Redis password** (FINDING-07).
8. **Rotate database credentials** to strong random values (FINDING-08).
9. **Sanitize filenames** in Content-Disposition headers (FINDING-09).
10. **Add password complexity validation** (FINDING-10).

### Ongoing
11. Review LLM prompt boundaries (FINDING-11).
12. Sanitize error messages to clients (FINDING-12).
13. Encrypt database dumps (FINDING-13).
14. Make CORS origins configurable (FINDING-14).
