# Feature: Interview Prep — Version History for Prep Plans

| | |
|---|---|
| **Document** | Design Proposal / PRD |
| **Version** | 1.1 |
| **Date** | 2026-07-08 |
| **Status** | FINALIZED — all decisions locked |
| **Parents** | `FEATURE-interview-prep.md`, `ARCHITECTURE-mvp.md` |
| **Feature ID** | interview-prep-versioning |
| **Scope** | Backend (data model + API) + Frontend (version switcher UX) |

> Every time a user regenerates a prep plan, the result is saved as a new immutable
> version. Users can switch between versions 1…N for a track, always seeing at least
> the last good plan even while a new generation is in progress.

---

## 1. Problem Statement

Today `POST /api/interview-prep/{plan_id}/regenerate` resets the single plan row
(`status=pending`, `plan_data=null`) and deletes all question rows before the new
generation finishes. If the regeneration errors or takes several minutes, the user
is left with no plan to read. There is also no audit trail of what earlier
generations produced — the user cannot compare across corpus snapshots.

**Goal:** Make every regeneration additive. Version N is never mutated once complete.
A failed or in-progress version N+1 must never destroy version N.

---

## 2. Data Model Options

Three concrete approaches, all grounded in the current schema.

### 2.1 Option A — Append-only plan rows (RECOMMENDED)

**Idea:** Drop `UNIQUE(user_id, track)`. Every regeneration inserts a new
`interview_prep_plans` row with an incremented `version` integer and
`is_current = false`. When generation succeeds, flip `is_current = true` on the
new row and `is_current = false` on all siblings for that (user, track).

**Schema delta:**

```
interview_prep_plans — add two columns:
  version     INTEGER  NOT NULL  DEFAULT 1
  is_current  BOOLEAN  NOT NULL  DEFAULT false

Constraints:
  DROP:   UNIQUE(user_id, track)                         -- uq_prep_user_track
  ADD:    UNIQUE(user_id, track, version)                -- uq_prep_user_track_ver
  ADD:    UNIQUE INDEX (user_id, track) WHERE is_current -- uix_prep_current (partial)
```

`interview_prep_questions` is unchanged — it already FKs to `interview_prep_plans.id`
with CASCADE, so questions are naturally versioned by their plan row.

**How "current" is resolved:**

```sql
SELECT * FROM interview_prep_plans
WHERE user_id = :uid AND track = :track AND is_current = true
LIMIT 1;
```

The partial unique index at the DB level enforces at most one current per
(user, track) at all times.

**In-flight regen safety — the central requirement:**

1. Route creates a new plan row: `version = N+1`, `status = 'pending'`,
   `is_current = false`.
2. Previous version row is untouched: `version = N`, `status = 'done'`,
   `is_current = true`.
3. Celery task runs against the new plan_id (its own SSE channel).
4. **On success:** inside a single DB transaction:
   ```sql
   UPDATE interview_prep_plans SET is_current = false
     WHERE user_id = :uid AND track = :track;
   UPDATE interview_prep_plans SET is_current = true
     WHERE id = :new_plan_id;
   ```
5. **On error:** new row stays `status = 'error'`, `is_current = false`.
   Version N remains current. User never loses their previous plan.

**Trade-offs:**

| Concern | Assessment |
|---|---|
| Query simplicity | Slightly more complex "current" query (filter by `is_current`), but the partial unique index makes it O(1). The `GET /api/interview-prep` list endpoint filters by `is_current = true`. |
| UNIQUE constraint | Dropped and replaced. Existing `_require_plan_access` and all FK relationships are untouched. |
| Cascade / retention | `DELETE /api/interview-prep/{plan_id}` cascades questions for that version only. Cross-version deletion is explicit. Retention is unlimited by design — see §4.6. |
| Storage growth | Unbounded by design (retention: unlimited — product decision). All plan rows and question rows accumulate indefinitely. Monitor `interview_prep_plans` row count as a health metric — see §9.1. |
| Breaking changes | `POST /api/interview-prep` and `POST /{plan_id}/regenerate` now return a new `plan_id` per call. Callers that cached the plan_id need to re-fetch. |
| SSE | Each version has its own plan_id, so `prep:{plan_id}` Redis namespace is naturally isolated per version. No changes to SSE infrastructure. |

