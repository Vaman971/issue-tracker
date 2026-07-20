#!/usr/bin/env python3
"""
Large-scale seed script for Issue Tracker.
Inserts 150+ users, 500 projects, 2000+ issues, comments, attachments, etc.

Usage (run inside backend container):
  docker cp backend/seed_large.py issue_tracker_backend:/app/seed_large.py
  docker exec issue_tracker_backend python /app/seed_large.py
"""
import asyncio
import json
import random
from datetime import datetime, timedelta

import asyncpg
from passlib.context import CryptContext

# ── Config ────────────────────────────────────────────────────────────────────
DB_DSN = "postgresql://issue_user:issue_password@postgres:5432/issue_tracker"
SEED_PASSWORD = "Password123!"

# Pre-compute ONE bcrypt hash — reused for all seed users so seeding is fast
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
HASHED_PW = _pwd_ctx.hash(SEED_PASSWORD)

# ── Data pools ────────────────────────────────────────────────────────────────
FIRST_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Hank",
    "Iris", "Jack", "Kara", "Leo", "Mia", "Nathan", "Olivia", "Paul",
    "Quinn", "Rose", "Sam", "Tara", "Uma", "Victor", "Wendy", "Xander",
    "Yara", "Zoe", "Aaron", "Beth", "Carl", "Dana", "Eli", "Fiona",
    "Gus", "Hana", "Ivan", "Julia", "Kyle", "Luna", "Mike", "Nina",
    "Oscar", "Pam", "Rex", "Sara", "Tom", "Ursula", "Val", "Will",
    "Xena", "Yasmine", "Zack", "Aria", "Blake", "Cleo", "Drew", "Ember",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
    "White", "Harris", "Martin", "Thompson", "Young", "Lee", "Walker",
    "Hall", "Allen", "King", "Scott", "Green", "Baker", "Adams", "Nelson",
    "Carter", "Mitchell", "Perez", "Roberts", "Turner", "Phillips",
    "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart",
    "Sanchez", "Morris", "Rogers", "Reed", "Cook", "Morgan", "Bell",
    "Murphy", "Bailey", "Rivera", "Cooper", "Richardson", "Cox", "Howard",
]

TECH_COMPANIES = [
    "Acme Corp", "ByteForge", "CloudNine", "DataSphere", "EdgeLogic",
    "FinStack", "GridWorks", "HyperLoop", "Infracore", "JetStream",
    "KernelOS", "LightSpeed", "MegaPay", "NodeBurst", "OmniCloud",
    "PixelFlow", "QuantumX", "RapidBase", "Securly", "TechNova",
    "UniStack", "VaultNet", "WebCraft", "Xcelerate", "YieldAI",
    "ZeroGap", "Apexify", "Blueshift", "CipherX", "DevNest",
    "Elevate", "Flexio", "Grantify", "Helixware", "Intellect",
    "Joinly", "Katana", "Launchpad", "Micromax", "Nexlify",
    "Optimate", "Prodify", "Quarry", "Rootline", "Systex",
    "Trackly", "Unirex", "Vennly", "Workbench", "Xenith",
    "Zephyr", "Altitude", "Beacon", "Cascade", "Driftly",
]

PROJECT_TYPES = [
    "Issue Tracker", "CRM Platform", "Payment Gateway", "Analytics Dashboard",
    "Mobile App", "API Gateway", "Data Pipeline", "Auth Service",
    "Notification Hub", "Billing System", "Reporting Suite", "Admin Panel",
    "Customer Portal", "Inventory Manager", "Deployment Pipeline",
    "Search Engine", "Email Service", "Monitoring System", "Content Management",
    "Onboarding Flow", "Audit Trail", "User Management", "Integration Layer",
    "Rate Limiter", "Feature Flags", "A/B Testing Platform", "Developer Portal",
    "Support Ticketing", "Release Manager", "Config Service",
    "Log Aggregator", "Cost Optimizer", "Access Control", "Scheduler",
    "Data Warehouse", "Event Bus", "Document Store", "Workflow Engine",
]

