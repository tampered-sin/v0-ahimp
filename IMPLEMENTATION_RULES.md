# AHIMP Implementation Rules

## 1. Purpose
These rules define how features are implemented, validated, and documented in this repository.
Use them for all backend, frontend, ML, and API work.

## 2. Core Principles
- Keep changes small, focused, and reversible.
- Prefer production-safe defaults over quick hacks.
- Preserve backward compatibility for existing APIs unless a breaking change is explicitly approved.
- Validate behavior with tests before marking work complete.
- Update implementation tickets and docs in the same change set.

## 3. Project Scope and Ownership
- Frontend: Next.js app in app/, components/, lib/, styles/.
- Backend: FastAPI service in backend/.
- ML models: backend/models/ with persisted artifacts in backend/models/pkl/.
- Data features and ingestion logic: backend/data/ and backend/api/consumption.py.
- Ticket source of truth: IMPLEMENTATION_TICKETS.md.

## 4. Task Execution Workflow
- Start from an explicit ticket or clearly written task statement.
- Confirm acceptance criteria before coding.
- Implement in vertical slices: model/service, API, tests, docs, ticket update.
- Run targeted tests first, then run the full backend test suite.
- Commit only relevant files for the task.

## 5. Coding Rules

### 5.1 Python Backend Rules
- Use type hints for all new functions and public methods.
- Keep functions single-purpose and side-effect aware.
- Raise HTTPException for API-level errors with clear status codes and messages.
- Avoid hidden global state except for explicit caches/buffers with documented limits.
- Keep imports deterministic and avoid runtime import side effects unless required.

### 5.2 API Rules
- All backend endpoints must live under /api.
- Use pydantic models for request validation.
- Return stable response shapes with predictable keys.
- For long-running operations, return progress metadata or run asynchronously.
- Add route tests for new endpoints and critical branches.

### 5.3 Frontend Rules
- Reuse existing UI and layout patterns unless redesign is requested.
- Keep data contracts aligned with backend response schemas.
- Handle backend unavailability gracefully (loading, empty, and error states).

## 6. ML and Tuning Rules
- Keep model training code deterministic when possible (seeded randomness).
- Use temporal splits for time-series validation.
- Track metrics used by tickets (R2, MAE, RMSE, inference time).
- Store tunable hyperparameters in code or JSON artifacts that can be audited.
- For tuning jobs:
  - Persist best params and top trials in backend/models/best_params.json.
  - Persist comparison summaries in backend/models/optimization_report.json.
- Do not commit large transient training artifacts unless explicitly required.

## 7. Data and Database Rules
- Prefer configured DATABASE_URL with supported fallback for local development.
- If PostgreSQL is unavailable locally, use SQLite fallback only for local execution.
- Seeder behavior must remain idempotent.
- Do not hardcode credentials or environment-specific secrets.

## 8. Testing and Validation Rules
- Every feature must include tests at the right level:
  - Unit tests for pure logic.
  - API tests for route behavior.
  - Integration checks for ML training/forecast workflows when applicable.
- Minimum validation before merge:
  - New/updated tests pass.
  - Full backend tests pass.
- Warnings are acceptable only when known and documented.

## 9. Dependency Rules
- Pin dependency versions in backend/requirements.txt.
- Use versions compatible with the active Python runtime in this repo.
- If a ticket specifies an incompatible version, choose the nearest compatible version and document the reason in tickets.

## 10. Git and Commit Rules
- Use one branch per epic with naming format `epic/<EPIC-ID>-<short-name>`.
- Create and work in the epic branch from the latest `main` baseline.
- Keep commits task-focused inside the epic branch (one logical commit group per task).
- Never include unrelated files in a task commit.
- Do not commit local-only noise files or generated caches.
- Keep commit messages explicit and traceable to ticket intent.
- Do not push the epic branch until all tasks in that epic are marked completed in `IMPLEMENTATION_TICKETS.md`.
- When all epic tasks are complete, run full regression, then push the epic branch and open the PR.

## 11. Documentation Rules
- Update IMPLEMENTATION_TICKETS.md whenever status or acceptance changes.
- Update backend/README.md when endpoints, training flow, or dependencies change.
- Record benchmark or tuning outputs in tracked JSON files when they support acceptance criteria.

## 12. Security and Operational Rules
- Keep secret values in environment variables only.
- Notification channels must fail safely (log fallback allowed).
- Ensure alerts and ingestion paths do not break core API availability if external services fail.

## 13. Definition of Done
A task is done only when all items below are satisfied:
- Acceptance criteria implemented or explicitly marked as pending with reason.
- Tests added and passing.
- Full backend regression passing.
- Ticket and relevant docs updated.
- Changes committed to the active epic branch.
- Epic branch is pushed only after all tasks in that epic are completed.

## 14. Agent LLM Policy (CrewAI + Ollama3)
- Default reasoning LLM for all CrewAI agents in this project is local Ollama.
- Required model identifier: `ollama/llama3`.
- Required local endpoint: `http://localhost:11434`.
- Agent configuration must use CrewAI `LLM` with explicit model and base URL.
- Do not require cloud LLM providers for core agent execution unless explicitly approved.
- If a fallback provider is introduced, document:
  - Why fallback is needed
  - Activation conditions
  - Security and cost impact
- Environment variables for agent runs should include:
  - `OLLAMA_BASE_URL=http://localhost:11434`
  - `OLLAMA_MODEL=ollama/llama3`
  - `CREW_LLM_PROVIDER=ollama`
- Any new agent ticket must state the Ollama model requirement in acceptance criteria.
