
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

### D4 — /rag/chat rate limit stays at 10 per minute per user (Step 7.1)

**Question:** 10 requests per 60s was a guessed default, not a measured one.
Is it right?

**Decision:** keep it.

**Rationale:** a normal user asks through a UI that waits for the answer, and
a turn costs 2-3s warm and 15s+ cold, so a sequential client cannot
realistically approach 10/min. For an attacker the cap is sufficient on its
own.

**Caveat worth remembering:** pipeline latency only throttles a *sequential*
client. Concurrent requests do not wait for one another, so an attacker can
spend the whole minute's budget at once — the protection is the limiter, not
the latency. 10 concurrent cold turns is a bounded burst, which is the
intended behaviour.

**Still open:** the limiter fails open when Redis is unreachable, matching the
rest of the RAG path. Anyone who can take Redis down lifts the cap.

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
- **6.7 — DONE, awaiting review.** `app/rag/tracing/telemetry.py`:
  `TelemetryRecord` carries the roadmap's exact keys (`LLM_TTFT` and
  `LLM_total_latency` included, odd casing and all — they are a contract with
  the log consumer). `build_record(trace, request_id, conversation_id)`
  flattens `RAGTrace`; `emit()` logs it via
  `extra={"telemetry": {...}}`, and `JsonFormatter` was extended to nest that
  as an object instead of dropping it.

  `RAGService` gained `request_id` and `conversation_id` (telemetry only) and
  calls `emit()` at the end of `_record_turn`, right after
  `TracePrinter.print`, so `total_duration_ms` is already set.

  **The request id has the same lifecycle trap as the session.** The logging
  middleware resets `request_id_context` when the handler returns, which for
  a streaming response is before any work happens. The route reads it with
  `request_id_context.get()` and passes it in, exactly as it does for
  `AccessScope`. Verified: a client-supplied `X-Request-ID` reaches the
  record.

  Verified cold vs warm on the same question: 17916ms -> 4131ms total,
  `search` cache 0/4 hits -> 4/0, filter/multi_query/rerank all false ->
  true, and `rerank_usd` correctly 0 on the cached turn.

### 6.7b — complete token and cost capture (DONE, awaiting review)

Closed the "cost is a floor" gap before first release, so debugging and
pipeline tuning have real numbers.

- `app/rag/llm/usage.py` — `read_usage(response, model)`. One reader instead
  of the same four-way ternary in five adapters. Also fixes a latent
  `AttributeError`: the reranker reached straight into
  `usage.output_tokens_details.reasoning_tokens`, which is absent on some
  responses.
- `LLMUsage` gained `reasoning_tokens`. It is a **subset** of `output_tokens`,
  not an addition — the Responses API bills reasoning as output, so cost must
  not count it twice. `estimate_cost` therefore still takes input + output.
- `RewriteResult`, `FilterResult` and `ExpansionResult` each carry a `usage`.
  Their adapters read it **before parsing**, because a call is billed whether
  or not its output turns out to be readable.
- `RewriteTrace`, `FilterTrace`, `MultiQueryTrace` gained model / tokens /
  cost, matching `RerankTrace`. `app/rag/tracing/usage.py` —
  `record_usage(trace, usage)` copies and prices in one place, typed with a
  `Protocol` so `slots` dataclasses need no base class.
- Stages record **on a cache miss only**, matching the rerank precedent: a
  hit, a skip and the deterministic filter path all leave zero, so summing a
  conversation never charges twice for work done once.
- `telemetry._cost` and `telemetry._tokens` now cover all five stages, each
  with a `by_stage` split carrying its own model (stages run `gpt-5`, the
  answer runs `gpt-5-mini`).

**Measured:** a cold turn is **$0.009186**, against the $0.006309 reported
before — the old figure understated by about 31%. Rerank is still the
dominant cost ($0.0058). A warm turn is $0.000428, answer model only.

`reasoning_tokens` reads 0 throughout because `OPENAI_REASONING_EFFORT` is
`minimal`. Verified as real rather than broken: the same reader returns 640
against a `medium`-effort call, matching the raw payload.

**Note:** `TracePrinter.print(trace)` is commented out in `_record_turn`
("emit serves the purpose"). The per-stage cost lines added to the printer
are dormant until that is uncommented, and `TracePrinter` is an unused import
in `rag_service.py` while it stays that way.

