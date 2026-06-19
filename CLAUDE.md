# FinDocIntel — CLAUDE.md

## Working Rules (Non-Negotiable)

### Day-wise execution
- Work is always scoped to the current day's deliverable from the plan (§8 of FinDocIntel_Plan_v2.md).
- Each day has exactly one concrete deliverable — not a goal. Done or not done.
- If a deliverable isn't finished, it carries over as the first task the next day. No silent slippage.

### Branch-per-day
- Every day gets its own branch: `sanyam/day1`, `sanyam/day2`, etc. (or `vaibhavi/day1`, etc.)
- Branch from `dev`, merge back to `dev` via PR at EOD.
- Never commit directly to `dev` or `main`.
- PR title follows: `type(scope): description` (e.g. `feat(api): scaffold FastAPI + docker-compose`)
- No PR merges without a description explaining what changed and why.

### Commit convention
Format: `type(scope): short description`
Types: `feat`, `fix`, `test`, `chore`, `docs`, `refactor`, `perf`
No vague messages: no `"fix stuff"`, `"wip"`, `"asdfasdf"`.

### Secrets
- Never commit `.env`, API keys, or real credentials.
- `.env.example` lists every required variable with placeholder values.
- `.gitignore` already excludes `.env`.

---

## Team
| Member | Role | Branch prefix |
|---|---|---|
| Sanyam | Backend ML + UI (LangGraph DAG, contradiction classifier, GraphRAG, eval metrics, /analyze + /retrieve, contradiction viewer UI) | `sanyam/` |
| Vaibhavi | Infra + ML + UI (EDGAR ingestion, chunker, risk extractor, Pydantic schema, LLM-as-judge, eval dashboard, Docker/CI/CD, deployment) | `vaibhavi/` |

---

## How to start each day

1. Pull latest `dev`:
   ```
   git checkout dev && git pull origin dev
   ```
2. Create the day branch:
   ```
   git checkout -b sanyam/dayN   # or vaibhavi/dayN
   ```
3. Check `todo.txt` for today's single deliverable.
4. Work. Commit often with proper messages.
5. Open PR to `dev` at EOD. Other member reviews before merge.

---

## Stack at a glance
- **Backend:** FastAPI + LangGraph (Python 3.11)
- **DB:** PostgreSQL 16 + pgvector extension (via `pgvector/pgvector:pg16` Docker image)
- **Local LLM:** Qwen2.5-14B-Instruct via Ollama (extractor); Llama-3.1 / Mistral (judge)
- **Embeddings:** bge-base-en-v1.5 or Qwen3-Embedding (local); `text-embedding-3-small` fallback
- **Frontend:** Next.js 14 (App Router)
- **Infra:** Docker Compose (local) → Railway/Fly.io (API) + Supabase (DB) + Vercel (frontend)

## Running locally
```bash
# From repo root
cp .env.example .env        # fill in real values
cd infra
docker compose up -d --build
curl http://localhost:8000/health   # → {"status":"ok"}
```

## Key files
- `FinDocIntel_Plan_v2.md` — full system design, schema, timeline, API contract
- `todo.txt` — current day's task checklist (updated daily)
- `summary.md` — running log of what's done + handoff notes between members
- `infra/docker-compose.yml` — local stack
- `backend/app/main.py` — FastAPI entrypoint
