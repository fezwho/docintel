"""
Create test database.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def create_test_database():
    """Create test database if it doesn't exist."""
    import asyncpg
    
    # Connect to default postgres database
    conn = await asyncpg.connect(
        user="docintel",
        password="dev_password_change_in_prod",
        database="postgres",
        host="localhost",
    )
    
    try:
        # Check if test database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'docintel_test'"
        )
        
        if not exists:
            # Create test database
            await conn.execute("CREATE DATABASE docintel_test")
            print("✅ Test database created: docintel_test")
        else:
            print("ℹ️  Test database already exists: docintel_test")
    
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(create_test_database())