---

### 2.2 Option B — Separate versions table

**Idea:** Keep `UNIQUE(user_id, track)` on `interview_prep_plans` (the "pointer"
table). Add `interview_prep_plan_versions` with full plan content. Plans gain a
`current_version_id FK plan_versions.id`.

**Why not recommended:**
- `interview_prep_questions` must be re-keyed to `plan_versions.id`, requiring
  a non-trivial migration on a live table with CASCADE FK changes.
- All question queries become two-hop joins: plan → current_version → questions.
- The Celery task must manage two tables with coordinated FKs.
- The SSE stream is keyed by `plan_id`, but multiple in-flight versions share
  the same plan_id — the stream namespace needs disambiguation.

Option B is more correct from a pure relational standpoint but adds substantial
complexity for this codebase's patterns.

---

### 2.3 Option C — Versions snapshotted in JSONB

**Idea:** Keep the single plan row. Add a `versions` JSONB column that appends
each completed generation's `plan_data`. Questions keep a `version` int column.

**Why not recommended:**
- JSONB blobs grow without bound (plan_data is 5–20 KB per version).
- Questions table still needs a `version` column and extra filtering.
- No easy way to reference, delete, or prune individual versions relationally.
- Makes the existing `_plan_public` serializer inconsistent.

---

## 3. Recommended Approach: Option A

Option A requires the smallest schema change, leaves question storage untouched,
and makes the in-flight safety guarantee trivially verifiable: if the Celery task
panics after step 1 and before step 4, the old row with `is_current = true` is
structurally intact and the new row with `is_current = false` is simply displayed
as `error` or `pending` — no data is lost.

---

## 4. Version Lifecycle & Semantics

### 4.1 Version numbering

- Versions are 1-indexed, per `(user_id, track)`.
- Assigned at plan creation time:
  ```sql
  SELECT COALESCE(MAX(version), 0) + 1 FROM interview_prep_plans
  WHERE user_id = :uid AND track = :track
  FOR UPDATE;
  ```
  The `FOR UPDATE` lock prevents duplicate version numbers from concurrent requests.
- Version numbers are immutable once assigned.

### 4.2 What "current" means

- Exactly one row per (user, track) has `is_current = true` at steady state.
  (Zero rows if no generation has ever succeeded for that track.)
- "Current" = the most recently pinned or successfully completed version.
- A `pending` or `generating` row is never current until it reaches `done`.
- An `error` row is never set to current.
- Users can explicitly reassign "current" via the pin endpoint (§5.2).

### 4.3 Failed or erroring generations (LOCKED)

**Decision: failed versions are kept in history.**

- A failed generation produces a new version row with `status = 'error'` and
  `is_current = false`.
- The previous current version is unaffected and remains current.
- Failed versions are kept indefinitely (never auto-deleted) so the user can see
  what went wrong and retry with context. They can be explicitly deleted via
  `DELETE /api/interview-prep/{plan_id}`.
- A failed version still increments the version counter — version 3 can be an
  error; version 4 is the next attempt. Gaps are normal.

### 4.4 Partially successful generations

The existing code allows individual topic batches to be skipped (LLM parse
failures) without failing the whole task, as long as `all_questions > 0`. This
behavior is unchanged. A partial success produces a `status = 'done'` version
(possibly with fewer questions) and becomes current. The `plan_data.corpus_coverage`
already captures `topics_without_coverage`.

### 4.5 Concurrent generation guard (LOCKED)

**Decision: 409 hard block.**

If a `(user_id, track)` already has a version with `status IN ('pending', 'generating')`,
the `POST /api/interview-prep` and `POST /{plan_id}/regenerate` endpoints return
**HTTP 409 Conflict** with body:
```json
{"detail": "A generation is already in progress for this track."}
```
This prevents runaway parallel tasks and ambiguous `is_current` flip ordering.

### 4.6 Retention (LOCKED)

**Decision: unlimited. All versions are kept forever.**

There is no auto-prune, no cap, and no `PREP_MAX_VERSIONS_PER_TRACK` config setting.
Every version — `done`, `error`, or otherwise — accumulates indefinitely per
(user, track). The only mechanism for reducing version count is explicit deletion
by the owner or admin via `DELETE /api/interview-prep/{plan_id}`.

