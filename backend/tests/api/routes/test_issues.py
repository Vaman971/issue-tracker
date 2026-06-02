import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.issue import Issue
from app.models.label import Label
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole


async def create_user(db_session: AsyncSession, email: str, role: UserRole):
    user = User(
        email=email,
        hashed_password=hash_password("testpassword123"),
        role=role,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


async def user_login(client: AsyncClient, email: str):
    response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "testpassword123",
        },
    )

    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_member_sees_only_project_issues(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "leader@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "dev@example.com", UserRole.DEVELOPER)

    project_one = Project(name="Project One", description=None, leader_id=leader.id)
    project_two = Project(name="Project Two", description=None, leader_id=leader.id)

    db_session.add_all([project_one, project_two])
    await db_session.commit()
    await db_session.refresh(project_one)
    await db_session.refresh(project_two)

    db_session.add(ProjectMember(project_id=project_one.id, user_id=developer.id))
    await db_session.commit()

    issue_one = Issue(
        title="Visible Issue",
        description=None,
        project_id=project_one.id,
        creator_id=developer.id,
    )
    issue_two = Issue(
        title="Hidden Issue",
        description=None,
        project_id=project_two.id,
        creator_id=leader.id,
    )

    db_session.add_all([issue_one, issue_two])
    await db_session.commit()

    token = await user_login(client, developer.email)

    response = await client.get(
        "/issues/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["title"] == "Visible Issue"


@pytest.mark.asyncio
async def test_issue_pagination_limit(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "admin@example.com", UserRole.ADMIN)

    project = Project(
        name="Pagination Project",
        description=None,
        leader_id=admin.id,
    )

    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    issues = [
        Issue(
            title=f"Issue {index}",
            description=None,
            project_id=project.id,
            creator_id=admin.id,
        )
        for index in range(5)
    ]

    db_session.add_all(issues)
    await db_session.commit()

    token = await user_login(client, admin.email)

    response = await client.get(
        "/issues/?skip=0&limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_viewer_member_cannot_create_issue(
    client: AsyncClient,
    db_session: AsyncSession,
):
    leader = await create_user(db_session, "leader3@example.com", UserRole.PROJECT_LEADER)
    viewer = await create_user(db_session, "viewer@example.com", UserRole.VIEWER)

    project = Project(
        name="Viewer Project",
        description=None,
        leader_id=leader.id,
    )

    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=viewer.id))
    await db_session.commit()

    token = await user_login(client, viewer.email)

    response = await client.post(
        "/issues/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Viewer issue",
            "description": "Should not be allowed",
            "project_id": project.id,
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_assignee_must_be_project_member(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """A plain DEVELOPER not in the project cannot be assigned (not a member, not a leader)."""
    admin = await create_user(db_session, "admin3@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "leader4@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "outside-dev@example.com", UserRole.DEVELOPER)

    project = Project(
        name="Assignee Project",
        description=None,
        leader_id=leader.id,
    )

    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await user_login(client, admin.email)

    response = await client.post(
        "/issues/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Invalid assignee",
            "description": None,
            "project_id": project.id,
            "assignee_ids": [developer.id],
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_developer_member_can_only_update_issue_status(
    client: AsyncClient,
    db_session: AsyncSession,
):
    leader = await create_user(db_session, "leader5@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "dev5@example.com", UserRole.DEVELOPER)

    project = Project(
        name="Status Only Project",
        description=None,
        leader_id=leader.id,
    )

    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=developer.id))
    await db_session.commit()

    issue = Issue(
        title="Original title",
        description="Original description",
        project_id=project.id,
        creator_id=leader.id,
    )

    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, developer.email)

    response = await client.patch(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Developer changed title",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Project members can only update issue status"


@pytest.mark.asyncio
async def test_issues_list_is_cached_and_invalidated_after_update(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis,
):
    admin = await create_user(db_session, "cache-admin@example.com", UserRole.ADMIN)

    project = Project(
        name="Issue Cache Project",
        description=None,
        leader_id=admin.id,
    )

    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    issue = Issue(
        title="Cached issue",
        description=None,
        project_id=project.id,
        creator_id=admin.id,
    )

    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, admin.email)

    list_response = await client.get(
        "/issues/?skip=0&limit=20",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert list_response.status_code == 200
    assert any(key.startswith("issues:list:") for key in fake_redis.store)

    update_response = await client.patch(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "in_progress"},
    )

    assert update_response.status_code == 200
    assert not any(key.startswith("issues:list:") for key in fake_redis.store)


# ---------------------------------------------------------------------------
# GET /issues/{issue_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_issue_by_id_admin(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "gi-admin@example.com", UserRole.ADMIN)
    project = Project(name="GI Project", leader_id=admin.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    issue = Issue(title="Target Issue", project_id=project.id, creator_id=admin.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, admin.email)
    response = await client.get(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == issue.id
    assert response.json()["title"] == "Target Issue"


@pytest.mark.asyncio
async def test_get_issue_project_member_can_access(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "gi-leader@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "gi-dev@example.com", UserRole.DEVELOPER)

    project = Project(name="GI Member Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=developer.id))

    issue = Issue(title="Member Issue", project_id=project.id, creator_id=leader.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, developer.email)
    response = await client.get(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == issue.id


@pytest.mark.asyncio
async def test_get_issue_non_member_forbidden(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "gi-ldr2@example.com", UserRole.PROJECT_LEADER)
    outsider = await create_user(db_session, "gi-out@example.com", UserRole.DEVELOPER)

    project = Project(name="GI Private Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    issue = Issue(title="Private Issue", project_id=project.id, creator_id=leader.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, outsider.email)
    response = await client.get(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_issue_not_found(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "gi-nf@example.com", UserRole.ADMIN)
    token = await user_login(client, admin.email)

    response = await client.get(
        "/issues/99999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /issues/{issue_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_issue_by_creator(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "di-ldr@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "di-dev@example.com", UserRole.DEVELOPER)

    project = Project(name="DI Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=developer.id))

    issue = Issue(title="Dev Created Issue", project_id=project.id, creator_id=developer.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, developer.email)
    response = await client.delete(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_issue_by_admin(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "di-admin@example.com", UserRole.ADMIN)
    project = Project(name="DI Admin Project", leader_id=admin.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    issue = Issue(title="Admin Deletes Issue", project_id=project.id, creator_id=admin.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, admin.email)
    response = await client.delete(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    # Confirm gone
    get_resp = await client.get(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_issue_by_project_leader(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "di-ldr2@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "di-dev2@example.com", UserRole.DEVELOPER)

    project = Project(name="DI Leader Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=developer.id))
    issue = Issue(title="Leader Deletes Dev Issue", project_id=project.id, creator_id=developer.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, leader.email)
    response = await client.delete(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_issue_non_creator_member_forbidden(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "di-ldr3@example.com", UserRole.PROJECT_LEADER)
    creator = await create_user(db_session, "di-creator@example.com", UserRole.DEVELOPER)
    bystander = await create_user(db_session, "di-bystander@example.com", UserRole.DEVELOPER)

    project = Project(name="DI Forbidden Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add_all([
        ProjectMember(project_id=project.id, user_id=creator.id),
        ProjectMember(project_id=project.id, user_id=bystander.id),
    ])
    issue = Issue(title="Creator Issue", project_id=project.id, creator_id=creator.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, bystander.email)
    response = await client.delete(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_issue_not_found(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "di-nf@example.com", UserRole.ADMIN)
    token = await user_login(client, admin.email)

    response = await client.delete(
        "/issues/99999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_issue_invalidates_cache(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis,
):
    admin = await create_user(db_session, "di-cache@example.com", UserRole.ADMIN)
    project = Project(name="DI Cache Project", leader_id=admin.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    issue = Issue(title="Cached Delete Issue", project_id=project.id, creator_id=admin.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, admin.email)

    # Warm up the list cache
    await client.get("/issues/?skip=0&limit=20", headers={"Authorization": f"Bearer {token}"})
    assert any(key.startswith("issues:list:") for key in fake_redis.store)

    delete_resp = await client.delete(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert delete_resp.status_code == 204
    assert not any(key.startswith("issues:list:") for key in fake_redis.store)


# ---------------------------------------------------------------------------
# Bug fix: issue response must include labels field
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_issue_response_includes_empty_labels_field(
    client: AsyncClient, db_session: AsyncSession
):
    admin = await create_user(db_session, "lbl-admin@example.com", UserRole.ADMIN)
    project = Project(name="Labels Bug Project", leader_id=admin.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    issue = Issue(title="Label Field Issue", project_id=project.id, creator_id=admin.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, admin.email)
    response = await client.get(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "labels" in data
    assert data["labels"] == []


@pytest.mark.asyncio
async def test_label_appears_in_issue_after_assignment(
    client: AsyncClient, db_session: AsyncSession
):
    admin = await create_user(db_session, "lbl-admin2@example.com", UserRole.ADMIN)
    project = Project(name="Label Assign Project", leader_id=admin.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    label = Label(project_id=project.id, name="bug", color="#FF0000")
    db_session.add(label)
    issue = Issue(title="Issue For Label", project_id=project.id, creator_id=admin.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(label)
    await db_session.refresh(issue)

    token = await user_login(client, admin.email)

    assign_resp = await client.post(
        f"/issues/{issue.id}/labels/{label.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert assign_resp.status_code == 201

    get_resp = await client.get(
        f"/issues/{issue.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    labels = get_resp.json()["labels"]
    assert len(labels) == 1
    assert labels[0]["name"] == "bug"
    assert labels[0]["color"] == "#FF0000"


# ---------------------------------------------------------------------------
# Bug fix: ActivityAction enum mismatch caused 500 on comment/attachment create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_comment_returns_201(
    client: AsyncClient, db_session: AsyncSession
):
    """POST /issues/{id}/comments/ must succeed — previously 500'd due to
    ActivityAction enum being stored as uppercase name instead of lowercase value."""
    leader = await create_user(db_session, "cmt-leader@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "cmt-dev@example.com", UserRole.DEVELOPER)

    project = Project(name="Comment Bug Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=developer.id))
    issue = Issue(title="Comment Test Issue", project_id=project.id, creator_id=leader.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, developer.email)
    response = await client.post(
        f"/issues/{issue.id}/comments/",
        json={"content": "This is a test comment"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "This is a test comment"
    assert data["author_id"] == developer.id


@pytest.mark.asyncio
async def test_upload_attachment_returns_201(
    client: AsyncClient, db_session: AsyncSession
):
    """POST /issues/{id}/attachments/ must succeed — previously 500'd due to
    ActivityAction enum being stored as uppercase name instead of lowercase value."""
    admin = await create_user(db_session, "att-admin@example.com", UserRole.ADMIN)

    project = Project(name="Attachment Bug Project", leader_id=admin.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    issue = Issue(title="Attachment Test Issue", project_id=project.id, creator_id=admin.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, admin.email)

    pdf_bytes = b"%PDF-1.4 test content"
    response = await client.post(
        f"/issues/{issue.id}/attachments/",
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "test.pdf"
    assert data["mime_type"] == "application/pdf"


# ---------------------------------------------------------------------------
# Multiple assignees
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_issue_response_includes_assignees_and_creator_fields(
    client: AsyncClient, db_session: AsyncSession
):
    """Issue response must have 'assignees' list and 'creator' object."""
    admin = await create_user(db_session, "ma-admin@example.com", UserRole.ADMIN)
    project = Project(name="MA Project", leader_id=admin.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    issue = Issue(title="MA Issue", project_id=project.id, creator_id=admin.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    token = await user_login(client, admin.email)
    resp = await client.get(f"/issues/{issue.id}", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert "assignees" in data
    assert data["assignees"] == []
    assert "creator" in data
    assert data["creator"]["email"] == admin.email


@pytest.mark.asyncio
async def test_create_issue_with_multiple_assignees(
    client: AsyncClient, db_session: AsyncSession
):
    """An admin can create an issue with multiple assignees who are project members."""
    admin = await create_user(db_session, "ma-admin2@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "ma-leader@example.com", UserRole.PROJECT_LEADER)
    dev1 = await create_user(db_session, "ma-dev1@example.com", UserRole.DEVELOPER)
    dev2 = await create_user(db_session, "ma-dev2@example.com", UserRole.DEVELOPER)

    project = Project(name="MA Create Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    from app.models.project_member import ProjectMember
    db_session.add_all([
        ProjectMember(project_id=project.id, user_id=dev1.id),
        ProjectMember(project_id=project.id, user_id=dev2.id),
    ])
    await db_session.commit()

    token = await user_login(client, admin.email)
    resp = await client.post(
        "/issues/",
        json={
            "title": "Multi-assignee Issue",
            "project_id": project.id,
            "assignee_ids": [dev1.id, dev2.id],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assignee_ids_returned = {a["id"] for a in data["assignees"]}
    assert dev1.id in assignee_ids_returned
    assert dev2.id in assignee_ids_returned


@pytest.mark.asyncio
async def test_viewer_can_be_issue_assignee(
    client: AsyncClient, db_session: AsyncSession
):
    """A viewer who is a project member can be assigned to an issue."""
    admin = await create_user(db_session, "va-admin@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "va-leader@example.com", UserRole.PROJECT_LEADER)
    viewer = await create_user(db_session, "va-viewer@example.com", UserRole.VIEWER)

    project = Project(name="VA Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    from app.models.project_member import ProjectMember
    db_session.add(ProjectMember(project_id=project.id, user_id=viewer.id))
    await db_session.commit()

    token = await user_login(client, admin.email)
    resp = await client.post(
        "/issues/",
        json={"title": "Viewer Assigned Issue", "project_id": project.id, "assignee_ids": [viewer.id]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 201
    assignee_ids_returned = {a["id"] for a in resp.json()["assignees"]}
    assert viewer.id in assignee_ids_returned


@pytest.mark.asyncio
async def test_cross_project_leader_can_be_assignee(
    client: AsyncClient, db_session: AsyncSession
):
    """A project_leader of ANOTHER project can be assigned without being a member."""
    admin = await create_user(db_session, "cp-admin@example.com", UserRole.ADMIN)
    leader_a = await create_user(db_session, "cp-leader-a@example.com", UserRole.PROJECT_LEADER)
    leader_b = await create_user(db_session, "cp-leader-b@example.com", UserRole.PROJECT_LEADER)

    project_a = Project(name="CP Project A", leader_id=leader_a.id)
    db_session.add(project_a)
    await db_session.commit()
    await db_session.refresh(project_a)

    token = await user_login(client, admin.email)
    resp = await client.post(
        "/issues/",
        json={
            "title": "Cross Leader Issue",
            "project_id": project_a.id,
            "assignee_ids": [leader_b.id],  # leader_b leads a different project
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 201
    assignee_ids_returned = {a["id"] for a in resp.json()["assignees"]}
    assert leader_b.id in assignee_ids_returned


@pytest.mark.asyncio
async def test_update_issue_replaces_assignees(
    client: AsyncClient, db_session: AsyncSession
):
    """PATCH /issues/{id} with assignee_ids replaces the existing assignee list."""
    admin = await create_user(db_session, "ua-admin@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "ua-leader@example.com", UserRole.PROJECT_LEADER)
    dev1 = await create_user(db_session, "ua-dev1@example.com", UserRole.DEVELOPER)
    dev2 = await create_user(db_session, "ua-dev2@example.com", UserRole.DEVELOPER)

    project = Project(name="UA Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    from app.models.project_member import ProjectMember
    db_session.add_all([
        ProjectMember(project_id=project.id, user_id=dev1.id),
        ProjectMember(project_id=project.id, user_id=dev2.id),
    ])
    await db_session.commit()

    token = await user_login(client, admin.email)

    # Create with dev1 as assignee
    create_resp = await client.post(
        "/issues/",
        json={"title": "UA Issue", "project_id": project.id, "assignee_ids": [dev1.id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 201
    issue_id = create_resp.json()["id"]

    # Update to dev2 only
    update_resp = await client.patch(
        f"/issues/{issue_id}",
        json={"assignee_ids": [dev2.id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_resp.status_code == 200
    ids_after = {a["id"] for a in update_resp.json()["assignees"]}
    assert dev1.id not in ids_after
    assert dev2.id in ids_after
