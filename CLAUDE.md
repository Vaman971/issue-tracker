
---

**Role & Objective**
You are an expert backend engineer building a production-ready RAG pipeline API. Your goal is to incrementally implement Phase 6 (Production API) and Phase 7 (Production Hardening) of our roadmap.

**Core Directives**

1. **Incremental Execution:** We will build this strictly step-by-step. Do **NOT** proceed to the next step until I have reviewed, tested, and explicitly approved the current step.
2. **Code Quality:** Write professional, low-complexity, and highly readable code. Use helper functions appropriately to keep the route handlers clean.
3. **Reference Architecture:** Follow the established patterns, dependency injection, and error handling styles found in `@backend/app/api/routes/issues.py`, `@backend/app/api/routes/projects.py`, and their respective helpers (`@backend/app/api/helpers/issue_helper.py`, `@backend/app/api/helpers/project_helper.py`).

---

### PHASE 6: Production API

Please start by acknowledging these instructions. When I give you the go-ahead, begin with **Step 6.1 & 6.2**.

#### Step 6.1 & 6.2: Persistent Conversation State & IDs

* **Task:** Design and implement the database schema/models to persist RAG conversation history. We cannot use volatile Python data structures.
* **Requirements:**
* Must generate and handle a unique `conversation_id`.
* Must store user queries and AI responses (with timestamps).
* Must support fetching a list of previous conversations for a user.


* **Action:** Propose the schema/model and the corresponding CRUD operations in a new helper file. Wait for my approval.

#### Step 6.3 & 6.5: Basic `POST /rag/chat` Endpoint & Streaming

* **Task:** Create the main route and integrate the basic RAG pipeline logic.
* **Requirements:**
* Create `@backend/app/api/routes/rag.py` (or similar).
* Implement the `/rag/chat` endpoint.
* Implement streaming for the response so the user gets real-time token generation.


* **Action:** Write the route handler and helper logic. Wait for my approval.

#### Step 6.4: Authentication & Security Layer

* **Task:** Secure the endpoint based on our RBAC model.
* **Requirements:**
* Ensure the user is authenticated.
* Apply read-level access. (Note: Since we do not have agentic/write features yet, any authenticated user can query the RAG pipeline; we do not need strict granular resource-level blocking for read-only RAG queries at this stage).


* **Action:** Integrate existing Authentication dependencies into the route. Wait for my approval.

#### Step 6.6: Graceful Error Handling

* **Task:** Implement robust exception handling across the RAG pipeline.
* **Requirements:** The endpoint must gracefully catch and return appropriate HTTP status codes and user-friendly messages for:
* `LLM failure`
* `Embedding/retrieval failure`
* `Redis unavailable`
* `Database failure`
* `Celery unavailable`
* `Invalid conversation ID`
* `Empty question`
* `Request timeout`


* **Action:** Add these try/except blocks and custom error responses. Wait for my approval.

#### Step 6.7: Tracing & Telemetry

* **Task:** Enhance our existing tracing to capture detailed execution metrics for every request.
* **Requirements:** Log or store the following exact payload structure:
* `request_id`
* `conversation_id`
* `total_latency`
* `rewrite_latency`
* `filter_latency`
* `multi_query_latency`
* `retrieval_latency`
* `rerank_latency`
* `LLM_TTFT` (Time To First Token)
* `LLM_total_latency`
* `cache_hits_misses`
* `retrieval_candidate_count`
* `model_used`
* `input_output_tokens`
* `cost`


* **Action:** Implement the tracing middleware or decorator. Wait for my approval.

---

### PHASE 7: Production Hardening

*(Do not begin Phase 7 until Phase 6 is entirely complete and approved).*

#### Step 7.1: Rate Limiting, Timeouts, & Retry Policy

* **Task:** Protect the endpoint from abuse and transient network failures.
* **Requirements:**
* Utilize existing services (e.g., `@backend/app/services/rate_limit.py`) to apply rate limits to the `/rag/chat` endpoint.
* Implement strict request timeouts.
* Implement exponential backoff/retry policies for downstream calls (like LLM or Redis connections).


* **Action:** Integrate these policies and present the updated code. Wait for my approval.

---
---

## DECISIONS LOG

Answers to design questions raised during implementation, recorded here so
they survive across sessions and are not re-litigated. Append a new entry
whenever a blocking question is settled.