LABEL_POOL = [
    ("Bug", "#EF4444"), ("Feature", "#3B82F6"), ("Enhancement", "#8B5CF6"),
    ("Documentation", "#6B7280"), ("Critical", "#DC2626"), ("Low Priority", "#10B981"),
    ("High Priority", "#F59E0B"), ("UI/UX", "#EC4899"), ("Performance", "#06B6D4"),
    ("Security", "#EF4444"), ("API", "#3B82F6"), ("Backend", "#8B5CF6"),
    ("Frontend", "#F97316"), ("Database", "#14B8A6"), ("Testing", "#84CC16"),
    ("Refactor", "#6366F1"), ("Regression", "#F43F5E"), ("Blocked", "#9CA3AF"),
    ("Ready for Review", "#22C55E"), ("Needs Design", "#A855F7"),
    ("Good First Issue", "#34D399"), ("Breaking Change", "#F87171"),
    ("Technical Debt", "#94A3B8"), ("Won't Fix", "#D1D5DB"),
]

ISSUE_TITLES = [
    "Fix null pointer exception in auth middleware",
    "Add pagination to user list endpoint",
    "Dashboard loading slowly on large datasets",
    "Implement dark mode toggle",
    "Session token not invalidated on logout",
    "Add CSV export for reports",
    "Database query timeout under heavy load",
    "Mobile layout broken on Safari iOS",
    "Implement rate limiting for API endpoints",
    "Email notifications not delivered to Gmail",
    "Fix CORS headers on preflight requests",
    "Add two-factor authentication support",
    "Memory leak in background worker process",
    "Improve search indexing performance",
    "Broken image upload on Windows file paths",
    "Add audit log for admin actions",
    "Refactor legacy authentication module",
    "WebSocket connections disconnect under load",
    "Missing validation on user registration form",
    "Implement soft delete for projects",
    "Cache invalidation not working correctly",
    "Intermittent 502 errors from load balancer",
    "Add support for SSO via OAuth2",
    "PDF generation fails for large reports",
    "Incorrect timezone handling in scheduler",
    "Improve error messages in API responses",
    "Add bulk user import via CSV",
    "Fix race condition in notification service",
    "Performance regression introduced in v2.3.1",
    "Upgrade PostgreSQL driver to latest version",
    "Add retry logic for failed webhook deliveries",
    "Button click not registering on mobile devices",
    "Implement data archival for old records",
    "Missing index causing slow dashboard queries",
    "XSS vulnerability in comment renderer",
    "Add keyboard shortcuts for common actions",
    "Fix broken pagination on search results page",
    "Attachment preview not loading in Firefox",
    "Add role-based field visibility controls",
    "Duplicate email notifications for same event",
    "API response time exceeds SLA on /reports endpoint",
    "User avatar upload fails silently on large files",
    "Filter dropdowns not persisting after page refresh",
    "Implement export to Excel functionality",
    "Add custom webhook support for integrations",
    "Fix stale data shown after concurrent edits",
    "Improve onboarding flow for new users",
    "Add GraphQL endpoint for mobile clients",
    "Deprecate legacy v1 API endpoints",
    "Implement IP allowlist for admin panel",
]

ISSUE_DESCRIPTIONS = [
    """Steps to reproduce:
1. Navigate to the affected page
2. Perform the triggering action
3. Observe the error in the console

Expected: Normal behavior continues
Actual: Exception is thrown and page becomes unresponsive""",

    """This has been affecting production users since the last deployment. Priority should be high as it blocks normal workflow for approximately 30% of our users.

Environment: Production (v2.4.1)
Frequency: Happens on every 3rd request under concurrent load""",

    """Performance profiling shows this query takes 3-8 seconds under normal load. Adding a composite index or rewriting the query with a CTE should reduce this to under 100ms.

Profiling output attached. The bottleneck is the N+1 query in the list view — eager loading should fix it.""",

    """Acceptance criteria:
- Feature works across all supported browsers (Chrome, Firefox, Safari, Edge)
- Mobile responsive down to 375px viewport
- Unit tests added with >80% coverage
- API documentation updated
- Feature flag added for gradual rollout""",

    """Reported by 5 enterprise customers this week. Temporary workaround: refresh the page and re-enter the form. Root cause under investigation — likely related to the session middleware refactor in last sprint.""",

    """The current implementation doesn't handle edge cases when the dataset exceeds 10,000 records. We need to add proper server-side pagination with cursor-based navigation and lazy loading for the frontend.""",

    """Security audit finding from external penetration test (report #SEC-2026-047). Needs immediate attention before the Q3 compliance review. See attached vulnerability report for full technical details and CVSS score (7.3 High).""",

    """This is a follow-up to the architecture review conducted last sprint. The refactor will improve maintainability, reduce technical debt, and align with our new domain-driven design principles.""",

    None,

    """Observed in staging environment after latest migration script ran. Database logs attached. The issue appears to be a deadlock between two concurrent transactions accessing the same rows in opposite order.""",

    """Customer impact: affects all users on the Enterprise plan. SLA breach risk if not resolved within 48 hours. Engineering escalation approved — assigning to senior backend team.""",

    """This blocks the Q3 roadmap delivery. Product team has been notified. We need a fix or workaround by end of week. Temporary mitigation deployed to reduce impact.""",
]

