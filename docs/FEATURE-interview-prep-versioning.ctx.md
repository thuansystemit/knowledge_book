# CTX: Interview Prep — Version History (interview-prep-versioning)

> **AI digest of `FEATURE-interview-prep-versioning.md`. Self-contained — read this alone.**
> Status: FINALIZED, all decisions locked (2026-07-08). Companion to `FEATURE-interview-prep-versioning.md`.
> Prerequisite: `FEATURE-interview-prep.ctx.md` (IP-01…IP-05 must be done first).

## What
Every regeneration of an interview prep plan inserts a new immutable `interview_prep_plans`
row (new plan_id, incremented version) instead of mutating the existing row. The previous
version's row and its questions are preserved. The user can switch between versions 1…N in
the UI and pin any past done version as current. A failed or in-progress generation never
destroys the last good version.

## Locked decisions (all resolved — no open questions)
- **Option A (append-only plan rows)** is the chosen model.
- **Retention: UNLIMITED.** No auto-prune, no cap, no `PREP_MAX_VERSIONS_PER_TRACK` config. All versions kept forever. Only mechanism for removal is explicit `DELETE /{plan_id}`.
- **Failed versions: KEPT in history** as status=error, is_current=false. Never auto-deleted.
- **Pin/rollback: IN SCOPE (Should).** `POST /{plan_id}/pin` is in this release, not deferred.
- **Concurrent regen: 409 hard block** while any (user, track) version has status pending/generating.
- **cost_usd shown in version switcher dropdown** (OQ-5: yes).
- **Admin `?all_versions=true` flag** on `GET /api/interview-prep` to see full history (OQ-6).
- **Partial unique index** `uix_prep_current ON (user_id, track) WHERE is_current=true` enforces at most one current per (user, track) at the DB layer. Postgres-only — acceptable.
- **is_current flip**: done inside a single `session_scope` transaction: bulk-unset all siblings, set new row = true. Partial unique index rejects any accidental double-current at commit time.

## Schema delta (interview_prep_plans only — questions table unchanged)
```sql
-- New columns
version     INTEGER  NOT NULL  DEFAULT 1
is_current  BOOLEAN  NOT NULL  DEFAULT false

-- Constraint changes
DROP CONSTRAINT uq_prep_user_track          -- was UNIQUE(user_id, track)
ADD CONSTRAINT  uq_prep_user_track_ver UNIQUE(user_id, track, version)
CREATE UNIQUE INDEX uix_prep_current ON interview_prep_plans(user_id, track)
  WHERE is_current = true
```
`interview_prep_questions` unchanged — already FKs to `interview_prep_plans.id` CASCADE.

## Migration: run_interview_prep_versioning() — app/migrations.py
Idempotent startup function (call after `run_interview_prep()` in `app/api.py`):
1. `ALTER TABLE interview_prep_plans ADD COLUMN IF NOT EXISTS version INTEGER`
2. `ALTER TABLE interview_prep_plans ADD COLUMN IF NOT EXISTS is_current BOOLEAN`
3. `UPDATE interview_prep_plans SET version = 1 WHERE version IS NULL`
4. `UPDATE interview_prep_plans SET is_current = (status = 'done') WHERE is_current IS NULL`
5. `ALTER COLUMN version SET NOT NULL DEFAULT 1; ALTER COLUMN is_current SET NOT NULL DEFAULT false`
6. `ALTER TABLE interview_prep_plans DROP CONSTRAINT IF EXISTS uq_prep_user_track`
7. `ALTER TABLE interview_prep_plans DROP CONSTRAINT IF EXISTS uq_prep_user_track_ver; ADD CONSTRAINT uq_prep_user_track_ver UNIQUE(user_id, track, version)`
8. `DROP INDEX IF EXISTS uix_prep_current; CREATE UNIQUE INDEX uix_prep_current ON interview_prep_plans(user_id, track) WHERE is_current = true`

Backfill: existing `done` rows → version=1, is_current=true. Other statuses → version=1, is_current=false.