### D1 — `BaseMemory` becomes async (Step 6.1/6.2)

**Question:** `BaseMemory` is synchronous (`add`, `messages`, `get_state`,
`update_state`, `clear`) and `RAGService` calls all of them without `await`.
A Postgres-backed memory needs `await`. Change the contract, or keep it sync
and persist outside the memory?

**Decision:** Make `BaseMemory` async.

**Consequences:**
- `BaseMemory` abstract methods become `async def`.
- `InMemoryMemory` becomes async (bodies unchanged, signatures awaited).
- `RAGService.ask()` awaits 4 call sites: `messages()`, `get_state()`,
  `update_state()`, `add()` (twice).
- `ReferenceResolver.resolve()` stays sync — it is pure logic over a
  `ConversationState` already in hand, it never touches storage.

### D2 — Conversation state persisted as a JSON column (Step 6.1/6.2)

**Question:** persist only the messages, or the `ConversationState` too?

**Decision:** Store `ConversationState` as a JSON column on the conversation
row, alongside the messages table.

**Rationale:** `last_result_ids` is what makes reference follow-ups work
("and the low priority ones?" scopes retrieval to the previous turn's
entities). Persisting messages without it means a reloaded conversation
answers follow-ups against the whole corpus instead of the referenced set.

**Shape:** conversation row carries `state` (JSON, defaults to an empty
`ConversationState`); messages live in a child table with role, content and
timestamp.

### D3 — RAG retrieval is scoped to project visibility (Step 6.4 follow-on)

**Question:** the roadmap defers "granular resource-level blocking", but the
RAG corpus spans every issue while the REST API enforces per-project
visibility. A `viewer` can therefore ask the chatbot about projects they
cannot open directly.

**Decision:** implement visibility scoping now rather than later, because the
gap is exploitable through the chatbot.

**Rule to mirror** (same as `_can_view_project` in `routes/projects.py`):
admin sees everything; everyone else sees projects they lead
(`Project.leader_id`) or belong to (`project_members` row).

**Approach:** enforce it *inside retrieval*, not as a post-filter, so the
model never receives documents the user may not see.

- `AccessScope` (`user_id`, `is_admin`) in `app/rag/filtering/schemas.py`.
- `build_access_conditions()` in `app/rag/filtering/conditions.py`, alongside
  the existing `build_conditions()`. Returns a SQL **subquery** condition
  (`RagDocument.entity_id.in_(select(Issue.id).where(...))`) rather than a
  materialised id list, which would be unbounded.
- Threaded like the existing `filters` / `entity_ids` params:
  `BaseRetriever.search(..., access=...)` -> `PGVectorRetriever`,
  `RagDocumentRepository.keyword_search`, `HybridRetriever`.
- `QueryRequest.access` carries it into `SearchStage`.
- `RAGService.__init__(access=...)`, built per request in `rag_helper`.
- Rows whose `entity_type` is not `issue` are excluded when a scope is
  present: deny-by-default, since a future entity type needs its own rule.

**CRITICAL:** the search-stage cache key MUST include the access scope.
`rag:search:*` entries are keyed on query+filters+entity_ids today; without
the scope, one user's cached results would be served to another — a worse
leak than the one being fixed.

---

## PROGRESS

- **6.1 & 6.2 — DONE, approved.** `conversations` + `conversation_messages`
  tables (UUID pk, JSONB `state`), migration `ab83738a90d3`,
  `conversation_helper.py`, `PostgresMemory`, `BaseMemory` made async.
- **6.3 & 6.5 — DONE, approved.** `routes/rag.py` with `POST /rag/chat`
  (SSE streaming), `GET /rag/conversations`,
  `GET /rag/conversations/{id}/messages`. `RAGService` split into
  `_prepare` / `_finalise` so `ask()` and `ask_stream()` share one path.
- **6.4 — DONE, approved.** `require_rag_access` in `rbac.py` (all roles may
  read; adds the `is_active` check that `get_current_user` lacks).
  Two bugs fixed: the stream now opens its own session (FastAPI closes
  `yield` deps before the streaming body runs), and `pool_pre_ping=True`
  guards against abandoned streams poisoning pooled connections.
