
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

---

## PHASE 8 — SCOPE CONTROL

### 8.1 — RouterStage (DONE, awaiting review)

**Problem:** the pipeline was unconditionally retrieval-first, so "Hello how
can you help me?" was embedded like any other query, retrieval returned its
five nearest neighbours (there is always a nearest neighbour), and `answer.j2`
listed them. The answer prompt could not be the fix — it deliberately says
"Never refuse merely because the context is incomplete", which is the
behaviour the retrieval tuning depends on.

**Approach:** intent routing before retrieval, the standard pattern (search
terms: query routing, intent classification, `semantic-router`, LlamaIndex
`RouterQueryEngine`). Not guardrails frameworks (new dependency) and not
agentic tool-calling (a pipeline rewrite).

`app/rag/routing/` mirrors `app/rag/filtering/` exactly — `schemas.py`,
`base.py`, `deterministic.py`, `openai_router.py`, plus `responses.py`.
`RouterStage` runs first and is structured like `FilterStage`: deterministic
pass, LLM fallback, cache over the fallback.

**Four intents, four outcomes:** `KNOWLEDGE` runs the pipeline unchanged;
`CAPABILITY`, `ACKNOWLEDGEMENT` and `OUT_OF_SCOPE` are answered from **fixed
strings** in `routing/responses.py`. Static on purpose — "what can you do?" has an answer
the product's author owns, and letting the model improvise it invites a
confident description of features that do not exist. Zero cost, zero latency,
cannot be prompt-injected.

**How the pipeline stops:** one `break` in `QueryPipeline.process` when
`processed.intent` is not `KNOWLEDGE`. No new abstraction, no per-stage
`should_run` edits. `ProcessedQuery.intent` defaults to `KNOWLEDGE`, so
`scripts/chat.py` and the eval harness — which build their own pipeline with
no router — behave exactly as before.

**Two decisions that matter:**

- **Follow-ups are settled deterministically, before any LLM call.** A
  fragment like "and the critical ones?" carries almost no topic of its own,
  and a classifier reading it alone will call it chitchat — silently breaking
  reference resolution. `route_deterministic` checks
  `REFERENCE_PATTERN` / `CONTINUATION_PATTERN` (reused from
  `reference_resolver`, so the router and the resolver cannot disagree) and
  returns `KNOWLEDGE` when there is history. This is also why the route cache
  can key on the message alone: the history-dependent case never reaches it.
- **A routed turn returns before `update_state`.** `last_result_ids` is what
  makes follow-ups work; a greeting has no results, so writing state would
  throw away the reference context the next real question needs. Verified:
  question -> "thanks!" -> "and the critical ones?" still scopes to the first
  turn's five results and returns the three critical ones.

**Every failure degrades to the old behaviour.** Unparseable JSON, an unknown
label, or no router configured all resolve to `KNOWLEDGE`. A broken
classifier costs a search, not a refused question.

**Measured:**

| turn | latency | cost |
|---|---|---|
| "Hello how can you help me?" | 72ms | **$0** (deterministic) |
| "thanks" | 20ms | **$0** |
| "i had a breakup last week..." | 4.5s | $0.00073 (was ~$0.009) |
| real question | 15.6s | $0.0097, of which routing $0.00069 |
| follow-up | 5.6s | routing $0 |

So routing costs real questions about **7% more**, and makes junk questions
free or near-free. 17 deterministic cases pass, including the ones that must
NOT be swallowed ("hi, which issues are blocked?" goes to the LLM, not to a
greeting reply).

**`ACKNOWLEDGEMENT` (added after review).** "thanks" used to get the full
capability description, which reads as a non sequitur right after the
assistant answered something. Three patterns now, checked in this order:

1. `CAPABILITY_PATTERN` — first, because "help" is a capability question
   while "hi" is not, and a looser ordering would let the shorter pattern win
2. `GREETING_PATTERN` — "hi", "good morning". Deliberately still answered
   with the CAPABILITY reply: someone who has just said hi is about to ask
   what this thing does, so orienting them is the right move
3. `ACKNOWLEDGEMENT_PATTERN` — "thanks", "ok", "got it", "perfect", "bye" ->
   "You're welcome. Tell me what else you would like me to find…"

The label is in `route_query.j2` too, so "thanks, that was really helpful" —
which no regex will fullmatch — is classified rather than treated as a
question.

23 deterministic cases pass, including the collisions that matter:
"thanks, now show me critical bugs" and "ok what about the payments project"
go to the LLM rather than being swallowed, and "ok, and the high priority
ones?" with history is still KNOWLEDGE.

### 8.2 — ConfidenceGateStage (DONE, awaiting review)

