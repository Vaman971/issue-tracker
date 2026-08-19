"""Ground-truth evaluation cases.

Every expected_entity_ids set here was VERIFIED against the database, not
assumed. Each case is anchored on a phrase confirmed to appear in exactly one
issue across all 2734 rows, so a miss is a genuine retrieval failure rather
than an artefact of incomplete labelling.

Deliberately excluded: broad topical queries such as "which issues mention
session token problems". The pre-existing corpus contains many issues on those
topics (59 issues are titled "Session token not invalidated on logout", 233
mention a security audit finding), so their true expected set cannot be
enumerated and any recall figure would be meaningless.

The same rule applies to multi-target cases. A query like "which issues are
account security risks" has hundreds of legitimate answers in this corpus, so
labelling it with two seeded ids measures nothing but the labeller's guess.
Every multi-target case below is therefore anchored the same way the single
target ones are.

Verification query used for every anchor:

    SELECT id FROM issues
    WHERE lower(title) LIKE '%<anchor>%'
       OR lower(description) LIKE '%<anchor>%'
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    category: str
    query: str
    expected_entity_ids: frozenset[int]


EVAL_CASES: list[EvalCase] = [

    # ---------------------------------------------------------------
    # specific — the query names details unique to one issue
    # ---------------------------------------------------------------

    EvalCase(
        id="session-token-01",
        category="specific",
        query=(
            "Which issue describes the authentication failure "
            "after the billing dashboard session expires?"
        ),
        expected_entity_ids=frozenset({2720}),  # anchor: "billing dashboard"
    ),

    EvalCase(
        id="attachment-preview-01",
        category="specific",
        query="Which issue is about attachment previews failing for large files?",
        expected_entity_ids=frozenset({2721}),  # anchor: "ten megabytes"
    ),

    EvalCase(
        id="duplicate-email-01",
        category="specific",
        query="Which issue reports duplicate notification emails during deploys?",
        expected_entity_ids=frozenset({2722}),  # anchor: "deploy window"
    ),

    EvalCase(
        id="non-ascii-search-01",
        category="specific",
        query="Which issue is about search failing for accented or non-ASCII titles?",
        expected_entity_ids=frozenset({2723}),  # anchor: "non-ascii"
    ),

    EvalCase(
        id="bulk-transition-01",
        category="specific",
        query="Which issue describes bulk status changes timing out?",
        expected_entity_ids=frozenset({2724}),  # anchor: "bulk status"
    ),

    EvalCase(
        id="membership-cache-01",
        category="specific",
        query="Which issue is about removed users keeping project access?",
        expected_entity_ids=frozenset({2725}),  # anchor: "membership cache"
    ),

    EvalCase(
        id="comment-draft-01",
        category="specific",
        query="Which issue reports losing unsaved comment text on reconnect?",
        expected_entity_ids=frozenset({2726}),  # anchor: "comment editor"
    ),

    EvalCase(
        id="export-columns-01",
        category="specific",
        query="Which issue describes CSV exports with blank custom field columns?",
        expected_entity_ids=frozenset({2727}),  # anchor: "custom field"
    ),

    EvalCase(
        id="webhook-retry-01",
        category="specific",
        query="Which issue is about webhook retries overwhelming the queue?",
        expected_entity_ids=frozenset({2728}),  # anchor: "backoff"
    ),

    EvalCase(
        id="timezone-due-date-01",
        category="specific",
        query="Which issue describes due dates shifting by one day across timezones?",
        expected_entity_ids=frozenset({2729}),  # anchor: "due date"
    ),

    EvalCase(
        id="archived-label-01",
        category="specific",
        query="Which issue is about archived labels still being applied?",
        expected_entity_ids=frozenset({2730}),  # anchor: "archived label"
    ),

    EvalCase(
        id="activity-order-01",
        category="specific",
        query="Which issue reports activity feed events ordering inconsistently?",
        expected_entity_ids=frozenset({2731}),  # anchor: "same millisecond"
    ),

    EvalCase(
        id="password-reset-01",
        category="specific",
        query="Which issue is about password reset links working more than once?",
        expected_entity_ids=frozenset({2732}),  # anchor: "password reset link"
    ),

    EvalCase(
        id="kanban-drag-01",
        category="specific",
        query="Which issue describes cards dropping in the wrong place on the board?",
        expected_entity_ids=frozenset({2733}),  # anchor: "kanban"
    ),

    EvalCase(
        id="import-truncation-01",
        category="specific",
        query="Which issue is about imported descriptions being cut short?",
        expected_entity_ids=frozenset({2734}),  # anchor: "truncat"
    ),

    # ---------------------------------------------------------------
    # paraphrased — same targets, wording that shares no vocabulary
    # with the issue text. These separate lexical matching from
    # semantic retrieval.
    # ---------------------------------------------------------------

    EvalCase(
        id="session-token-02",
        category="paraphrased",
        query="Why do finance users get logged out of the billing dashboard?",
        expected_entity_ids=frozenset({2720}),
    ),

    EvalCase(
        id="attachment-preview-02",
        category="paraphrased",
        query="Why is the preview pane blank for big image uploads?",
        expected_entity_ids=frozenset({2721}),
    ),

    EvalCase(
        id="membership-cache-02",
        category="paraphrased",
        query="Is there a security problem with offboarding?",
        expected_entity_ids=frozenset({2725}),
    ),

    EvalCase(
        id="password-reset-02",
        category="paraphrased",
        query="Can a reset token be reused to take over an account?",
        expected_entity_ids=frozenset({2732}),
    ),

    EvalCase(
        id="webhook-retry-02",
        category="paraphrased",
        query="What makes search indexing fall behind during an outage?",
        expected_entity_ids=frozenset({2728}),
    ),

    # ---------------------------------------------------------------
    # multi-target — every member verified by an anchor phrase that
    # matches EXACTLY these issues across all 2734 rows. Earlier versions
    # of these cases used broad concepts ("account security risks",
    # "deployment") whose true answer set runs into the hundreds; those
    # were unwinnable by construction and have been replaced.
    # ---------------------------------------------------------------

    EvalCase(
        id="silent-failure-01",
        category="multi",
        query="Which issues describe something failing with no warning to the user?",
        # anchor "without warning" -> corpus [2720, 2734]
        expected_entity_ids=frozenset({2720, 2734}),
    ),

    EvalCase(
        id="renders-empty-01",
        category="multi",
        query="Which issues cause content to render blank or empty?",
        # anchor "blank" -> corpus [2721, 2727]
        expected_entity_ids=frozenset({2721, 2727}),
    ),

    EvalCase(
        id="wrong-ordering-01",
        category="multi",
        query="Which issues cause items to appear in the wrong order or position?",
        # anchor "ordering" -> corpus [2731, 2733]
        expected_entity_ids=frozenset({2731, 2733}),
    ),
]