COMMENT_CONTENTS = [
    "I can reproduce this consistently. It happens when the session token is older than 24 hours and the user hasn't interacted with the app.",
    "Working on a fix now. Should have a PR up by end of day — the root cause is a missing null check before the property access.",
    "This looks related to the issue we fixed in the auth module last month. Let me check if the same root cause applies here.",
    "Tested the fix on staging — looks good across all three test scenarios! Ready for code review and QA sign-off.",
    "We might want to consider a more permanent solution instead of the quick fix proposed here. The underlying architecture has a design flaw we keep patching around.",
    "Can we get more details about the environment where this was observed? Specifically: OS version, browser, network conditions, and whether it's reproducible on a clean browser profile.",
    "Just confirmed this affects the mobile app as well, not just the web client. iOS 16.5 and Android 13 both affected.",
    "PR #456 has been opened to address this. Includes unit tests, integration tests, and updated API documentation. Please review when you get a chance.",
    "I'll schedule this for the next sprint. The current sprint is at capacity and this doesn't meet the P1 threshold.",
    "The fix is straightforward — just need to add a null check before accessing the nested property. Three-line change, low risk.",
    "Have we considered the downstream impact on the reporting module? Changing this behavior might break the weekly digest emails.",
    "This is a P0 for our team — it's blocking our Q3 release milestone. Can we get someone from the platform team to look at this today?",
    "Added additional context to the PR description. The fix uses a LEFT JOIN instead of INNER JOIN to handle the case where related records have been soft-deleted.",
    "Looks like a regression introduced in commit abc1234 when the authentication middleware was updated. A targeted revert of that commit should unblock us immediately.",
    "Unit tests pass but the integration tests against a real Postgres instance are still failing intermittently. Investigating whether it's a test isolation issue.",
    "After profiling with py-spy, the bottleneck is the N+1 query in the list view loader. Adding select_related() calls cuts the query count from ~300 to 3.",
    "Closing as won't fix — the observed behavior is intentional per the product spec agreed with stakeholders in the Q2 planning session.",
    "Resolved as part of the v2.5 release deployment yesterday. Monitoring dashboards look clean. Marking as done.",
    "Needs design mockups before implementation can begin. I've pinged the design team — they'll have something in Figma by Thursday.",
    "The backend API changes are deployed to staging. Frontend integration work will be included in next week's release candidate.",
    "After further investigation, this is a configuration issue in the nginx proxy rather than an application bug. Updating the nginx config and redeploying.",
    "I've added a failing test case that demonstrates the bug. Now working on the fix — should be straightforward.",
    "This is more complex than initially estimated. The fix requires changes across 4 services and coordination with the infra team for the deployment.",
    "Quick update: found the root cause. It's a timezone offset bug in the scheduler — all timestamps were being stored in local time instead of UTC.",
]

ATTACHMENT_FILES = [
    ("screenshot_error.png", "image/png", 245678),
    ("debug_log.txt", "text/plain", 12345),
    ("performance_report.pdf", "application/pdf", 1234567),
    ("api_response.json", "application/json", 8901),
    ("test_results.csv", "text/csv", 45678),
    ("architecture_diagram.png", "image/png", 345678),
    ("error_trace.txt", "text/plain", 23456),
    ("db_schema_v2.pdf", "application/pdf", 987654),
    ("repro_case.zip", "application/zip", 123456),
    ("mockup_v3.png", "image/png", 456789),
    ("access_log.txt", "text/plain", 34567),
    ("config_backup.json", "application/json", 5678),
    ("load_test_results.csv", "text/csv", 67890),
    ("crash_dump.zip", "application/zip", 2345678),
    ("flamegraph.svg", "image/svg+xml", 189034),
    ("db_query_plan.txt", "text/plain", 4567),
    ("user_feedback.pdf", "application/pdf", 567890),
    ("network_trace.json", "application/json", 234567),
]

