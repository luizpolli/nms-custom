"""Local users, roles, and permission catalog endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.permissions_catalog import (
    BUILT_IN_ROLES,
    PERMISSION_CATALOG,
    PERMISSION_DESCRIPTIONS,
    SYSTEM_SETTINGS_SUBMENUS,
)
from app.database import get_db
from app.models.system import AppRole, AppUser
from app.security.auth import (
    PERM_SETTINGS_SYSTEM,
    PERM_SETTINGS_USER_ADMIN_USERS_GROUPS,
    PERM_SETTINGS_USERS_GROUPS,
    Principal,
    require_settings_permission,
)
from app.security.passwords import hash_password
from app.services.account_audit import record_account_activity

from ._schemas import (
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
    _ensure_builtin_roles,
    _record_settings_audit,
)

router = APIRouter()


@router.get("/users", response_model=list[UserRead])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        object,
        Depends(
            require_settings_permission(
                PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS
            )
        ),
    ],
) -> list[UserRead]:
    result = await db.execute(select(AppUser).order_by(AppUser.username))
    return [UserRead.model_validate(user) for user in result.scalars().all()]


@router.get("/permissions")
async def list_permission_catalog(
    _principal: Annotated[
        object,
        Depends(
            require_settings_permission(
                PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS
            )
        ),
    ],
) -> dict[str, list[dict[str, str]]]:
    return PERMISSION_CATALOG


@router.get("/permissions/descriptions")
async def list_permission_descriptions(
    _principal: Annotated[
        object,
        Depends(
            require_settings_permission(
                PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS
            )
        ),
    ],
) -> dict[str, str]:
    return PERMISSION_DESCRIPTIONS


@router.get("/permissions/system-settings")
async def list_system_settings_permissions(
    _principal: Annotated[
        object,
        Depends(
            require_settings_permission(
                PERM_SETTINGS_SYSTEM,
                PERM_SETTINGS_USERS_GROUPS,
                PERM_SETTINGS_USER_ADMIN_USERS_GROUPS,
            )
        ),
    ],
) -> list[dict[str, str]]:
    """Table 2: Additional Permissions for System Settings Submenus (EPNM 4.0)."""
    return SYSTEM_SETTINGS_SUBMENUS


@router.get("/roles", response_model=list[RoleRead])
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        object,
        Depends(
            require_settings_permission(
                PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS
            )
        ),
    ],
) -> list[RoleRead]:
    await _ensure_builtin_roles(db)
    result = await db.execute(select(AppRole).order_by(AppRole.built_in.desc(), AppRole.name))
    return [RoleRead.from_role(role) for role in result.scalars().all()]


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    body: RoleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        object,
        Depends(
            require_settings_permission(
                PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS
            )
        ),
    ],
) -> RoleRead:
    existing = await db.execute(select(AppRole).where(AppRole.name == body.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Role already exists")
    role = AppRole(**body.model_dump(), built_in=False)
    db.add(role)
    await db.flush()
    await db.refresh(role)
    _record_settings_audit(
        db,
        "role.create",
        target=str(role.id),
        details={"name": role.name, "user_type": role.user_type, "permissions": role.permissions},
    )
    return RoleRead.from_role(role)


@router.patch("/roles/{id}", response_model=RoleRead)
async def update_role(
    id: uuid.UUID,
    body: RoleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        object,
        Depends(
            require_settings_permission(
                PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS
            )
        ),
    ],
) -> RoleRead:
    role = await db.get(AppRole, id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.built_in:
        meta = BUILT_IN_ROLES.get(role.name, {})
        if meta.get("editable", True) is False:
            raise HTTPException(
                status_code=400, detail="This built-in role is locked and cannot be modified"
            )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(role, field, value)
    await db.flush()
    await db.refresh(role)
    _record_settings_audit(
        db,
        "role.update",
        target=str(role.id),
        details={"name": role.name, "user_type": role.user_type, "permissions": role.permissions},
    )
    return RoleRead.from_role(role)


@router.delete("/roles/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        object,
        Depends(
            require_settings_permission(
                PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS
            )
        ),
    ],
) -> None:
    role = await db.get(AppRole, id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.built_in:
        raise HTTPException(status_code=400, detail="Built-in roles cannot be deleted")
    await db.delete(role)
    _record_settings_audit(db, "role.delete", target=str(id), details={"name": role.name})


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        Principal,
        Depends(
            require_settings_permission(
                PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS
            )
        ),
    ],
) -> UserRead:
    existing = await db.execute(select(AppUser).where(AppUser.username == body.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = AppUser(
        username=body.username,
        display_name=body.display_name,
        password_hash=hash_password(body.password.get_secret_value()),
        role=",".join(body.roles) if body.roles else body.role,
        user_type=body.user_type,
        custom_permissions=body.custom_permissions,
        virtual_domain=body.virtual_domain,
        enabled=body.enabled,
        force_password_change=body.force_password_change,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    _record_settings_audit(
        db,
        "user.create",
        target=str(user.id),
        details={"username": user.username, "role": user.role, "user_type": user.user_type},
    )
    await record_account_activity(
        db,
        principal=_principal,
        action="user.privileges.update",
        message=f"User privileges created for {user.username}",
        details={
            "target_username": user.username,
            "target_role": user.role,
            "target_user_type": user.user_type,
            "change_type": "create_user",
        },
    )
    return UserRead.model_validate(user)


@router.patch("/users/{id}", response_model=UserRead)
async def update_user(
    id: uuid.UUID,
    body: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        Principal,
        Depends(
            require_settings_permission(
                PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS
            )
        ),
    ],
) -> UserRead:
    user = await db.get(AppUser, id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    previous_role = user.role
    previous_user_type = user.user_type
    previous_permissions = user.custom_permissions or {}
    data = body.model_dump(exclude_unset=True, exclude={"password", "roles"})
    for field, value in data.items():
        setattr(user, field, value)
    if body.roles is not None:
        user.role = ",".join(body.roles)
    if body.password is not None:
        user.password_hash = hash_password(body.password.get_secret_value())
    await db.flush()
    await db.refresh(user)
    _record_settings_audit(
        db,
        "user.update",
        target=str(user.id),
        details={"username": user.username, "role": user.role, "user_type": user.user_type},
    )
    changed_privilege_fields = []
    if previous_role != user.role:
        changed_privilege_fields.append("roles")
    if previous_user_type != user.user_type:
        changed_privilege_fields.append("user_type")
    if body.custom_permissions is not None and previous_permissions != (
        user.custom_permissions or {}
    ):
        changed_privilege_fields.append("custom_permissions")
    if changed_privilege_fields:
        await record_account_activity(
            db,
            principal=_principal,
            action="user.privileges.update",
            message=f"User privileges changed for {user.username}",
            details={
                "target_username": user.username,
                "target_role": user.role,
                "previous_role": previous_role,
                "target_user_type": user.user_type,
                "previous_user_type": previous_user_type,
                "changed_fields": changed_privilege_fields,
            },
        )
    return UserRead.model_validate(user)


@router.delete("/users/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        object,
        Depends(
            require_settings_permission(
                PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS
            )
        ),
    ],
) -> None:
    user = await db.get(AppUser, id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    _record_settings_audit(db, "user.delete", target=str(id), details={"username": user.username})