Storage growth is accepted as a product trade-off. It should be monitored via
`interview_prep_plans` row count per user (see §9.1).

### 4.7 Explicit deletion

`DELETE /api/interview-prep/{plan_id}` deletes a single version:
- Cascades to `interview_prep_questions` for that version only.
- If the deleted version was `is_current = true`, the endpoint promotes the
  most recent `done` version (by `version` descending) to `is_current = true`.
  If no other `done` version exists, no version is current after deletion.
- Deleting the last remaining version of a track leaves no current version —
  the track card reverts to "Not Started".

---

## 5. API Design

All endpoints under `/api/interview-prep`. Auth is `Bearer` JWT; RBAC rules are
stated per endpoint using the existing `_require_plan_access` helper (owner or admin).

### 5.1 Existing endpoints — what changes

| Endpoint | Change | Breaking? |
|---|---|---|
| `POST /api/interview-prep` | Now inserts a new version row instead of upserting. Returns the new plan_id (different from any previous call). 409 if a generation is in-flight for that track. Adds `version` and `is_current` to response. | **Yes** — response plan_id changes per call |
| `GET /api/interview-prep` | Filters by `is_current = true`; still returns one plan per track. Adds `version`, `is_current` to each item. Admin can pass `?all_versions=true` to see all versions across the org. | No — shape is the same, just enriched |
| `GET /api/interview-prep/{plan_id}` | Unchanged. Returns the specific version by its UUID. Adds `version`, `is_current` to response. | No |
| `POST /api/interview-prep/{plan_id}/regenerate` | Creates a new version instead of mutating this row. Returns the new plan_id. 409 if a generation already in-flight. | **Yes** — response plan_id is a new ID |
| `POST /api/interview-prep/{plan_id}/stream-token` | Unchanged. Token is scoped to the new plan_id. | No |
| `GET /api/interview-prep/{plan_id}/events` | Unchanged. SSE stream is per plan_id. | No |
| `DELETE /api/interview-prep/{plan_id}` | Now deletes one version (not the whole track). Promotes a new current if needed. Returns `{"ok": true, "new_current_id": "<id or null>"}`. | **Yes** — semantics change |

### 5.2 New endpoints

#### `GET /api/interview-prep/{plan_id}/versions`

List all versions for the same `(user_id, track)` as this plan.

**RBAC:** owner or admin (via `_require_plan_access` on the referenced plan).

**Response:**
```json
{
  "track": "junior_backend",
  "versions": [
    {
      "id": "abc123",
      "version": 3,
      "is_current": true,
      "status": "done",
      "model": "claude-sonnet-4-6",
      "cost_usd": 0.18,
      "question_count": 22,
      "generated_at": "2026-07-08T12:00:00Z",
      "created_at": "2026-07-08T11:58:00Z",
      "error": null
    },
    {
      "id": "def456",
      "version": 2,
      "is_current": false,
      "status": "error",
      "model": null,
      "cost_usd": null,
      "question_count": 0,
      "generated_at": null,
      "created_at": "2026-07-07T10:00:00Z",
      "error": "interview-prep cost cap exceeded: $0.52 > $0.50"
    },
    {
      "id": "ghi789",
      "version": 1,
      "is_current": false,
      "status": "done",
      "model": "claude-sonnet-4-6",
      "cost_usd": 0.15,
      "question_count": 19,
      "generated_at": "2026-07-06T09:00:00Z",
      "created_at": "2026-07-06T08:58:00Z",
      "error": null
    }
  ]
}
```

Note: `plan_data` and full questions are NOT included here; call `GET /{plan_id}`
to retrieve full content for a specific version.

#### `POST /api/interview-prep/{plan_id}/pin`

Mark this version as `is_current = true`, atomically unmark all other versions for
this (user, track). Allows the user to roll back to a previous version as "current".

**RBAC:** owner or admin.

**Constraints:**
- Only `done` versions can be pinned. Pinning a `pending`, `generating`, or `error`
  version returns **HTTP 422** with body `{"detail": "Only completed versions can be pinned."}`.
- Cross-user pin attempt returns **403** (enforced by `_require_plan_access`).

