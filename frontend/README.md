# KnowledgeBook — Workflow Dashboard (React)

Live dashboard for the extraction service: upload a PDF, **watch each pipeline
stage run** (classify → OCR → chunk → extract → merge → brief) with live progress
via Server-Sent Events, then explore the resulting concept graph + Brief.

Stack mirrors `toeic_app/frontend`: **Vite + React + TypeScript +
`react-force-graph-2d`** (+ axios). No auth, no router — a single dashboard page.

## Run
```bash
# 1. start the API (in ../extraction-service)
cd ../extraction-service
pip install -r requirements.txt
uvicorn app.api:app --host 0.0.0.0 --port 8000      # reads ./.env (ollama host)

# 2. start the dashboard
cd ../frontend
cp .env.example .env          # VITE_API_URL=http://localhost:8000
npm install
npm run dev                   # http://localhost:5173
```
Open http://localhost:5173, click **Upload a PDF**, and watch the workflow.

## How it talks to the backend (`src/api.ts`)
- `POST /api/jobs` (multipart) → `{ job_id }`
- `EventSource /api/jobs/{id}/events` → one JSON event per stage (live progress)
- `GET /api/jobs/{id}` → final `{ status, graph }` (graph + Brief)

## Files
```
src/
  api.ts                      # axios client + SSE subscribe + types
  App.tsx                     # the dashboard page
  components/
    WorkflowStages.tsx        # stage list driven by live events
    GraphView.tsx             # react-force-graph-2d concept graph
  styles.css
```
