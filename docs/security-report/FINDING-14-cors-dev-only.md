# FINDING-14: CORS Configuration Limited to Development Origins

## Severity: INFO

## Status: CONFIRMED

## Location

- `extraction-service/app/api.py`, lines 52-58

## Description

The CORS middleware is hardcoded to allow only `http://localhost:5173` and `http://127.0.0.1:5173` -- the Vite development server. This means the API will reject cross-origin requests from any production frontend deployment. While not a vulnerability in itself, this creates a deployment risk: operators may "fix" this by changing `allow_origins` to `["*"]` while keeping `allow_credentials=True`, which is a CORS misconfiguration that enables credential theft from any origin.

## Proof / Reasoning

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

The `allow_methods=["*"]` and `allow_headers=["*"]` are overly permissive but not exploitable as long as origins are restricted. However, `allow_credentials=True` with `allow_origins=["*"]` (a common "fix") would allow any website to make authenticated requests to the API.

## Impact

- **Current state:** Low risk -- origins are restricted to localhost.
- **Deployment risk:** High risk if an operator changes origins to `"*"` to "make it work in production" without understanding the credential implications.
- **Missing flexibility:** No environment-variable-driven origin configuration, making production deployment harder.

## Remediation

1. **Make CORS origins configurable** via environment variable:
   ```python
   origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
   ```

2. **Add a validation guard** that prevents `allow_origins=["*"]` when `allow_credentials=True`:
   ```python
   if "*" in origins and allow_credentials:
       raise ValueError("CORS: wildcard origins with credentials is insecure")
   ```

3. Restrict `allow_methods` and `allow_headers` to only what the frontend actually needs:
   ```python
   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
   allow_headers=["Authorization", "Content-Type"],
   ```