**Response:** the pinned plan object (same shape as `GET /{plan_id}`), with
`is_current = true`.

**Priority: Should.** This is in scope for this release — not deferred.

### 5.3 Response field additions

All plan responses gain:
```json
{
  "version": 3,
  "is_current": true,
  ...existing fields...
}
```

---

## 6. UX Design

### 6.1 TrackCard

The three track cards on `InterviewPrepPage` show the current version's status.
When a new generation is in progress, a secondary indicator appears.

| Scenario | Badge shown | CTA |
|---|---|---|
| No versions yet | — (empty) | "Generate Plan" |
| Version N done (current), no in-progress | "v3 · Ready" (green) | "View Plan" + "Regenerate → v4" |
| Version N done (current), vN+1 generating | "v3 · Ready" + "v4 Generating…" (spinner) | "View v3" (the regen is already running) |
| Latest version is error, no good version | "v2 · Error" (red) | "Try Again → v3" |
| Latest version is error, v1 is current | "v1 · Ready" + "v2 Failed" | "View v1" + "Regenerate → v3" |

### 6.2 Version Switcher

A dropdown at the top of `PrepPlanView`, visible whenever there are 2 or more
versions. Rendered as a `<select>` or a Radix-style popover menu.

Each option label (cost_usd shown per locked OQ-5):
```
v3 · Current · 2026-07-08 · claude-sonnet-4-6 · 22 Qs · $0.18
v2 · Failed  · 2026-07-07
v1 · Older   · 2026-07-06 · claude-sonnet-4-6 · 19 Qs · $0.15
```

The current version is pre-selected. Selecting a different version fetches that
version's full detail (`GET /{plan_id}`) and re-renders the tab panels below.

If only one version exists, the version switcher is hidden.

### 6.3 Read-only banner for historical versions

When the displayed version is not `is_current`:
```
┌─────────────────────────────────────────────────────────────────────┐
│ ⓘ  Viewing Version 1 (generated 2026-07-06) — Read-only.           │
│    Switch to v3 (Current) →    Pin this version as Current          │
└─────────────────────────────────────────────────────────────────────┘
```

- The "Regenerate" button is hidden when viewing a historical version.
- A "Pin as Current" button appears in the banner and calls `POST /{plan_id}/pin`.

### 6.4 In-progress generation alongside existing content

When a regeneration is running:
- The current version (`is_current = true`) is displayed normally in `PrepPlanView`.
- A progress strip appears above the version switcher:
  ```
  ┌──────────────────────────────────────────────────────────────────┐
  │ ⟳  Generating v4…  Scanning corpus for 'API design patterns'…   │
  └──────────────────────────────────────────────────────────────────┘
  ```
  This strip uses `PrepProgressPanel` with the new plan_id's SSE stream.
- When v4 completes: the version switcher adds v4, auto-selects it, and the
  progress strip disappears.
- The user can continue reading v3's content while v4 generates.

### 6.5 Regenerate button copy

The "Regenerate" button in `PrepPlanView` (visible only on the current version):
- Default: "Regenerate → creates v4"
- Disabled with tooltip when a generation is in-progress: "Generation in progress (v4)…"

### 6.6 Version detail chips (in PrepPlanView header)

Below the track title, a row of metadata chips:
```
v3 · Current  |  claude-sonnet-4-6  |  Jul 8, 2026  |  22 questions  |  $0.18  |  3 docs scanned
```

For older (non-current) versions, the "Current" chip is replaced by "Older version".

---

## 7. Migration

### 7.1 New idempotent startup function: `run_interview_prep_versioning()`

Called from `_startup()` in `app/api.py` after the existing `run_interview_prep()`.

Steps (all idempotent via `ADD COLUMN IF NOT EXISTS` and `IF NOT EXISTS`):

