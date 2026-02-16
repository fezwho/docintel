# """
# Seed RBAC data (roles and permissions).
# """

# import asyncio
# import sys
# from pathlib import Path

# sys.path.insert(0, str(Path(__file__).parent.parent))

# from sqlalchemy import select
# from sqlalchemy.orm import selectinload

# from app.core.database import db_manager
# from app.models.role import Permission, Role
# from app.models.user import User


# # Permission definitions
# PERMISSIONS = [
#     ("documents:read", "View documents"),
#     ("documents:write", "Create and edit documents"),
#     ("documents:delete", "Delete documents"),
#     ("documents:share", "Share documents with others"),
#     ("analytics:view", "View analytics and reports"),
#     ("users:read", "View users"),
#     ("users:manage", "Manage users (create, edit, delete)"),
#     ("settings:manage", "Manage tenant settings"),
# ]

# # Role definitions (role_name, permissions, description)
# ROLES = [
#     (
#         "admin",
#         ["documents:read", "documents:write", "documents:delete", "documents:share",
#          "analytics:view", "users:read", "users:manage", "settings:manage"],
#         "Full access to all features within the tenant"
#     ),
#     (
#         "member",
#         ["documents:read", "documents:write", "documents:share", "analytics:view", "users:read"],
#         "Standard user with document management access"
#     ),
#     (
#         "viewer",
#         ["documents:read", "analytics:view"],
#         "Read-only access to documents and analytics"
#     ),
# ]


# async def seed_rbac() -> None:
#     """Create permissions and roles."""
#     print("🔐 Seeding RBAC data...")
    
#     db_manager.init()
    
#     async for db in db_manager.get_session():
#         # Create permissions
#         permission_map = {}
        
#         for perm_name, perm_desc in PERMISSIONS:
#             result = await db.execute(
#                 select(Permission).where(Permission.name == perm_name)
#             )
#             permission = result.scalar_one_or_none()
            
#             if not permission:
#                 permission = Permission(
#                     name=perm_name,
#                     description=perm_desc,
#                     tenant_id=None,  # System-wide permissions
#                 )
#                 db.add(permission)
#                 await db.flush()
#                 print(f"  ✅ Created permission: {perm_name}")
            
#             permission_map[perm_name] = permission
        
#         # Create roles
#         for role_name, role_perms, role_desc in ROLES:
#             result = await db.execute(
#                 select(Role).where(
#                     Role.name == role_name,
#                     Role.tenant_id.is_(None)
#                 )
#             )
#             role = result.scalar_one_or_none()
            
#             if not role:
#                 role = Role(
#                     name=role_name,
#                     description=role_desc,
#                     is_system_role=True,
#                     tenant_id=None,  # System-wide role
#                 )
#                 db.add(role)
#                 await db.flush()
#                 print(f"  ✅ Created role: {role_name}")
            
#             # Assign permissions to role
#             role.permissions = [permission_map[perm] for perm in role_perms]
        
#         await db.commit()
        
#         # Assign admin role to existing admin users
#         result = await db.execute(
#             select(User).where(User.is_superuser == True)
#         )
#         admin_users = result.scalars().all()
        
#         result = await db.execute(
#             select(Role).where(Role.name == "admin", Role.is_system_role == True)
#         )
#         admin_role = result.scalar_one()
        
#         for user in admin_users:
#             if admin_role not in user.roles:
#                 user.roles.append(admin_role)
#                 print(f"  ✅ Assigned admin role to: {user.email}")
        
#         await db.commit()
    
#     await db_manager.close()
#     print("🎉 RBAC seeding complete!")


# if __name__ == "__main__":
#     asyncio.run(seed_rbac())



"""
Seed RBAC data (roles and permissions).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, delete, insert
from sqlalchemy.orm import selectinload

from app.core.database import db_manager
from app.models.role import Permission, Role, role_permissions
from app.models.user import User


# Permission definitions
PERMISSIONS = [
    ("documents:read", "View documents"),
    ("documents:write", "Create and edit documents"),
    ("documents:delete", "Delete documents"),
    ("documents:share", "Share documents with others"),
    ("analytics:view", "View analytics and reports"),
    ("users:read", "View users"),
    ("users:manage", "Manage users (create, edit, delete)"),
    ("settings:manage", "Manage tenant settings"),
]

# Role definitions (role_name, permissions, description)
ROLES = [
    (
        "admin",
        ["documents:read", "documents:write", "documents:delete", "documents:share",
         "analytics:view", "users:read", "users:manage", "settings:manage"],
        "Full access to all features within the tenant"
    ),
    (
        "member",
        ["documents:read", "documents:write", "documents:share", "analytics:view", "users:read"],
        "Standard user with document management access"
    ),
    (
        "viewer",
        ["documents:read", "analytics:view"],
        "Read-only access to documents and analytics"
    ),
]


async def seed_rbac() -> None:
    """Create permissions and roles."""
    print("Seeding RBAC data...")
    
    db_manager.init()
    
    async for db in db_manager.get_session():
        # Create permissions
        permission_map = {}
        
        for perm_name, perm_desc in PERMISSIONS:
            result = await db.execute(
                select(Permission).where(Permission.name == perm_name)
            )
            permission = result.scalar_one_or_none()
            
            if not permission:
                permission = Permission(
                    name=perm_name,
                    description=perm_desc,
                    tenant_id=None,  # System-wide permissions
                )
                db.add(permission)
                await db.flush()
                print(f"  Created permission: {perm_name}")
            
            permission_map[perm_name] = permission
        
        # Create roles
        for role_name, role_perms, role_desc in ROLES:
            result = await db.execute(
                select(Role).where(
                    Role.name == role_name,
                    Role.tenant_id.is_(None),
                )
            )
            role = result.scalar_one_or_none()

            if not role:
                role = Role(
                    name=role_name,
                    description=role_desc,
                    is_system_role=True,
                    tenant_id=None,  # System-wide role
                )
                db.add(role)
                await db.flush()
                print(f"  Created role: {role_name}")

            # Update role-permission links via the association table to avoid async lazy loads
            await db.execute(
                delete(role_permissions).where(role_permissions.c.role_id == role.id)
            )

            for perm_name in role_perms:
                permission = permission_map[perm_name]
                await db.execute(
                    insert(role_permissions).values(
                        role_id=role.id,
                        permission_id=permission.id,
                    )
                )
        
        await db.commit()
        
        # Assign admin role to existing admin users
        # Added selectinload(User.roles) here
        result = await db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.is_superuser == True)
        )
        admin_users = result.scalars().all()
        
        result = await db.execute(
            select(Role).where(Role.name == "admin", Role.is_system_role == True)
        )
        admin_role = result.scalar_one()
        
        for user in admin_users:
            # This check is now safe because user.roles is already loaded
            if admin_role not in user.roles:
                user.roles.append(admin_role)
                print(f"  Assigned admin role to: {user.email}")
        
        await db.commit()
    
    await db_manager.close()
    print("RBAC seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_rbac())