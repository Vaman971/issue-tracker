from app.models.issue import Issue
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.refresh_token import RefreshToken
from app.models.user import User

# this file helps as, in alembic's .env file we will directly import all the models with * and it will know what tables to migrate 
