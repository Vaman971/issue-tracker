
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