## ORM model additions (app/models.py)
```python
# InterviewPrepPlan — add:
version:    Mapped[int]  = mapped_column(Integer, default=1)
is_current: Mapped[bool] = mapped_column(Boolean, default=False)

# __table_args__: replace UniqueConstraint("user_id","track",...) with:
UniqueConstraint("user_id", "track", "version", name="uq_prep_user_track_ver"),
Index("uix_prep_current", "user_id", "track",
      unique=True, postgresql_where=text("is_current = true")),
```

## Config: NO NEW SETTINGS
`app/config.py` requires no changes. There is no `prep_max_versions_per_track`. Retention is unlimited and unconfigured.

## generate_plan changes (app/interview_prep.py)
After bulk-inserting questions and persisting plan_data, inside the same `session_scope`:
```python
# Flip is_current atomically (NO prune — retention is unlimited)
db.query(InterviewPrepPlan).filter(
    InterviewPrepPlan.user_id == plan.user_id,
    InterviewPrepPlan.track == plan.track,
    InterviewPrepPlan.id != plan.id,
).update({"is_current": False})
plan.is_current = True
plan.status = "done"
# Commit happens at session_scope exit — partial unique index validates here
```
On error path: plan.status = 'error', plan.is_current remains False (correct since it defaults False on insert). No changes needed in the error handler.

## Route changes (app/interview_prep_routes.py)

### _create_new_version helper (replaces upsert logic in create_plan + regenerate_plan)
```python
from sqlalchemy import func

def _create_new_version(track: str, user: User, db: Session) -> InterviewPrepPlan:
    in_flight = db.scalar(select(InterviewPrepPlan).where(
        InterviewPrepPlan.user_id == user.id,
        InterviewPrepPlan.track == track,
        InterviewPrepPlan.status.in_(["pending", "generating"]),
    ))
    if in_flight:
        raise HTTPException(409, "A generation is already in progress for this track.")
    next_ver = (db.scalar(
        select(func.max(InterviewPrepPlan.version)).where(
            InterviewPrepPlan.user_id == user.id,
            InterviewPrepPlan.track == track,
        )
    ) or 0) + 1
    plan = InterviewPrepPlan(
        user_id=user.id, org_id=user.org_id, track=track,
        status="pending", version=next_ver, is_current=False,
    )
    db.add(plan)
    db.flush()
    return plan
```

### create_plan (POST /api/interview-prep)
Remove upsert logic entirely; call `_create_new_version(body.track, user, db)`.

### regenerate_plan (POST /api/interview-prep/{plan_id}/regenerate)
Resolve track from the referenced plan; call `_create_new_version(plan.track, user, db)`.
Return the new version's plan object. Do NOT mutate the old plan row.

### list_plans (GET /api/interview-prep)
Non-admin: add `InterviewPrepPlan.is_current == True` filter.
Admin: same default; `?all_versions=true` omits the filter (returns all versions, paginated 50).

### delete_plan (DELETE /api/interview-prep/{plan_id})
If plan.is_current: find next most-recent done version, set is_current=True on it.
db.delete(plan). Return `{"ok": True, "new_current_id": replacement.id or None}`.

### list_versions (new GET /api/interview-prep/{plan_id}/versions)
RBAC: _require_plan_access. Query all rows with same (user_id, track), order by version desc.
Include question_count per version via a GROUP BY subquery. Exclude plan_data and questions.
Response: `{track, versions: [{id, version, is_current, status, model, cost_usd, question_count, generated_at, created_at, error}]}`.

### pin_version (new POST /api/interview-prep/{plan_id}/pin)
RBAC: _require_plan_access (owner or admin).
Validate plan.status == 'done' → 422 if not ("Only completed versions can be pinned.").
Bulk-unset siblings: `UPDATE ... SET is_current=False WHERE user_id=... AND track=... AND id != plan.id`.
Set plan.is_current=True. Commit.
Return full plan + questions (same shape as GET /{plan_id}).

## _plan_public serializer additions (interview_prep_routes.py)
```python
"version": plan.version,
"is_current": plan.is_current,
```

