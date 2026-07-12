# FINDING-12: Error Messages Leak Internal Implementation Details

## Severity: LOW

**CVSS 3.1 Estimate:** 3.1 (AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:N/A:N)

## Status: CONFIRMED

## Location

- `extraction-service/app/chat_routes.py`, lines 166-169
- `extraction-service/app/tasks.py`, line 46
- `extraction-service/app/pipeline.py`, line 268

## Description

Exception messages from internal components (LLM providers, database operations, pipeline errors) are sent directly to the client in API responses and SSE streams. These messages can reveal internal hostnames, file paths, library versions, and infrastructure details that aid an attacker in reconnaissance.

## Proof / Reasoning

**Chat stream error (chat_routes.py, lines 166-169):**
```python
except Exception as e:  # e.g. LLM host unreachable
    audit("CHAT_STREAM_ERROR", job=job_id, error=str(e))
    yield f"data: {json.dumps({'error': str(e)})}\n\n"
```

**Task error propagation (tasks.py, line 44-46):**
```python
except Exception as e:
    status, error = "error", str(e)
    ...
    on_event({"stage": "done", "status": "error", "detail": str(e)})
```

**Chunk extraction errors (pipeline.py, line 268-269):**
```python
audit("CHUNK_FAILED", index=chunk["index"], error=str(last_err))
```

These errors are stored in `job.error` and `job.events` (api.py line 54, line 228), which are returned to the client.

## Impact

- Error messages from network libraries reveal internal hostnames: `ConnectionError: HTTPConnectionPool(host='192.168.100.158', port=11434)`.
- Database errors reveal table/column names and SQL structure.
- LLM SDK errors reveal API key format hints or endpoint URLs.
- This information aids targeted attacks but is not directly exploitable.

## Remediation

1. **Map exceptions to generic user-facing messages:**
   ```python
   except Exception as e:
       audit("CHAT_STREAM_ERROR", job=job_id, error=str(e))  # keep for server logs
       yield f"data: {json.dumps({'error': 'An internal error occurred. Please try again.'})}\n\n"
   ```

2. Store the full error in server-side audit logs (already done), but send only a sanitized message to the client.

3. Define an error classification system that maps exception types to safe user-facing messages.