```sql
-- Step 1: Add new columns (NULLable first to avoid default-value table rewrites)
ALTER TABLE interview_prep_plans
  ADD COLUMN IF NOT EXISTS version INTEGER;
ALTER TABLE interview_prep_plans
  ADD COLUMN IF NOT EXISTS is_current BOOLEAN;

-- Step 2: Backfill existing rows
UPDATE interview_prep_plans
SET version = 1
WHERE version IS NULL;

UPDATE interview_prep_plans
SET is_current = (status = 'done')
WHERE is_current IS NULL;

-- Step 3: Apply NOT NULL constraints now that data is populated
ALTER TABLE interview_prep_plans
  ALTER COLUMN version SET NOT NULL,
  ALTER COLUMN version SET DEFAULT 1;
ALTER TABLE interview_prep_plans
  ALTER COLUMN is_current SET NOT NULL,
  ALTER COLUMN is_current SET DEFAULT false;

-- Step 4: Drop old uniqueness constraint
ALTER TABLE interview_prep_plans
  DROP CONSTRAINT IF EXISTS uq_prep_user_track;

-- Step 5: Add new uniqueness constraint
ALTER TABLE interview_prep_plans
  DROP CONSTRAINT IF EXISTS uq_prep_user_track_ver;
ALTER TABLE interview_prep_plans
  ADD CONSTRAINT uq_prep_user_track_ver UNIQUE (user_id, track, version);

-- Step 6: Add partial unique index for is_current
DROP INDEX IF EXISTS uix_prep_current;
CREATE UNIQUE INDEX uix_prep_current
  ON interview_prep_plans (user_id, track)
  WHERE is_current = true;
```

**Backfill semantics for existing rows:**
- Existing `status = 'done'` rows: `version = 1, is_current = true`. These become
  the baseline versions.
- Existing `status = 'error'` rows: `version = 1, is_current = false`. These existed
  because the UNIQUE constraint allowed them — they were overwritten on the next
  attempt. Now they surface as version 1 with error status.
- Existing `status IN ('pending', 'generating')` rows: `version = 1, is_current = false`.
  Unlikely to exist at migration time (restarts leave orphaned tasks resolved to error).

Note: the partial unique index `WHERE is_current = true` is Postgres-specific.
The project already requires Postgres, so this is acceptable.

### 7.2 ORM model changes

In `app/models.py`, `InterviewPrepPlan` gains:
```python
version: Mapped[int] = mapped_column(Integer, default=1)
is_current: Mapped[bool] = mapped_column(Boolean, default=False)
```
The `UniqueConstraint("user_id", "track", ...)` in `__table_args__` is replaced by
`UniqueConstraint("user_id", "track", "version", name="uq_prep_user_track_ver")`.
The partial index is declared as an `Index(..., postgresql_where=...)` in
`__table_args__`.

---

## 8. Backend Implementation Notes

### 8.1 `generate_plan` changes (`app/interview_prep.py`)

After the persist step, within the same `session_scope`, atomically flip `is_current`:

```python
# Flip is_current atomically — no auto-prune (retention: unlimited)
db.query(InterviewPrepPlan).filter(
    InterviewPrepPlan.user_id == plan.user_id,
    InterviewPrepPlan.track == plan.track,
    InterviewPrepPlan.id != plan.id,
).update({"is_current": False})
plan.is_current = True
plan.status = "done"
```

On error path: `plan.status = 'error'`, `plan.is_current = False` (already correct
since `is_current` defaults to `False` on insert — no change needed in the error
handler).

There is no pruning step. All versions accumulate indefinitely.

### 8.2 Route changes (`app/interview_prep_routes.py`)

**`_create_new_version` helper** (replaces upsert logic in `create_plan` and
`regenerate_plan`):
```python
from sqlalchemy import func

def _create_new_version(track: str, user: User, db: Session) -> InterviewPrepPlan:
    # 409 guard — at most one in-flight generation per (user, track)
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

**`list_plans`** — adds `is_current = true` filter for non-admin queries. Admin with
`?all_versions=true` omits this filter to see all versions across the org.

**`delete_plan`** — deletes one version; promotes a new current if the deleted
version was current:
```python
if plan.is_current:
    replacement = db.scalar(
        select(InterviewPrepPlan)
        .where(InterviewPrepPlan.user_id == plan.user_id,
               InterviewPrepPlan.track == plan.track,
               InterviewPrepPlan.status == "done",
               InterviewPrepPlan.id != plan.id)
        .order_by(InterviewPrepPlan.version.desc())
    )
    if replacement:
        replacement.is_current = True