STATUSES = ["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE"]
PRIORITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
STATUS_WEIGHTS = [0.35, 0.25, 0.15, 0.25]
PRIORITY_WEIGHTS = [0.15, 0.40, 0.30, 0.15]

ACTIVITY_ACTIONS = [
    "created", "status_changed", "priority_changed", "assigned",
    "comment_added", "label_added", "title_changed", "attachment_added",
    "description_changed", "label_removed",
]
ACTIVITY_WEIGHTS = [0.20, 0.20, 0.10, 0.15, 0.15, 0.08, 0.05, 0.04, 0.02, 0.01]

NOTIF_TYPES = [
    ("issue_created",      "New issue in your project",    "A new issue has been opened in a project you lead."),
    ("issue_assigned",     "Issue assigned to you",        "You have been assigned to an issue that needs attention."),
    ("issue_status_changed","Issue status updated",        "An issue you're watching changed status."),
    ("issue_commented",    "New comment on your issue",    "Someone left a comment on an issue you created."),
    ("issue_updated",      "Issue updated",                "An issue in your project was updated."),
    ("project_member_added","Added to a project",          "You have been added as a member to a new project."),
]


def rand_dt(days_ago_max: int = 365, days_ago_min: int = 1) -> datetime:
    delta = timedelta(
        days=random.randint(days_ago_min, days_ago_max),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    return datetime.utcnow() - delta


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("Connecting to database …")
    conn = await asyncpg.connect(DB_DSN)
    try:
        await seed(conn)
    finally:
        await conn.close()
    print("\nSeeding complete.")


async def seed(conn: asyncpg.Connection) -> None:  # noqa: C901 (complexity ok for a seed script)
    existing = await conn.fetchval("SELECT COUNT(*) FROM users")
    print(f"Existing users in DB: {existing}")

    # ── 1. Users ──────────────────────────────────────────────────────────────
    print("\n[1/11] Seeding users …")

    role_batches = [
        ("ADMIN",          3),
        ("PROJECT_LEADER", 22),
        ("DEVELOPER",      75),
        ("QA",             30),
        ("VIEWER",         20),
    ]

    users_data = []
    idx = 1
    for role, count in role_batches:
        for _ in range(count):
            fn = random.choice(FIRST_NAMES)
            ln = random.choice(LAST_NAMES)
            email = f"{fn.lower()}.{ln.lower()}{idx}@seeddata.dev"
            users_data.append((email, HASHED_PW, role, f"{fn} {ln}", True, True))
            idx += 1

    await conn.executemany(
        """
        INSERT INTO users (email, hashed_password, role, full_name, is_active, is_email_verified)
        VALUES ($1, $2, $3::userrole, $4, $5, $6)
        ON CONFLICT (email) DO NOTHING
        """,
        users_data,
    )
    print(f"  → {len(users_data)} users inserted (conflicts silently skipped)")

    rows = await conn.fetch("SELECT id, role FROM users WHERE email LIKE '%@seeddata.dev'")
    users_by_role: dict[str, list[int]] = {
        "ADMIN": [], "PROJECT_LEADER": [], "DEVELOPER": [], "QA": [], "VIEWER": []
    }
    all_seed_uids: list[int] = []
    for r in rows:
        users_by_role[r["role"]].append(r["id"])
        all_seed_uids.append(r["id"])

    leader_pool = users_by_role["PROJECT_LEADER"] + users_by_role["ADMIN"]
    print(f"  → leaders available: {len(leader_pool)}, total seed users: {len(all_seed_uids)}")

    # ── 2. Projects ───────────────────────────────────────────────────────────
    print("\n[2/11] Seeding projects …")

    existing_names: set[str] = {
        r["name"] for r in await conn.fetch("SELECT name FROM projects")
    }

    projects_data: list[tuple] = []
    attempts = 0
    while len(projects_data) < 500 and attempts < 5000:
        attempts += 1
        company = random.choice(TECH_COMPANIES)
        ptype = random.choice(PROJECT_TYPES)
        # Add a variant suffix so the same company can have multiple project types
        variant = random.randint(1, 9)
        name = f"{company} — {ptype} {variant}"
        if name in existing_names:
            continue
        existing_names.add(name)
        desc = (
            f"Core {ptype.lower()} platform built by {company}. "
            "Designed for scalability, reliability, and developer ergonomics."
        )
        projects_data.append((name, desc, random.choice(leader_pool)))

    await conn.executemany(
        "INSERT INTO projects (name, description, leader_id) VALUES ($1, $2, $3)",
        projects_data,
    )

    proj_rows = await conn.fetch(
        "SELECT id, leader_id FROM projects WHERE name LIKE '%@seeddata%' OR id > "
        "(SELECT COALESCE(MAX(id),0) - $1 FROM projects)",
        len(projects_data) + 10,
    )
    # Safer: just load recent ones by leader membership
    proj_rows = await conn.fetch(
        "SELECT p.id, p.leader_id FROM projects p "
        "JOIN users u ON u.id = p.leader_id "
        "WHERE u.email LIKE '%@seeddata.dev'"
    )
    project_ids: list[int] = [r["id"] for r in proj_rows]
    proj_leader: dict[int, int] = {r["id"]: r["leader_id"] for r in proj_rows}
    print(f"  → {len(project_ids)} seed projects available")

    # ── 3. Project Members ────────────────────────────────────────────────────
    print("\n[3/11] Seeding project members …")

    existing_pm: set[tuple[int, int]] = {
        (r["project_id"], r["user_id"])
        for r in await conn.fetch("SELECT project_id, user_id FROM project_members")
    }

    members_data: list[tuple] = []
    for pid in project_ids:
        # Leader is always a member
        lid = proj_leader[pid]
        if (pid, lid) not in existing_pm:
            members_data.append((pid, lid))
            existing_pm.add((pid, lid))

        # 5–14 additional random members
        n = random.randint(5, 14)
        pool = random.sample(all_seed_uids, min(n + 10, len(all_seed_uids)))
        added = 0
        for uid in pool:
            if added >= n:
                break
            if (pid, uid) not in existing_pm:
                members_data.append((pid, uid))
                existing_pm.add((pid, uid))
                added += 1

    await conn.executemany(
        "INSERT INTO project_members (project_id, user_id) VALUES ($1, $2)",
        members_data,
    )
    print(f"  → {len(members_data)} memberships inserted")

    # Build project → members map for downstream steps
    pm_rows = await conn.fetch(
        "SELECT project_id, user_id FROM project_members WHERE project_id = ANY($1)",
        project_ids,
    )
    proj_members: dict[int, list[int]] = {}
    for r in pm_rows:
        proj_members.setdefault(r["project_id"], []).append(r["user_id"])

    # ── 4. Labels ─────────────────────────────────────────────────────────────
    print("\n[4/11] Seeding labels …")

    existing_labels: set[tuple[int, str]] = {
        (r["project_id"], r["name"])
        for r in await conn.fetch("SELECT project_id, name FROM labels")
    }

    labels_data: list[tuple] = []
    for pid in project_ids:
        sample = random.sample(LABEL_POOL, random.randint(5, 8))
        for name, color in sample:
            if (pid, name) not in existing_labels:
                labels_data.append((pid, name, color))
                existing_labels.add((pid, name))

    await conn.executemany(
        "INSERT INTO labels (project_id, name, color) VALUES ($1, $2, $3)",
        labels_data,
    )
    print(f"  → {len(labels_data)} labels inserted")

    proj_labels: dict[int, list[int]] = {}
    for r in await conn.fetch(
        "SELECT id, project_id FROM labels WHERE project_id = ANY($1)", project_ids
    ):
        proj_labels.setdefault(r["project_id"], []).append(r["id"])

    # ── 5. Issues ─────────────────────────────────────────────────────────────
    print("\n[5/11] Seeding issues …")

    issues_data: list[tuple] = []
    for pid in project_ids:
        members = proj_members.get(pid, [])
        if not members:
            continue
        for _ in range(random.randint(3, 8)):
            issues_data.append((
                random.choice(ISSUE_TITLES),
                random.choice(ISSUE_DESCRIPTIONS),
                random.choices(STATUSES, weights=STATUS_WEIGHTS)[0],
                random.choices(PRIORITIES, weights=PRIORITY_WEIGHTS)[0],
                pid,
                random.choice(members),
            ))

    await conn.executemany(
        """
        INSERT INTO issues (title, description, status, priority, project_id, creator_id)
        VALUES ($1, $2, $3::issuestatus, $4::issuepriority, $5, $6)
        """,
        issues_data,
    )
    print(f"  → {len(issues_data)} issues inserted")

    issue_rows = await conn.fetch(
        "SELECT id, project_id, creator_id FROM issues WHERE project_id = ANY($1)",
        project_ids,
    )
    # issue_id → {project_id, creator_id}
    issue_meta: dict[int, dict] = {
        r["id"]: {"project_id": r["project_id"], "creator_id": r["creator_id"]}
        for r in issue_rows
    }
    all_issue_ids = list(issue_meta)
    print(f"  → {len(all_issue_ids)} total issues in scope (including pre-existing)")

    # ── 6. Issue Assignees ────────────────────────────────────────────────────
    print("\n[6/11] Seeding issue assignees …")

    existing_assign: set[tuple[int, int]] = {
        (r["issue_id"], r["user_id"])
        for r in await conn.fetch("SELECT issue_id, user_id FROM issue_assignees")
    }

    assignees_data: list[tuple] = []
    for iid, meta in issue_meta.items():
        members = proj_members.get(meta["project_id"], [])
        if not members:
            continue
        n = random.randint(1, min(3, len(members)))
        for uid in random.sample(members, n):
            if (iid, uid) not in existing_assign:
                assignees_data.append((iid, uid))
                existing_assign.add((iid, uid))

    await conn.executemany(
        "INSERT INTO issue_assignees (issue_id, user_id) VALUES ($1, $2)",
        assignees_data,
    )
    print(f"  → {len(assignees_data)} assignees inserted")

    # ── 7. Issue Labels ───────────────────────────────────────────────────────
    print("\n[7/11] Seeding issue labels …")

    existing_il: set[tuple[int, int]] = {
        (r["issue_id"], r["label_id"])
        for r in await conn.fetch("SELECT issue_id, label_id FROM issue_labels")
    }

    il_data: list[tuple] = []
    for iid, meta in issue_meta.items():
        avail = proj_labels.get(meta["project_id"], [])
        if not avail or random.random() > 0.75:  # 75% of issues get labels
            continue
        for lid in random.sample(avail, random.randint(1, min(3, len(avail)))):
            if (iid, lid) not in existing_il:
                il_data.append((iid, lid))
                existing_il.add((iid, lid))

    await conn.executemany(
        "INSERT INTO issue_labels (issue_id, label_id) VALUES ($1, $2)",
        il_data,
    )
    print(f"  → {len(il_data)} issue–label links inserted")

    # ── 8. Comments ───────────────────────────────────────────────────────────
    print("\n[8/11] Seeding comments …")

    top_comments: list[tuple] = []
    for iid, meta in issue_meta.items():
        members = proj_members.get(meta["project_id"], [])
        if not members:
            continue
        for _ in range(random.randint(2, 7)):
            top_comments.append((
                iid,
                random.choice(members),
                random.choice(COMMENT_CONTENTS),
                None,
                rand_dt(180),
            ))

    await conn.executemany(
        """
        INSERT INTO issue_comments (issue_id, author_id, content, parent_id, created_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        top_comments,
    )
    print(f"  → {len(top_comments)} top-level comments inserted")

    # Build issue → top-level comment IDs for replies
    tc_rows = await conn.fetch(
        """
        SELECT ic.id, ic.issue_id
        FROM issue_comments ic
        WHERE ic.issue_id = ANY($1) AND ic.parent_id IS NULL
        """,
        all_issue_ids,
    )
    comments_by_issue: dict[int, list[int]] = {}
    for r in tc_rows:
        comments_by_issue.setdefault(r["issue_id"], []).append(r["id"])

    replies: list[tuple] = []
    for iid, cids in comments_by_issue.items():
        meta = issue_meta.get(iid)
        if not meta:
            continue
        members = proj_members.get(meta["project_id"], [])
        if not members:
            continue
        for cid in cids:
            if random.random() < 0.30:  # 30% of top-level comments get replies
                for _ in range(random.randint(1, 3)):
                    replies.append((
                        iid,
                        random.choice(members),
                        random.choice(COMMENT_CONTENTS),
                        cid,
                        rand_dt(90),
                    ))

    if replies:
        await conn.executemany(
            """
            INSERT INTO issue_comments (issue_id, author_id, content, parent_id, created_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            replies,
        )
    print(f"  → {len(replies)} reply comments inserted")

    # ── 9. Attachments ────────────────────────────────────────────────────────
    print("\n[9/11] Seeding attachments …")

    att_data: list[tuple] = []
    for iid, meta in issue_meta.items():
        members = proj_members.get(meta["project_id"], [])
        if not members or random.random() > 0.65:  # 65% of issues get attachments
            continue
        for _ in range(random.randint(1, 3)):
            fname, mime, base_size = random.choice(ATTACHMENT_FILES)
            size = max(1, base_size + random.randint(-base_size // 4, base_size // 4))
            att_data.append((
                iid,
                random.choice(members),
                fname,
                f"uploads/seed/{iid}/{fname}",
                size,
                mime,
                rand_dt(180),
            ))

    await conn.executemany(
        """
        INSERT INTO issue_attachments
          (issue_id, uploader_id, original_filename, file_key, file_size_bytes, mime_type, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        att_data,
    )
    print(f"  → {len(att_data)} attachments inserted")

    # ── 10. Activities ────────────────────────────────────────────────────────
    print("\n[10/11] Seeding activities …")

    statuses_lower = ["todo", "in_progress", "in_review", "done"]
    priorities_lower = ["low", "medium", "high", "critical"]

    act_data: list[tuple] = []
    for iid, meta in issue_meta.items():
        members = proj_members.get(meta["project_id"], [])
        if not members:
            continue

        base = rand_dt(days_ago_max=300, days_ago_min=60)
        for i in range(random.randint(3, 8)):
            action = random.choices(ACTIVITY_ACTIONS, weights=ACTIVITY_WEIGHTS)[0]
            actor = random.choice(members)
            old_val = new_val = None

            if action == "status_changed":
                old_val = random.choice(statuses_lower)
                new_val = random.choice([s for s in statuses_lower if s != old_val])
            elif action == "priority_changed":
                old_val = random.choice(priorities_lower)
                new_val = random.choice([p for p in priorities_lower if p != old_val])
            elif action == "assigned":
                new_val = str(random.choice(members))
            elif action in ("label_added", "label_removed"):
                lbls = proj_labels.get(meta["project_id"], [])
                if lbls:
                    new_val = str(random.choice(lbls))

            act_ts = base + timedelta(days=i * random.randint(1, 5))
            act_data.append((iid, actor, action, old_val, new_val, act_ts))

    await conn.executemany(
        """
        INSERT INTO issue_activities (issue_id, actor_id, action, old_value, new_value, created_at)
        VALUES ($1, $2, $3::activityaction, $4, $5, $6)
        """,
        act_data,
    )
    print(f"  → {len(act_data)} activity entries inserted")

    # ── 11. Notifications ─────────────────────────────────────────────────────
    print("\n[11/11] Seeding notifications …")

    notif_data: list[tuple] = []
    for uid in all_seed_uids:
        for _ in range(random.randint(3, 10)):
            ntype, title, msg = random.choice(NOTIF_TYPES)
            notif_data.append((
                uid,
                ntype,
                title,
                msg,
                random.random() < 0.60,  # 60% read
                json.dumps({"seeded": True}),
                rand_dt(90),
            ))

    await conn.executemany(
        """
        INSERT INTO notifications (user_id, type, title, message, is_read, meta, created_at)
        VALUES ($1, $2::notificationtype, $3, $4, $5, $6, $7)
        """,
        notif_data,
    )
    print(f"  → {len(notif_data)} notifications inserted")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n─── Final table counts ──────────────────────────────────")
    for tbl in [
        "users", "projects", "project_members", "labels",
        "issues", "issue_assignees", "issue_labels",
        "issue_comments", "issue_attachments", "issue_activities", "notifications",
    ]:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {tbl}")  # noqa: S608
        print(f"  {tbl:<25} {count:>6}")


if __name__ == "__main__":
    asyncio.run(main())