## API — breaking changes summary
| Endpoint | Old behavior | New behavior |
|---|---|---|
| POST /api/interview-prep | Upsert single row; returns same plan_id if track existed | Always inserts new row; returns new plan_id; 409 if in-flight |
| POST /{plan_id}/regenerate | Mutates existing row in-place; returns same plan_id | Inserts new row; returns new plan_id; 409 if in-flight |
| DELETE /{plan_id} | Deletes entire (user, track) history | Deletes one version; promotes next current if needed |

## New API endpoints
| Method | Path | RBAC | Priority | Returns |
|---|---|---|---|---|
| GET | /api/interview-prep/{plan_id}/versions | owner or admin | Must | {track, versions:[{id,version,is_current,status,model,cost_usd,question_count,generated_at,created_at,error}]} |
| POST | /api/interview-prep/{plan_id}/pin | owner or admin; done only (422 otherwise) | Should | full plan object with is_current=true |

## Frontend files
- `frontend/src/api/interview-prep.api.ts` — add `version: number`, `is_current: boolean` to `PrepPlan`; add `listVersions(planId): Promise<VersionList>`, `pinVersion(planId): Promise<PrepPlanDetail>`
- `frontend/src/routes/InterviewPrepPage.tsx` — per-track state: `{currentPlan, inProgressPlan}`; subscribe to inProgressPlan's SSE; on done event re-fetch versions and switch to new current
- `frontend/src/components/interview-prep/TrackCard.tsx` — version badge ("v3 · Ready"); in-progress secondary indicator ("v4 Generating…")
- `frontend/src/components/interview-prep/PrepPlanView.tsx` — render `<VersionSwitcher>` when ≥2 versions; read-only banner with "Pin as Current" button when !is_current; in-progress strip (PrepProgressPanel) for inProgressPlan.id; hide Regenerate when viewing historical version
- `frontend/src/components/interview-prep/PrepProgressPanel.tsx` — no structural change; receives new plan_id per regen
- `frontend/src/components/interview-prep/VersionSwitcher.tsx` (new) — controlled dropdown; props: `versions`, `selectedId`, `onChange`; each option: "v{N} · {status} · {relative_date} · {Qs} Qs · ${cost_usd}"

## Acceptance criteria IDs
IP-06 (schema + migration) · IP-07 (regen creates new row, old intact) · IP-08 (success: is_current flip) · IP-09 (error: old version preserved) · IP-10 (list_versions RBAC + question_count) · IP-11 (version switcher UX + cost display) · IP-12 (409 concurrent guard) · IP-13 (pin: atomic flip, RBAC, 422 on non-done)

## Resolved decisions (no open questions remain)
OQ-1: retention = unlimited (no cap, no prune)
OQ-2: failed versions kept visible in history
OQ-3: pin in scope (Should, this release)
OQ-4: 409 hard block on concurrent regen
OQ-5: cost_usd shown per version in switcher dropdown
OQ-6: admin ?all_versions=true flag on GET /api/interview-prep

## Storage monitoring note
No auto-prune. Add `interview_prep_plans` row count (per user and per track) to `GET /api/admin/metrics` as a health signal. Alert if any user exceeds 20 versions per track. If storage becomes a concern in future, introduce a manual admin bulk-delete endpoint — do not add auto-prune without a new product decision.

## Files
`extraction-service/app/models.py` · `extraction-service/app/migrations.py` · `extraction-service/app/api.py` · `extraction-service/app/interview_prep.py` · `extraction-service/app/interview_prep_routes.py` · `frontend/src/api/interview-prep.api.ts` · `frontend/src/routes/InterviewPrepPage.tsx` · `frontend/src/components/interview-prep/TrackCard.tsx` · `frontend/src/components/interview-prep/PrepPlanView.tsx` · `frontend/src/components/interview-prep/PrepProgressPanel.tsx` · `frontend/src/components/interview-prep/VersionSwitcher.tsx` (new)

Note: `extraction-service/app/config.py` — NO CHANGES NEEDED.