- **D3 visibility scoping — DONE, awaiting review.** Implemented exactly as
  designed above. `AccessScope` + `build_access_conditions()`; `access`
  threaded through `BaseRetriever.search` -> `PGVectorRetriever` /
  `HybridRetriever` / `keyword_search` (both the AND and OR passes),
  `QueryRequest.access`, `RAGService(access=...)`, `build_access_scope(user)`
  in `rag_helper`, resolved in the route while `current_user` is still
  attached. The search cache key now carries `"access"`; unscoped and admin
  requests share a key because they run the identical query.

  Verified: rendered SQL is a subquery, not an id list; cache keys differ per
  user and are stable per user; a developer in one project retrieves only that
  project while an admin reaches 33; end to end, "session tokens dropped or
  not invalidated" returns 5 issues from 5 projects to the admin and only
  `issue:2720` to the developer — none of the 59 corpus-wide
  "Session token not invalidated on logout" issues leaked.

  Downstream caches were checked for the same class of leak: `rag:rerank:*`
  keys on a fingerprint of the candidate set, so a shared key implies
  identical candidates; the filter and multi-query caches hold no documents.
- **6.6 — DONE, awaiting review.** `app/rag/exceptions.py`: `RagError` base
  (`status_code` / `code` / `message`) with `EmptyQuestionError` 400,
  `RetrievalError` 503, `LLMError` 503, `DatabaseError` 503,
  `PersistenceError` 500, `RagTimeoutError` 504, plus `translate(exc,
  fallback)` which classifies by exception type first and by phase second.

  Errors split by *when* they happen, because a stream cannot change a status
  line it has already sent:
  - before the response starts -> real HTTP status, via the `RagError`
    handler in `main.py`
  - after -> an SSE `{"type": "error", "code", "message"}` event

  `RAGService` classifies by phase: `_prepare` wraps `_build_turn`
  (retrieval), the two generation loops wrap the LLM, `_finalise` wraps
  `_record_turn` (persistence). Each is a thin wrapper so the existing bodies
  did not have to be reindented. `except Exception` deliberately, so
  `GeneratorExit` / `CancelledError` from a client hanging up are not
  reported as model failures.

  `RAG_REQUEST_TIMEOUT_SECONDS` (120) caps a whole turn via
  `asyncio.timeout` in the stream body. Step 7.1 adds per-downstream
  timeouts underneath it.

  Verified by forcing every mode: `llm_unavailable` (0 deltas),
  `retrieval_unavailable` (0), `database_unavailable` (0),
  `not_persisted` (88 deltas — answer delivered, write failed),
  `timeout` (11 deltas), and pre-stream 400 / 404 / 422 / 401.
  Redis stopped -> the request still answers, uncached.
- **Next:** 6.7 telemetry, then Phase 7.

### 6.6 findings worth keeping

- **A database outage is not a `SQLAlchemyError`.** asyncpg raises at the
  socket layer before SQLAlchemy's DBAPI wrapping, so a stopped Postgres
  arrives as `socket.gaierror` and a closed port as `ConnectionRefusedError`
  — both plain `OSError`s. `translate()` and the `main.py` handler cover all
  three shapes; registering on `OSError` wholesale was rejected so a real
  file-I/O bug still surfaces as a 500.
- **The RAG router cannot catch its own database failures.** With Postgres
  down the request dies in `get_current_user` (`app/api/deps.py:47`), which
  runs before any route body. That is why the handler is registered app-wide
  rather than on the router — it changes every route's behaviour, deliberately.
- **`min_length=1` was removed from `RagChatRequest.question`.** It made `""`
  a pydantic 422 blob while `"   "` got the clean 400. The route trims and
  rejects both identically now.
- **Celery is not in the `/rag/chat` path at all.** The roadmap lists
  "Celery unavailable" under 6.6, but a chat request never enqueues a task —
  Celery serves attachments, auth email and the background embedding refresh.
  An unavailable worker means embeddings go stale, not that a chat fails, so
  no handler was written for it. Revisit if a RAG route ever enqueues work.

### Standing gotchas

- `alembic revision --autogenerate` proposes dropping `idx_rag_documents_fts`,
  `uq_rag_document_entity_chunk` and both `ix_issue_assignees_*` indexes —
  they come from hand-written migrations and are absent from the models.
  Strip those lines from every generated migration.
- `migrate`, `celery-beat` and `flower` build their own images. Use
  `docker compose build` with no service name when dependencies change.
- `get_current_user` does not check `is_active`; only the RAG routes do.