**Problem the router cannot solve:** a question that genuinely belongs to
this system, about something the corpus has no answer for. Vector search
always returns its nearest neighbours, so the answer prompt got five
unrelated issues and listed them.

**The score had to be recovered first.** `RerankStage` did
`processed.results = [item.result for item in reranked.results]`, which drops
`RerankResult.score` — `SearchResult.score` is the RRF value, not a relevance
judgement. `ProcessedQuery.top_relevance` now carries it.

**The trap that would have caused a regression:** when the reranker's JSON
cannot be parsed it falls back to passing candidates through in retrieval
order, and their scores are RRF values (~0.03). Gating on those would refuse
a perfectly good answer every time the reranker hiccuped. So
`RerankResponse.model_scored` records whether the model judged anything, and
`top_relevance` is **None** when it did not. The gate treats None as "no
evidence", not "bad evidence", and stays out of the way.

**Threshold measured, not guessed:**

| | top score |
|---|---|
| six questions with real matches | **0.74 – 0.99** |
| six plausible questions with nothing in the corpus | **0.06 – 0.18** |

`RAG_MIN_RELEVANCE_SCORE = 0.35` sits in that gap with about a factor of two
of headroom either side. **Re-measure before changing the reranker's model or
prompt** — the scores are that model's opinion and nothing more.

`ConfidenceGateStage` runs last, after consolidation, so it judges exactly
the set the answer model would have received. `NO_MATCH_REPLY` lives in
`routing/responses.py` with the other fixed replies — it is not a routing
intent, but that module is where every reply that skips the answer model
lives, and one file of user-facing copy beats a tidier import graph.

**Verified:** 3 relevant questions answered, 3 irrelevant declined, none
wrong. A declined turn shows `LLM_total_latency: 0` — the answer model is
never called. A *repeated* irrelevant question costs **26ms and $0**: the
search cache returns the empty set and the gate fires before anything runs.

**Gating is a correctness win, not a cost win.** A first-time declined turn
still pays for retrieval and reranking — about $0.009 of a $0.0096 turn —
because rerank is where the money goes. Only the ~$0.0005 answer call is
saved.

**Telemetry gained `retrieval_top_score` and `route_latency`,** both
extensions to the agreed payload. The first is the number the threshold is
tuned against and cannot be recovered from the rest; the second was simply
missing after 8.1 added a stage.

### 8.3 — Reranker latency (DONE, awaiting review)

**The prompt was not the problem.** Eight calls with byte-identical input
returned byte-identical output (323 tokens, 0 reasoning) in **3.49s to
59.95s** — 92.6 tok/s against 5.4 tok/s for the same work. Output length,
candidate count and reasoning effort were all ruled out by measurement:

| lever | effect |
|---|---|
| top_k 3 -> 15 (117 -> 472 output tokens) | 3.97s -> 4.16s, i.e. none |
| candidates 5 -> 15 (919 -> 1887 input tokens) | 2.25s -> 4.10s, mild |
| same input, repeated | **3.49s -> 59.95s** |

**The tail is the API stalling.** Proven by disabling retries: an attempt
timed out at exactly **30.04s**, the per-attempt budget. So a stall in
production cost 30s before the retry even began, and 30 + 30 explains the
59.95s.

**Fix: size the timeout to the operation.** `build_openai_client(timeout=…)`
now takes an override, and `OPENAI_STRUCTURED_TIMEOUT_SECONDS` (10s) applies
to the five adapters that return a short JSON payload — router, rewriter,
filter, multi-query, reranker. The answer model and the embedder keep the 30s
default; the answer model streams, so its time is spent producing tokens the
user is already reading.

**Measured, 14 paced calls each:**

| | median | worst |
|---|---|---|
| 30s budget (before) | 4.97s | **59.95s** |
| 10s budget (after) | 3.75s | **13.88s** |

The median is untouched — normal calls never approach either budget. A stall
now costs 10s plus a ~4s retry instead of 30s plus a retry.

**Caveat worth remembering:** a cut attempt may still be billed for whatever
the server generated, so a stall that retries twice could cost up to three
reranks. Rerank is already the dominant spend, so if the bill looks wrong,
look here first.

**Not yet done:** nginx's `proxy_read_timeout` is 60s and
`RAG_REQUEST_TIMEOUT_SECONDS` is 120s. The worst turn measured before this
fix was 67.9s, which nginx would have cut. The fix makes that far less
likely but does not align the two numbers.

### 8.4 — Eval harness re-baselined, and the reranker model changed (DONE)

**The harness had silently drifted.** It retrieved `SEARCH_TOP_K = 30` and
fused at `k = 60` long after production moved to 15 and 30, so every number
it printed described a pipeline that no longer existed. The constants are now
**imported** — `rag_helper.SEARCH_TOP_K`, `settings.DAMPING_CONSTANT`,
`settings.RAG_MIN_RELEVANCE_SCORE` — so the harness follows production by
construction instead of by memory. That is the fix that matters; the numbers
below will drift again otherwise.

