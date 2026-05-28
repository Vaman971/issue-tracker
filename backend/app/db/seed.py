import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole

async def seed_admin_user():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.email == settings.SEED_ADMIN_EMAIL)
        )

        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            print("Admin user already exists")
            return
        
        admin_user = User(
            email = settings.SEED_ADMIN_EMAIL,
            hashed_password=hash_password(settings.SEED_ADMIN_PASSWORD),
            role=UserRole.ADMIN
        )

        db.add(admin_user)

        await db.commit()
        await db.refresh(admin_user)

        print("Admin user created")

if __name__ == "__main__":
    asyncio.run(seed_admin_user())