db.delete(plan)
db.commit()
return {"ok": True, "new_current_id": replacement.id if (plan.is_current and replacement) else None}
```

**`list_versions`** (new):
```python
@router.get("/{plan_id}/versions")
def list_versions(plan_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    plan = _require_plan_access(db.get(InterviewPrepPlan, plan_id), user)
    versions = db.scalars(
        select(InterviewPrepPlan)
        .where(InterviewPrepPlan.user_id == plan.user_id,
               InterviewPrepPlan.track == plan.track)
        .order_by(InterviewPrepPlan.version.desc())
    ).all()
    counts = dict(db.execute(
        select(InterviewPrepQuestion.plan_id, func.count())
        .where(InterviewPrepQuestion.plan_id.in_([v.id for v in versions]))
        .group_by(InterviewPrepQuestion.plan_id)
    ).all())
    return {"track": plan.track,
            "versions": [_version_summary(v, counts.get(v.id, 0)) for v in versions]}
```

**`pin_version`** (new):
```python
@router.post("/{plan_id}/pin")
def pin_version(plan_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    plan = _require_plan_access(db.get(InterviewPrepPlan, plan_id), user)
    if plan.status != "done":
        raise HTTPException(422, "Only completed versions can be pinned.")
    db.query(InterviewPrepPlan).filter(
        InterviewPrepPlan.user_id == plan.user_id,
        InterviewPrepPlan.track == plan.track,
        InterviewPrepPlan.id != plan.id,
    ).update({"is_current": False})
    plan.is_current = True
    db.commit()
    questions = db.scalars(select(InterviewPrepQuestion).where(
        InterviewPrepQuestion.plan_id == plan_id
    ).order_by(InterviewPrepQuestion.sort_order)).all()
    return {**_plan_public(plan), "questions": [_question_public(q) for q in questions]}
```

### 8.3 No config addition

There is no `prep_max_versions_per_track` setting. Retention is unlimited and
requires no configuration.

---

## 9. Risks & Resolved Decisions

### 9.1 Known risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Race on version number assignment** | Low (user would have to click Regenerate simultaneously from two tabs) | Medium — duplicate version constraint violation | `SELECT ... FOR UPDATE` in the version-assignment transaction; 409 guard on in-flight versions eliminates the practical path |
| **Partial unique index (Postgres-only)** | Low (project is Postgres-only) | Low | Documented dependency; acceptable for this stack |
| **Storage growth (unbounded by design)** | Medium — power users regenerate often; growth is permanent | Medium — Postgres table bloat over time | Accepted product trade-off. Monitoring recommendation: add `interview_prep_plans` row count to the admin metrics endpoint (`GET /api/admin/metrics`). If growth becomes a concern, introduce a manual admin endpoint to bulk-delete old versions for a user; do not auto-prune without a future product decision |
| **is_current flip non-atomicity** | Low (done in a single transaction) | High if it occurs | Both UPDATE statements and the `plan.status = 'done'` write are in one `session_scope` block; the partial unique index causes a constraint error on commit if two rows end up current |
| **Orphaned generating rows** | Medium (worker crash mid-task) | Low | Celery error handler already sets `status='error'`; orphaned `pending` rows surface as stuck versions and are cleared by the 409 guard on the next attempt |
| **Admin list performance** | Low (small user base initially) | Low | `is_current` filter is indexed via `uix_prep_current`; paginate admin `?all_versions=true` at 50 per page |

### 9.2 Resolved decisions

All open questions from the initial proposal have been decided and are now locked:

| # | Question | Decision | Rationale |
|---|---|---|---|
| OQ-1 | Retention cap per track | **Unlimited — no cap, no auto-prune** | Product decision; all history kept forever |
| OQ-2 | Failed versions in history | **Keep visible** (status=error, is_current=false) | User can see error detail and retry with context |
| OQ-3 | Pin / rollback support | **In scope — Should** (`POST /{plan_id}/pin`) | Needed so users can roll back if a newer version is worse |
| OQ-4 | Concurrent regen guard | **409 hard block** while pending/generating exists | Prevents cost overruns and ambiguous is_current ordering |
| OQ-5 | Cost display in switcher | **Yes** — show `cost_usd` per version in the dropdown | Provenance context for version comparison |
| OQ-6 | Admin version visibility | **Admin `?all_versions=true` flag** on `GET /api/interview-prep` | Default admin list shows current versions; flag exposes history |

---

## 10. Acceptance Criteria

| ID | Criterion |
|---|---|
| IP-06 AC | `interview_prep_plans` gains `version` and `is_current` columns; partial unique index `uix_prep_current` enforces at most one current per (user, track); existing rows backfilled as version 1 |
| IP-07 AC | Regenerating a track creates a new row (new plan_id, version N+1, is_current=false); the previous row is NOT mutated; the old plan's questions are intact; SSE streams to the new plan_id |
| IP-08 AC | On task success: new version flips is_current=true; old current unset; questions for old version remain intact; API returns new version as current in GET /api/interview-prep |
| IP-09 AC | On task error: new version has status=error, is_current=false; previous current version unchanged; user can still GET the previous current plan |
| IP-10 AC | GET /{plan_id}/versions returns all versions for that (user, track) in descending version order; RBAC blocks cross-user access (403); question_count per version is accurate |
| IP-11 AC | Version switcher renders in PrepPlanView when >= 2 versions exist; each option shows version number, status, relative date, question count, and cost_usd; switching versions fetches and renders the correct content; read-only banner shows for non-current versions |
| IP-12 AC | Concurrent regen returns 409 if a pending/generating version exists for that track; no new row is created on 409 |
| IP-13 AC | PIN: `POST /{plan_id}/pin` on a done version sets is_current=true and unsets all siblings in one transaction; cross-user pin returns 403; pinning a non-done version returns 422; the previously current version's is_current becomes false |

---

## 11. Success Metrics

| Metric | Target | How measured |
|---|---|---|
| Zero data-loss regressions | 0 incidents of a user's current version being destroyed by a failed regen | Monitor `is_current` on plans with `status = 'error'` — should always be false |
| Version switcher usage | ≥ 20% of users with ≥ 2 versions click the switcher within 7 days | New `activation_event` `kind = prep_version_switch` |
| Storage health | Average versions per (user, track) ≤ 5; alert if any user exceeds 20 versions per track | `AVG / MAX` of version count per (user, track) in admin metrics |

---

## 12. Files Changed

| File | Change |
|---|---|
| `extraction-service/app/models.py` | Add `version`, `is_current` to `InterviewPrepPlan`; update `__table_args__` |
| `extraction-service/app/migrations.py` | Add `run_interview_prep_versioning()` |
| `extraction-service/app/api.py` | Call `run_interview_prep_versioning()` after `run_interview_prep()` |
| `extraction-service/app/interview_prep.py` | Update `generate_plan`: atomic is_current flip on success (no prune) |
| `extraction-service/app/interview_prep_routes.py` | `_create_new_version` helper; update `create_plan`, `regenerate_plan`, `list_plans`, `delete_plan`; add `list_versions`, `pin_version` |
| `frontend/src/api/interview-prep.api.ts` | Add `version`, `is_current` to `PrepPlan`; add `listVersions(planId)`, `pinVersion(planId)` |
| `frontend/src/routes/InterviewPrepPage.tsx` | Track in-progress plan_id alongside current plan per track |
| `frontend/src/components/interview-prep/TrackCard.tsx` | Show version number badge + in-progress indicator |
| `frontend/src/components/interview-prep/PrepPlanView.tsx` | Add version switcher; read-only banner with Pin button; in-progress generation strip |
| `frontend/src/components/interview-prep/PrepProgressPanel.tsx` | Accept new plan_id for each regen (minor) |
| `frontend/src/components/interview-prep/VersionSwitcher.tsx` (new) | Dropdown with version metadata chips |

Note: `extraction-service/app/config.py` requires **no changes** — there is no
`prep_max_versions_per_track` setting.

---

## 13. Future (Phase 2 — explicitly deferred)

- **Diff view**: side-by-side comparison of two versions' question sets.
- **Version annotations**: user notes on why they regenerated ("added 3 new books").
- **Version export**: export a specific version as Markdown or Anki.
- **Shared plan versions**: admin publishes a specific version as the org-curated plan.
- **Bulk version management**: admin endpoint to delete all non-current versions for
  a user (storage reclamation without auto-prune).

---

*End of Design Proposal v1.1 — all decisions locked 2026-07-08.*
