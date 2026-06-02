import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
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


async def login_user(email: str, client: AsyncClient):
    response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "testpassword123",
        },
    )

    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_admin_can_create_project(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(
        db_session,
        "admin@example.com",
        UserRole.ADMIN,
    )

    leader = await create_user(
        db_session,
        "leader@example.com",
        UserRole.PROJECT_LEADER,
    )

    token = await login_user(admin.email, client)

    response = await client.post(
        "/projects/",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={
            "name": "Alpha Project",
            "description": "First project",
            "leader_id": leader.id,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Alpha Project"
    assert data["leader_id"] == leader.id


@pytest.mark.asyncio
async def test_project_leader_sees_only_their_projects(client: AsyncClient, db_session: AsyncSession):
    leader_one = await create_user(
        db_session,
        "leader1@example.com",
        UserRole.PROJECT_LEADER,
    )
    leader_two = await create_user(
        db_session,
        "leader2@example.com",
        UserRole.PROJECT_LEADER,
    )

    project_one = Project(
        name="Leader one Project",
        description="Visible to leader one",
        leader_id=leader_one.id,
    )
    project_two = Project(
        name="Leader two Project",
        description="Visible to leader two",
        leader_id=leader_two.id,
    )

    db_session.add_all([project_one, project_two])
    await db_session.commit()

    token = await login_user(leader_one.email, client)

    response = await client.get(
        "/projects/",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "Leader one Project"


@pytest.mark.asyncio
async def test_admin_cannot_create_project_with_non_leader_user(
    client: AsyncClient,
    db_session: AsyncSession,
):
    admin = await create_user(
        db_session,
        "admin2@example.com",
        UserRole.ADMIN,
    )
    developer = await create_user(
        db_session,
        "developer@example.com",
        UserRole.DEVELOPER,
    )

    token = await login_user(admin.email, client)

    response = await client.post(
        "/projects/",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={
            "name": "Invalid Leader Project",
            "description": "This should fail",
            "leader_id": developer.id,
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_project_member_sees_assigned_projects(
    client: AsyncClient,
    db_session: AsyncSession,
):
    leader = await create_user(
        db_session,
        "leader-member@example.com",
        UserRole.PROJECT_LEADER,
    )
    viewer = await create_user(
        db_session,
        "viewer-member@example.com",
        UserRole.VIEWER,
    )

    visible_project = Project(
        name="Visible Member Project",
        description="Visible to member",
        leader_id=leader.id,
    )
    hidden_project = Project(
        name="Hidden Member Project",
        description="Not visible to member",
        leader_id=leader.id,
    )

    db_session.add_all([visible_project, hidden_project])
    await db_session.commit()
    await db_session.refresh(visible_project)
    await db_session.refresh(hidden_project)

    db_session.add(
        ProjectMember(
            project_id=visible_project.id,
            user_id=viewer.id,
        )
    )
    await db_session.commit()

    token = await login_user(viewer.email, client)

    response = await client.get(
        "/projects/",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "Visible Member Project"


@pytest.mark.asyncio
async def test_projects_list_is_cached_and_invalidated_after_create(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis,
):
    admin = await create_user(db_session, "cache-admin@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "cache-leader@example.com", UserRole.PROJECT_LEADER)

    token = await login_user(admin.email, client)

    list_response = await client.get(
        "/projects/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert list_response.status_code == 200
    assert any(key.startswith("projects:list:") for key in fake_redis.store)

    create_response = await client.post(
        "/projects/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Cached Project",
            "description": "Created after cache warmup",
            "leader_id": leader.id,
        },
    )

    assert create_response.status_code == 201
    assert not any(key.startswith("projects:list:") for key in fake_redis.store)


# ---------------------------------------------------------------------------
# GET /projects/{project_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_project_by_id_admin(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "gp-admin@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "gp-ldr@example.com", UserRole.PROJECT_LEADER)

    project = Project(name="GP Target Project", description="A project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(admin.email, client)
    response = await client.get(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == project.id
    assert response.json()["name"] == "GP Target Project"


@pytest.mark.asyncio
async def test_get_project_by_id_leader(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "gp-ldr2@example.com", UserRole.PROJECT_LEADER)

    project = Project(name="GP Leader Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(leader.email, client)
    response = await client.get(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["leader_id"] == leader.id


@pytest.mark.asyncio
async def test_get_project_by_id_member(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "gp-ldr3@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "gp-dev@example.com", UserRole.DEVELOPER)

    project = Project(name="GP Member Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=developer.id))
    await db_session.commit()

    token = await login_user(developer.email, client)
    response = await client.get(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_project_non_member_forbidden(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "gp-ldr4@example.com", UserRole.PROJECT_LEADER)
    outsider = await create_user(db_session, "gp-out@example.com", UserRole.DEVELOPER)

    project = Project(name="GP Private Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(outsider.email, client)
    response = await client.get(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "gp-nf@example.com", UserRole.ADMIN)
    token = await login_user(admin.email, client)

    response = await client.get(
        "/projects/99999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /projects/{project_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_can_update_project(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "up-admin@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "up-ldr@example.com", UserRole.PROJECT_LEADER)

    project = Project(name="UP Original Name", description="old desc", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(admin.email, client)
    response = await client.patch(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "UP Updated Name", "description": "new desc"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "UP Updated Name"
    assert data["description"] == "new desc"


@pytest.mark.asyncio
async def test_update_project_can_change_leader(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "up-admin2@example.com", UserRole.ADMIN)
    old_leader = await create_user(db_session, "up-old-ldr@example.com", UserRole.PROJECT_LEADER)
    new_leader = await create_user(db_session, "up-new-ldr@example.com", UserRole.PROJECT_LEADER)

    project = Project(name="UP Leader Change Project", leader_id=old_leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(admin.email, client)
    response = await client.patch(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"leader_id": new_leader.id},
    )

    assert response.status_code == 200
    assert response.json()["leader_id"] == new_leader.id


@pytest.mark.asyncio
async def test_update_project_invalid_leader_rejected(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "up-admin3@example.com", UserRole.ADMIN)
    developer = await create_user(db_session, "up-dev@example.com", UserRole.DEVELOPER)
    leader = await create_user(db_session, "up-ldr2@example.com", UserRole.PROJECT_LEADER)

    project = Project(name="UP Invalid Leader Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(admin.email, client)
    response = await client.patch(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"leader_id": developer.id},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_non_admin_cannot_update_project(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "up-ldr3@example.com", UserRole.PROJECT_LEADER)

    project = Project(name="UP Protected Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(leader.email, client)
    response = await client.patch(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Hacked Name"},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /projects/{project_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_can_delete_project(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "dp-admin@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "dp-ldr@example.com", UserRole.PROJECT_LEADER)

    project = Project(name="DP Delete Me Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(admin.email, client)
    response = await client.delete(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    get_resp = await client.get(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_cascades_issues_and_members(
    client: AsyncClient,
    db_session: AsyncSession,
):
    from app.models.issue import Issue

    admin = await create_user(db_session, "dp-admin2@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "dp-ldr2@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "dp-dev@example.com", UserRole.DEVELOPER)

    project = Project(name="DP Cascade Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=developer.id))
    issue = Issue(title="Should Be Deleted", project_id=project.id, creator_id=leader.id)
    db_session.add(issue)
    await db_session.commit()
    await db_session.refresh(issue)

    issue_id = issue.id
    token = await login_user(admin.email, client)

    delete_resp = await client.delete(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_resp.status_code == 204

    # Issue should no longer be accessible
    issue_resp = await client.get(
        f"/issues/{issue_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert issue_resp.status_code == 404


@pytest.mark.asyncio
async def test_non_admin_cannot_delete_project(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "dp-ldr3@example.com", UserRole.PROJECT_LEADER)

    project = Project(name="DP Protected Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(leader.email, client)
    response = await client.delete(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /projects/{project_id}/members/
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_project_members(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "pm-admin@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "pm-ldr@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "pm-dev@example.com", UserRole.DEVELOPER)

    project = Project(name="PM List Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=developer.id))
    await db_session.commit()

    token = await login_user(admin.email, client)
    response = await client.get(
        f"/projects/{project.id}/members/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["user_id"] == developer.id
    # Response must include embedded user details
    assert "user" in data[0]
    assert data[0]["user"]["email"] == developer.email


@pytest.mark.asyncio
async def test_list_project_members_non_member_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
):
    leader = await create_user(db_session, "pm-ldr2@example.com", UserRole.PROJECT_LEADER)
    outsider = await create_user(db_session, "pm-out@example.com", UserRole.DEVELOPER)

    project = Project(name="PM Private Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(outsider.email, client)
    response = await client.get(
        f"/projects/{project.id}/members/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/members/
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leader_can_add_project_member(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "pm-ldr3@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "pm-dev2@example.com", UserRole.DEVELOPER)

    project = Project(name="PM Add Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(leader.email, client)
    response = await client.post(
        f"/projects/{project.id}/members/",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": developer.id},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == developer.id
    assert data["project_id"] == project.id
    assert data["user"]["email"] == developer.email


@pytest.mark.asyncio
async def test_add_duplicate_member_rejected(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "pm-ldr4@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "pm-dev3@example.com", UserRole.DEVELOPER)

    project = Project(name="PM Dup Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=developer.id))
    await db_session.commit()

    token = await login_user(leader.email, client)
    response = await client.post(
        f"/projects/{project.id}/members/",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": developer.id},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_add_project_leader_as_member_rejected(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "pm-ldr5@example.com", UserRole.PROJECT_LEADER)

    project = Project(name="PM Leader-as-Member Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(leader.email, client)
    response = await client.post(
        f"/projects/{project.id}/members/",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": leader.id},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_developer_cannot_add_project_member(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "pm-ldr6@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "pm-dev4@example.com", UserRole.DEVELOPER)
    other = await create_user(db_session, "pm-dev5@example.com", UserRole.DEVELOPER)

    project = Project(name="PM Dev Cannot Add Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=developer.id))
    await db_session.commit()

    token = await login_user(developer.email, client)
    response = await client.post(
        f"/projects/{project.id}/members/",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": other.id},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /projects/{project_id}/members/{user_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leader_can_remove_project_member(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "pm-ldr7@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "pm-dev6@example.com", UserRole.DEVELOPER)

    project = Project(name="PM Remove Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=developer.id))
    await db_session.commit()

    token = await login_user(leader.email, client)
    response = await client.delete(
        f"/projects/{project.id}/members/{developer.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    # Confirm removed — developer can no longer see the project
    dev_token = await login_user(developer.email, client)
    get_resp = await client.get(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {dev_token}"},
    )
    assert get_resp.status_code == 403


@pytest.mark.asyncio
async def test_remove_non_existent_member_not_found(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "pm-ldr8@example.com", UserRole.PROJECT_LEADER)
    outsider = await create_user(db_session, "pm-out2@example.com", UserRole.DEVELOPER)

    project = Project(name="PM Remove NF Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(leader.email, client)
    response = await client.delete(
        f"/projects/{project.id}/members/{outsider.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_developer_cannot_remove_project_member(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "pm-ldr9@example.com", UserRole.PROJECT_LEADER)
    developer = await create_user(db_session, "pm-dev7@example.com", UserRole.DEVELOPER)
    other = await create_user(db_session, "pm-dev8@example.com", UserRole.DEVELOPER)

    project = Project(name="PM Dev Cannot Remove Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add_all([
        ProjectMember(project_id=project.id, user_id=developer.id),
        ProjectMember(project_id=project.id, user_id=other.id),
    ])
    await db_session.commit()

    token = await login_user(developer.email, client)
    response = await client.delete(
        f"/projects/{project.id}/members/{other.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /projects/{project_id}/members/candidates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_candidates_excludes_existing_members_and_leader(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "cand-ldr1@example.com", UserRole.PROJECT_LEADER)
    member = await create_user(db_session, "cand-mem1@example.com", UserRole.DEVELOPER)
    outsider = await create_user(db_session, "cand-out1@example.com", UserRole.DEVELOPER)

    project = Project(name="Candidates Project 1", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=member.id))
    await db_session.commit()

    token = await login_user(leader.email, client)
    resp = await client.get(
        f"/projects/{project.id}/members/candidates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    candidate_ids = {u["id"] for u in resp.json()}
    assert outsider.id in candidate_ids
    assert member.id not in candidate_ids
    assert leader.id not in candidate_ids


@pytest.mark.asyncio
async def test_candidates_admin_can_access(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "cand-adm1@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "cand-ldr2@example.com", UserRole.PROJECT_LEADER)

    project = Project(name="Candidates Project 2", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(admin.email, client)
    resp = await client.get(
        f"/projects/{project.id}/members/candidates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_candidates_regular_member_forbidden(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "cand-ldr3@example.com", UserRole.PROJECT_LEADER)
    member = await create_user(db_session, "cand-mem2@example.com", UserRole.DEVELOPER)

    project = Project(name="Candidates Project 3", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=member.id))
    await db_session.commit()

    token = await login_user(member.email, client)
    resp = await client.get(
        f"/projects/{project.id}/members/candidates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_candidates_excludes_inactive_users(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "cand-ldr4@example.com", UserRole.PROJECT_LEADER)

    inactive = User(
        email="cand-inactive@example.com",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.DEVELOPER,
        is_active=False,
        is_email_verified=False,
    )
    db_session.add(inactive)
    await db_session.commit()
    await db_session.refresh(inactive)

    project = Project(name="Candidates Project 4", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(leader.email, client)
    resp = await client.get(
        f"/projects/{project.id}/members/candidates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    candidate_ids = {u["id"] for u in resp.json()}
    assert inactive.id not in candidate_ids


# ---------------------------------------------------------------------------
# GET /projects/{project_id}/issues/
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_project_issues_returns_all_issues(client: AsyncClient, db_session: AsyncSession):
    from app.models.issue import Issue

    admin = await create_user(db_session, "pi-admin@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "pi-leader@example.com", UserRole.PROJECT_LEADER)

    project = Project(name="PI Issues Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    issue1 = Issue(title="PI Issue One", project_id=project.id, creator_id=leader.id)
    issue2 = Issue(title="PI Issue Two", project_id=project.id, creator_id=leader.id)
    db_session.add_all([issue1, issue2])
    await db_session.commit()

    token = await login_user(admin.email, client)
    resp = await client.get(
        f"/projects/{project.id}/issues/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    titles = {i["title"] for i in data}
    assert "PI Issue One" in titles
    assert "PI Issue Two" in titles


@pytest.mark.asyncio
async def test_get_project_issues_status_filter(client: AsyncClient, db_session: AsyncSession):
    from app.models.issue import Issue, IssueStatus

    admin = await create_user(db_session, "pif-admin@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "pif-leader@example.com", UserRole.PROJECT_LEADER)

    project = Project(name="PIF Filter Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    todo_issue = Issue(title="Todo Issue", status=IssueStatus.TODO, project_id=project.id, creator_id=leader.id)
    done_issue = Issue(title="Done Issue", status=IssueStatus.DONE, project_id=project.id, creator_id=leader.id)
    db_session.add_all([todo_issue, done_issue])
    await db_session.commit()

    token = await login_user(admin.email, client)
    resp = await client.get(
        f"/projects/{project.id}/issues/?status=done",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Done Issue"


@pytest.mark.asyncio
async def test_get_project_issues_non_member_forbidden(client: AsyncClient, db_session: AsyncSession):
    leader = await create_user(db_session, "pif-ldr2@example.com", UserRole.PROJECT_LEADER)
    outsider = await create_user(db_session, "pif-out@example.com", UserRole.DEVELOPER)

    project = Project(name="PIF Private Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(outsider.email, client)
    resp = await client.get(
        f"/projects/{project.id}/issues/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /projects/{project_id} — leader object in response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_response_includes_leader_object(client: AsyncClient, db_session: AsyncSession):
    admin = await create_user(db_session, "pl-admin@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "pl-leader@example.com", UserRole.PROJECT_LEADER)
    leader.full_name = "Alice Leader"
    await db_session.commit()

    project = Project(name="PL Leader Object Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    token = await login_user(admin.email, client)
    resp = await client.get(
        f"/projects/{project.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "leader" in data
    assert data["leader"] is not None
    assert data["leader"]["email"] == leader.email


# ---------------------------------------------------------------------------
# GET /projects/{project_id}/issue-assignee-candidates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_issue_assignee_candidates_includes_members_and_leaders(
    client: AsyncClient, db_session: AsyncSession
):
    admin = await create_user(db_session, "iac-admin@example.com", UserRole.ADMIN)
    leader = await create_user(db_session, "iac-leader@example.com", UserRole.PROJECT_LEADER)
    member = await create_user(db_session, "iac-member@example.com", UserRole.DEVELOPER)
    other_leader = await create_user(db_session, "iac-other-ldr@example.com", UserRole.PROJECT_LEADER)
    outsider = await create_user(db_session, "iac-outsider@example.com", UserRole.DEVELOPER)

    project = Project(name="IAC Project", leader_id=leader.id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    db_session.add(ProjectMember(project_id=project.id, user_id=member.id))
    await db_session.commit()

    token = await login_user(admin.email, client)
    resp = await client.get(
        f"/projects/{project.id}/issue-assignee-candidates",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    candidate_ids = {u["id"] for u in resp.json()}
    assert leader.id in candidate_ids       # project leader
    assert member.id in candidate_ids       # project member
    assert other_leader.id in candidate_ids  # project_leader of another project
    assert outsider.id not in candidate_ids  # plain developer, not in project
