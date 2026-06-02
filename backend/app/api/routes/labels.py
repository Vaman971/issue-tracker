"""Labels — per-project label management and issue label assignment."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.activity import ActivityAction, IssueActivity
from app.models.issue import Issue
from app.models.label import IssueLabel, Label
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole
from app.schemas.label import LabelCreate, LabelRead

router = APIRouter(tags=["labels"])


async def _get_project_or_404(project_id: int, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    p = result.scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return p


async def _can_manage_labels(project: Project, user: User, db: AsyncSession) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    return project.leader_id == user.id


async def _can_view_project(project: Project, user: User, db: AsyncSession) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    if project.leader_id == user.id:
        return True
    member = (await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user.id,
        )
    )).scalar_one_or_none()
    return member is not None


# ---------------------------------------------------------------------------
# Project labels
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/labels/", response_model=list[LabelRead])
async def list_labels(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project_or_404(project_id, db)
    if not await _can_view_project(project, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(
        select(Label).where(Label.project_id == project_id).order_by(Label.name)
    )
    return result.scalars().all()


@router.post("/projects/{project_id}/labels/", response_model=LabelRead, status_code=status.HTTP_201_CREATED)
async def create_label(
    project_id: int,
    payload: LabelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project_or_404(project_id, db)
    if not await _can_manage_labels(project, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only project leaders and admins can manage labels")

    existing = (await db.execute(
        select(Label).where(Label.project_id == project_id, Label.name == payload.name)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Label with this name already exists")

    label = Label(project_id=project_id, name=payload.name, color=payload.color)
    db.add(label)
    await db.commit()
    await db.refresh(label)
    return label


@router.delete("/projects/{project_id}/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_label(
    project_id: int,
    label_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project_or_404(project_id, db)
    if not await _can_manage_labels(project, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only project leaders and admins can manage labels")

    result = await db.execute(
        select(Label).where(Label.id == label_id, Label.project_id == project_id)
    )
    label = result.scalar_one_or_none()
    if label is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")

    await db.delete(label)
    await db.commit()


# ---------------------------------------------------------------------------
# Issue label assignment
# ---------------------------------------------------------------------------

@router.post("/issues/{issue_id}/labels/{label_id}", response_model=LabelRead, status_code=status.HTTP_201_CREATED)
async def add_label_to_issue(
    issue_id: int,
    label_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue_result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = issue_result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    label_result = await db.execute(
        select(Label).where(Label.id == label_id, Label.project_id == issue.project_id)
    )
    label = label_result.scalar_one_or_none()
    if label is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found in this project")

    project = await _get_project_or_404(issue.project_id, db)
    if not await _can_manage_labels(project, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    existing = (await db.execute(
        select(IssueLabel).where(IssueLabel.issue_id == issue_id, IssueLabel.label_id == label_id)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Label already added to this issue")

    db.add(IssueLabel(issue_id=issue_id, label_id=label_id))
    db.add(IssueActivity(
        issue_id=issue_id,
        actor_id=current_user.id,
        action=ActivityAction.LABEL_ADDED,
        new_value=label.name,
    ))
    await db.commit()
    return label


@router.delete("/issues/{issue_id}/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_label_from_issue(
    issue_id: int,
    label_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue_result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = issue_result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    project = await _get_project_or_404(issue.project_id, db)
    if not await _can_manage_labels(project, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(
        select(IssueLabel).where(IssueLabel.issue_id == issue_id, IssueLabel.label_id == label_id)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not on this issue")

    label_result = await db.execute(select(Label).where(Label.id == label_id))
    label = label_result.scalar_one_or_none()

    db.add(IssueActivity(
        issue_id=issue_id,
        actor_id=current_user.id,
        action=ActivityAction.LABEL_REMOVED,
        old_value=label.name if label else str(label_id),
    ))

    await db.delete(assignment)
    await db.commit()