**Ground truth re-verified** before trusting anything: all 15 distinct
expected ids still exist in `issues` AND in `rag_documents` with
`is_active`. A dataset pointing at deleted or unindexed rows would have
invalidated the whole run silently.

**Two additions:**
- the confidence gate is now a measured layer, because a case can score
  perfectly and still be declined in production. Any declined case that the
  reranker got right is printed as `WOULD LOSE A CORRECT ANSWER`.
- a rerank failure no longer aborts the run. With a 10s structured timeout a
  sustained stall exhausts the retries and raises; one bad call used to throw
  away the other 22 cases. It now falls back to fused order, is counted, and
  is reported so a degraded run is never read as a good one.
- `--rerank-model` runs the sweep against a different model without editing
  settings.

**Current baseline (23 cases, production config):**

| layer | recall@5 | prec@5 | hit@5 | misses |
|---|---|---|---|---|
| RRF k=30 | 0.957 | 0.209 | 1.000 | 0 |
| Reranker | **1.000** | 0.226 | 1.000 | 0 |
| Answer | **0.978** | **0.949** | **1.000** | 0 |

Gate: **0/23 declined**, top score min 0.98. The 0.35 threshold has enormous
margin against real questions — which is the evidence that it is safe.

**The reranker now runs `gpt-5-mini`** (`OPENAI_RERANK_MODEL`). Measured, not
assumed: mini matched `gpt-5` exactly on reranking (recall@5 1.000, 0 misses,
the same two multi-target rescues) and was marginally better end to end
(answer hit@5 1.000 against 0.957, one fewer miss).

| | before | after |
|---|---|---|
| rerank cost | $0.0058 | **$0.001265** |
| total cold turn | $0.0092 | **$0.005356** |

A **42% cut** in the cost of a turn.

**Caveat, and why this is a separate setting:** mini returned one unparseable
response in 23. The reranker already falls back to retrieval order there, and
the gate treats an unscored result as no evidence rather than bad evidence,
so it is contained — the run with that failure still scored answer hit@5
1.000. `OPENAI_CHAT_MODEL` is untouched: the other four stages that use it
were not measured here.

**Evals do not use Redis, and now do not touch it at all.** Only two stages
in the eval path cache — `FilterStage` and `MultiQueryStage`. The harness
builds its own retriever with an uncached embedder and calls the reranker
directly, so nothing else was ever involved.

`CACHE_ENABLED` (new, in `app/core/config.py`) short-circuits all four
functions in `app/services/cache.py`, and the runner sets it False unless
`--cache` is passed. Two reasons, and the second is the important one:

- Running the harness from the host rather than inside Docker cannot resolve
  the `redis` hostname, so every lookup paid a DNS failure and logged a stack
  trace. Measured against an unresolvable host, one get plus one set cost
  **3.70s** with caching on and **0.00s** with it off.
- **A benchmark that reads a cache is not measuring the code under test.** A
  filter or expansion cached under an older prompt survives the prompt change
  and quietly invalidates the comparison. Disabling it also stops eval
  queries writing into the cache the application shares.

Consequence worth knowing: every run now makes fresh filter and multi-query
calls, so a run costs more and `search_queries` vary slightly between runs.
That is the correct trade for a benchmark.

**How to re-run:**

    python -m scripts.rag_eval.runner --answer
    python -m scripts.rag_eval.runner --answer --rerank-model gpt-5
    python -m scripts.rag_eval.runner --k 60 30 20 10
    python -m scripts.rag_eval.runner --cache          # opt back into caching

**Standing note:** the admin password resets to `SEED_ADMIN_PASSWORD`
(`admin12345`) on a backend restart, so a test script that reset it will fail
with 401 afterwards.

---

## FRONTEND

Complete and approved. Both steps below are done.

### F1 — `ragApi.js` (DONE, approved)

`frontend/src/store/features/rag/ragApi.js`. `getConversations` and
`getConversationMessages` are ordinary RTK Query endpoints.
`sendChatMessage` is not, and cannot be.

**Why chat needs `queryFn`:** `/rag/chat` is `text/event-stream`, and
`fetchBaseQuery` reads a response to completion before handing it over.
Routing chat through it works but surrenders streaming — the answer appears
at once after ~15s instead of the first token after ~2s.

**What a manual fetch loses, and how it was restored:** `fetchBaseQuery` was
attaching the token and refreshing on 401. `refreshAccessToken` was extracted
in `store/api.js` and `baseQueryWithRefresh` now uses it too, so there is one
place that knows the token keys and the logout-on-failure rule. Without this,
chat would be the single call that fails on an expired token (15 min) while
every other call quietly refreshes.

