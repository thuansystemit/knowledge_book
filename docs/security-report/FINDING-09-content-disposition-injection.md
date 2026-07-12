# FINDING-09: Content-Disposition Header Injection via Unsanitized Filename

## Severity: MEDIUM

**CVSS 3.1 Estimate:** 5.3 (AV:N/AC:L/PR:L/UI:R/S:U/C:N/I:L/A:N)

## Status: CONFIRMED

## Location

- `extraction-service/app/api.py`, line 202

## Description

When serving stored files back to users, the `Content-Disposition` header is constructed using the original filename from the upload, without sanitization. A malicious filename containing double quotes or newlines can break the header format, potentially leading to response header injection.

## Proof / Reasoning

**Vulnerable line (api.py, line 200-202):**
```python
return Response(content=f.data, media_type=f.mime or "application/pdf",
                headers={"Content-Disposition": f'inline; filename="{f.filename}"'})
```

`f.filename` is stored directly from the upload (api.py, line 133):
```python
db.add(DocumentFile(job_id=job.id, filename=file.filename or "document.pdf",
                    mime=file.content_type or "application/pdf", data=data))
```

**Contrast with the export endpoint (api.py, lines 185-192) which DOES sanitize:**
```python
safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (job.title or "document"))[:80]
...
headers={"Content-Disposition": f'attachment; filename="{safe}.json"'}
```

The export endpoint applies character filtering, but the PDF serving endpoint does not.

## Impact

- A filename like `evil.pdf"; malicious-header: injected` could inject additional header directives.
- In practice, modern frameworks and ASGI servers mitigate most header injection via response serialization, but the unsanitized input is still a defense-in-depth violation.
- Edge cases with specific proxy configurations could lead to response splitting.

## Exploit Scenario

1. Attacker uploads a file named: `document.pdf\r\nX-Injected: true`
2. When the file is served, the raw filename is placed in the `Content-Disposition` header.
3. Depending on the ASGI server and any reverse proxies, this could result in header injection.

## Remediation

1. **Sanitize the filename** before including it in the header, using the same pattern as the export endpoint:
   ```python
   safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in (f.filename or "document.pdf"))[:255]
   ```

2. Use RFC 6266 `filename*` encoding for non-ASCII filenames.

3. Consider using `Content-Disposition: attachment` instead of `inline` for additional safety.
