# FINDING-01: Live API Key Hardcoded in .env File

## Severity: CRITICAL

**CVSS 3.1 Estimate:** 9.1 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N)

## Status: CONFIRMED

## Location

`extraction-service/.env`, lines 39-41

## Description

The active `.env` file contains a live NVIDIA NIM API key in plaintext. While `.env` is gitignored and not tracked in the repository, the key is present on the development machine's disk and could be leaked through backups, disk images, shared access, or accidental inclusion in a future commit.

## Proof / Reasoning

```
# extraction-service/.env, lines 38-41
LLM_PROVIDER=openai
OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1
OPENAI_API_KEY=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
OPENAI_MODEL=qwen/qwen3.5-122b-a10b
```

The `.env.example` file even explicitly warns against this (line 24):
```
#   OPENAI_API_KEY=nvapi-...        # put your real key here, never commit it
```

## Impact

- An attacker with access to this file can use the NVIDIA NIM API under the owner's account, incurring compute charges.
- The key grants access to the `qwen/qwen3.5-122b-a10b` model endpoint and potentially other models.
- If the same key is reused across services, lateral movement is possible.
- Any backup, disk image, or screenshot that captures this file leaks the credential.

## Exploit Scenario

1. Attacker gains read access to the development machine (shared host, exposed backup, stolen laptop, accidental file share).
2. Attacker reads `extraction-service/.env` and extracts the NVIDIA API key.
3. Attacker makes API calls to `https://integrate.api.nvidia.com/v1` using the stolen key, consuming the owner's quota or credits.

## Remediation

1. **Immediately rotate** the NVIDIA API key (`nvapi-coHe7D...`) via the NVIDIA dashboard.
2. Use a secrets manager (e.g., Docker secrets, HashiCorp Vault, 1Password CLI) instead of plaintext `.env` files.
3. Add a pre-commit hook (e.g., `detect-secrets`, `gitleaks`) to prevent accidental commits of secrets.
4. Consider using environment variable injection from CI/CD or container orchestration rather than `.env` files on disk.