**`onDelta` and the serializable check:** the chat mutation takes an
`onDelta` callback so tokens can render as they arrive. RTK puts a mutation's
args into the action, and a function is not serialisable, so `store.js`
exempts `meta.arg.originalArgs.onDelta`. When a `ragSlice` exists, dispatch
deltas into it instead and remove both the callback and the exemption.

### F2 — `RagChatWidget` (DONE, approved)

`frontend/src/components/RagChatWidget/` (`page.jsx` + `page.module.css`,
matching the folder convention every other component uses).

**Mounted in `app/(protected)/layout.jsx`, inside `ProtectedRoute`** — so it
exists on every signed-in page and none of the public ones, with no auth
check of its own. Rendered through `createPortal` to `document.body`, like
`NotificationDrawer`.

**Deliberately not a modal.** No backdrop and no body-scroll lock, unlike the
notification drawer: it is a small floating window, so the app stays visible
and usable while it is open. z-index 900/901, below the drawer's 1000/1001,
so opening notifications covers it rather than the two fighting.

**Design** follows `NotificationDrawer` exactly — `#111827` header, `#f4f6f9`
body, `#2563eb` primary, `#e5e7eb` borders, 0.15s transitions — so the two
read as one product.

**Behaviour:** streams tokens via the mutation's `onDelta`; `streamingText`
is kept separate from `messages` so a half-written reply is never mistaken
for a finished one. A thinking indicator covers the gap before the first
token (retrieval, ~2s warm and ~15s cold). `conversationId` is held in
component state and sent back, so follow-ups resolve references against the
same conversation. Errors show the backend's own user-facing message; a
`not_persisted` failure still renders its answer, because that answer was
generated and delivered and only the write failed.

**Persistence and history (added after review):**

- The active `conversation_id` is kept in `localStorage`
  (`ragActiveConversationId`), so a reload reopens the same conversation.
- **The saved transcript is the source of truth** for a conversation that
  exists server-side: `useGetConversationMessagesQuery` hydration *replaces*
  the local copy rather than merging. The two cannot disagree, since every
  turn goes through this component, and replacing is self-correcting.
- **Hydration is suppressed while a send is in flight.** The refetch that a
  completed send triggers (`invalidatesTags` on `ConversationMessage`) would
  otherwise land mid-stream and wipe the question the user just asked. This
  is the subtle one — if messages ever flicker or vanish during streaming,
  look here first.
- Messages carry a `key`: the server row id once saved, a local counter
  before that. Index keys broke React's reconciliation across the hydration
  swap.
- A stored id can outlive its conversation (deleted, or a different account
  signed in). A 404 from the transcript query clears the stored id and starts
  fresh rather than leaving the widget stuck.
- "New chat" clears the id, so the next question makes the backend create a
  conversation. "History" lists the last 20, most recently active first, with
  the open one marked the way the drawer marks unread notifications.
- Both queries are `skip`-ped while the panel is closed, and the history
  query also while the chat view is showing, so an unopened widget costs
  nothing.

**Not verified by me:** how it looks and feels in a browser. Confirmed only
that it lints, compiles into the `(protected)/layout` chunk without errors,
and that every endpoint it calls returns the expected shape through the real
browser path (nginx + `/api`), including 404 for an unknown conversation.

### Frontend gotchas

- **SSE chunk boundaries do not align with frames.** The parser buffers and
  cuts completed frames off the front. Verified against six chunkings
  including one byte at a time, a split exactly between the two newlines of a
  separator, and a multi-byte UTF-8 character straddling a chunk (handled by
  `TextDecoder({ stream: true })`). Change that function only with those
  cases in mind.
- **nginx `/api/` proxies straight to the backend**, not through the Next
  rewrite. The Next rewrite only applies when hitting Next directly in dev.
- **Streaming does survive nginx** — measured 217 deltas over a 1.82s spread
  through the browser path. nginx *consumes* `X-Accel-Buffering` rather than
  forwarding it, so its absence downstream is normal and is NOT evidence of
  buffering. Judge buffering by delta spread, and only on a long answer: a
  short answer has too few deltas to tell.
- **nginx `proxy_read_timeout` is 60s, `RAG_REQUEST_TIMEOUT_SECONDS` is
  120s.** It resets per read, so a flowing token stream is safe, but the gap
  before the first token is one read. A bad cold turn could be cut by nginx
  before the backend's own ceiling fires, and the client would see a
  truncated stream instead of the `timeout` error event. Not yet aligned.
- **`injectEndpoints` registers on import**, so a feature's endpoints only
  exist once something imports one of its hooks.

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
