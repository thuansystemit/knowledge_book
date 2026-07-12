# FINDING-13: Database Dumps Created Without Encryption or Access Control

## Severity: LOW

**CVSS 3.1 Estimate:** 4.0 (AV:L/AC:L/PR:H/UI:N/S:U/C:H/I:N/A:N)

## Status: CONFIRMED

## Location

- `extraction-service/scripts/db-dump.sh`
- `extraction-service/scripts/db-restore.sh`

## Description

The database dump script creates an unencrypted gzip-compressed SQL file containing the entire database: user credentials (bcrypt hashes), all uploaded PDF files (binary), extracted knowledge graphs, chat histories, Stripe billing data, and activation events. The dump file has no file-level encryption and no access controls beyond standard filesystem permissions.

## Proof / Reasoning

**db-dump.sh (lines 17-20):**
```bash
docker compose exec -T db pg_dump -U kb -d kb \
  --no-owner --no-privileges --clean --if-exists \
  | gzip > "$OUT"
```

The output is a plain gzip'd SQL file. The script uses hardcoded credentials (`-U kb`, database `kb`).

**db-restore.sh (lines 26-27):**
```bash
$CAT "$IN" | docker compose exec -T db psql -U kb -d kb -v ON_ERROR_STOP=1 -q
```

The restore accepts any SQL file and executes it against the database, also with hardcoded credentials.

## Impact

- A dump file left on disk, transferred via unencrypted channels, or backed up to cloud storage exposes all application data.
- The dump includes bcrypt password hashes -- while bcrypt is slow to crack, a sufficiently motivated attacker with a leaked dump can attempt offline cracking.
- The dump includes all uploaded PDFs as binary blobs.
- If a malicious SQL dump is provided to the restore script, it could execute arbitrary SQL (though the interactive `y/N` prompt provides a minimal safeguard).

## Remediation

1. **Encrypt dump files** using GPG or age:
   ```bash
   docker compose exec -T db pg_dump -U kb -d kb | gzip | gpg -e -r admin@company.com > "$OUT.gpg"
   ```

2. **Set restrictive file permissions** on dump files: `chmod 600 "$OUT"`.

3. **Transfer dumps only over encrypted channels** (SCP, SFTP, encrypted object storage).

4. Consider adding a `--encrypt` flag to the dump script with a required passphrase.

5. For the restore script, validate that the SQL file contains only expected PostgreSQL commands (though this is difficult to do comprehensively).
