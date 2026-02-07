"""
Seed database with initial test data.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.database import db_manager
from app.models.tenant import Tenant
from app.models.user import User


async def seed_data() -> None:
    """Create initial test data."""
    print("🌱 Seeding database...")
    
    # Initialize database
    db_manager.init()
    
    async for db in db_manager.get_session():
        # Check if data already exists
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
        await db.flush()  # Get tenant.id
        
        # Create test user
        user = User(
            email="admin@acme.com",
            hashed_password="$2b$12$test_hash_placeholder",  # We'll hash properly in Milestone 3
            full_name="Admin User",
            is_active=True,
            is_superuser=True,
            is_verified=True,
            tenant_id=tenant.id,
        )
        db.add(user)
        
        await db.commit()
        
        print(f"✅ Created tenant: {tenant.name} (ID: {tenant.id})")
        print(f"✅ Created user: {user.email} (ID: {user.id})")
    
    await db_manager.close()
    print("🎉 Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_data())