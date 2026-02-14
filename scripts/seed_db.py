"""
Seed database with initial test data.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.database import db_manager
from app.core.security import hash_password  # NEW
from app.models.tenant import Tenant
from app.models.user import User


async def seed_data() -> None:
    """Create initial test data."""
    print("🌱 Seeding database...")
    
    db_manager.init()
    
    async for db in db_manager.get_session():
        # Check if data exists
        result = await db.execute(select(Tenant))
        if result.first():
            print("⚠️  Database already contains data. Skipping seed.")
            return
        
        # Create test tenant
        tenant = Tenant(
            name="Acme Corporation",
            slug="acme-corp",
            max_users=50,
            max_documents=10000,
        )
        db.add(tenant)
        await db.flush()
        
        # Create admin user with proper password hashing
        admin_user = User(
            email="admin@acme.com",
            hashed_password=hash_password("Admin123!"),  # UPDATED
            full_name="Admin User",
            is_active=True,
            is_superuser=True,
            is_verified=True,
            tenant_id=tenant.id,
        )
        db.add(admin_user)
        
        # Create regular user
        regular_user = User(
            email="user@acme.com",
            hashed_password=hash_password("User123!"),  # UPDATED
            full_name="Regular User",
            is_active=True,
            is_superuser=False,
            is_verified=True,
            tenant_id=tenant.id,
        )
        db.add(regular_user)
        
        await db.commit()
        
        print(f"✅ Created tenant: {tenant.name}")
        print(f"✅ Created admin: {admin_user.email} (password: Admin123!)")
        print(f"✅ Created user: {regular_user.email} (password: User123!)")
    
    await db_manager.close()
    print("🎉 Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_data())