### 6.7 gaps, deliberate
- **Telemetry is emitted on success only.** A failed turn never reaches
  `_record_turn`. Emitting a partial record would be worse than none: with no
  error field in the agreed payload, a failure would look identical to a
  cheap cache-heavy success. Adding `status` / `error_code` to the payload is
  the fix, and it changes the agreed structure, so it needs a decision.
- **`rewrite_latency: 0.0` is ambiguous** — it means "skipped" far more often
  than "ran instantly", because `should_run` skips self-contained questions.
  Averaged across requests this understates the real rewrite cost. The trace
  has `skipped` flags; surfacing them would extend the payload.
- **7.1 — DONE, awaiting review.**

  *Rate limiting.* `_enforce_chat_rate_limit` in `routes/rag.py` reuses
  `services/rate_limit.py`. Keyed on `user.id`, not client IP — the endpoint
  is authenticated and each call spends real money. Not reset on success,
  unlike login: there a reset stops a user being locked out by their own
  typos, here every request is a genuine cost. `RAG_RATE_LIMIT_MAX_REQUESTS`
  10 per `RAG_RATE_LIMIT_WINDOW_SECONDS` 60. Fails open when Redis is down,
  matching how the rest of the RAG path treats an unavailable cache.
  Verified: 13 requests -> 10 accepted, 3 rejected, first 429 at #11, and a
  second user is unaffected while the first is blocked.

  *Ordering.* Question validation runs BEFORE the limiter: rejecting a blank
  question reaches no model, and the limit is justified by cost. The
  conversation lookup stays after it, since that is a real database query.

  *One OpenAI client.* `app/rag/llm/client.py` — `build_openai_client()`.
  All six adapters (answer, embedder, reranker, rewriter, filter,
  multi-query) built their own bare `AsyncOpenAI`, so a policy would have had
  to be set in six places and would drift. Timeout and retries now live in
  one place.

  *Retry policy is the SDK's, deliberately.* It is already exponential
  backoff with jitter over exactly the right failures. Proven rather than
  assumed, against a local server: a 503 makes 3 attempts over 2.16s, a 400
  makes 1 attempt in 0.01s. A hand-rolled loop would duplicate it and retry
  the errors it deliberately does not.

  *Timeouts.* `OPENAI_TIMEOUT_SECONDS` 30 x `OPENAI_MAX_RETRIES` 2 = 90s
  worst case per call, sized to fit inside the 120s
  `RAG_REQUEST_TIMEOUT_SECONDS` turn ceiling. `DB_CONNECT_TIMEOUT_SECONDS`
  10 via `connect_args` — a connect timeout, NOT a command timeout, because
  ingestion runs long statements through the same engine.

### 7.1 findings worth keeping

- **The first retry config made a Redis outage 3x worse.** 2 retries against
  the reused 3s healthcheck timeout took a turn from 15s to 77s with Redis
  down. A turn touches the cache dozens of times, so every second spent
  failing is multiplied.
- **But the realistic outage is nearly free.** Measured per failed lookup:
  host resolves / port closed (a crashed Redis, the production case) 0.01s;
  host does not resolve (a removed container, mostly dev) 0.50s, bounded by
  `REDIS_CONNECT_TIMEOUT_SECONDS`. The 77s was DNS resolution for a stopped
  container, not connection cost. That measurement is why there is **no
  circuit breaker** — the retry chain is already bounded where it matters.
- **Redis needs its own timeouts, and connect is not command.** First split
  from `REDIS_HEALTHCHECK_TIMEOUT_SECONDS` (3s, fine for a readiness probe,
  far too long for a per-lookup cost) to a single 0.5s value — which then
  timed out against a **healthy** Redis from a cold-start script, because
  establishing a connection includes DNS and that can exceed a second on a
  cold process in Docker. Now two budgets:
  `REDIS_CONNECT_TIMEOUT_SECONDS` 2.0 (paid once per connection, covers DNS)
  and `REDIS_COMMAND_TIMEOUT_SECONDS` 0.5 (paid per lookup), with 1 retry.
- **No DB retry, on purpose.** A retried write could double-write, and
  `pool_pre_ping=True` already covers the stale-connection case that a retry
  would otherwise catch.
- **Next:** Phase 7 beyond 7.1, if any. Phase 6 and 7.1 are otherwise complete.

### Cost observation worth remembering

On a cold turn the reranker costs roughly ten times the answer model
($0.0058 vs $0.0005). If cost becomes a concern, rerank is the lever.

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
