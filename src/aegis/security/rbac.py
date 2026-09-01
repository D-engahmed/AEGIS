"""Role-based access control: role -> permission mapping and the checker.

Default-deny: permission is granted only when the actor's role holds it AND the
resource lives in the actor's tenant. Override of a safety gate is the most
restricted permission in the system (deployment-strategy.md).
"""

from __future__ import annotations

from aegis.domain import InsufficientPermission, Role

from .models import AuthContext, Permission
from .ports import PermissionChecker, TenantScopeGuard

_POLICY_PERMISSIONS = frozenset({Permission.POLICY_MODIFY, Permission.POLICY_OVERRIDE})
_READ_PERMISSIONS = frozenset(
    {
        Permission.EXPERIMENT_VIEW,
        Permission.RUN_VIEW,
        Permission.RESULT_VIEW,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset(Permission) - _POLICY_PERMISSIONS,
    Role.ENGINEER: frozenset(
        {
            Permission.EXPERIMENT_CREATE,
            Permission.EXPERIMENT_VIEW,
            Permission.EXPERIMENT_START,
            Permission.EXPERIMENT_CANCEL,
            Permission.RUN_VIEW,
            Permission.RUN_CANCEL,
            Permission.RESULT_VIEW,
            Permission.DATASET_MANAGE,
            Permission.TARGET_MANAGE,
        }
    ),
    Role.ANALYST: frozenset(
        {
            Permission.EXPERIMENT_VIEW,
            Permission.RUN_VIEW,
            Permission.RESULT_VIEW,
        }
    ),
    Role.VIEWER: _READ_PERMISSIONS,
}


class RBACPermissionChecker(PermissionChecker, TenantScopeGuard):
    """Permission and tenant checks against the role mapping."""

    def check(self, context: AuthContext, permission: Permission, resource_org_id: str) -> None:
        if not self.has_permission(context, permission, resource_org_id):
            raise InsufficientPermission(
                f"user {context.user_id!r} lacks {permission.value} for "
                f"organization {resource_org_id!r}"
            )

    def has_permission(
        self, context: AuthContext, permission: Permission, resource_org_id: str
    ) -> bool:
        if context.organization_id != resource_org_id:
            return False
        return permission in ROLE_PERMISSIONS[context.role]

    def require_same_tenant(self, context: AuthContext, resource_org_id: str) -> None:
        if context.organization_id != resource_org_id:
            raise InsufficientPermission(
                f"user {context.user_id!r} may not access data in organization {resource_org_id!r}"
            )


__all__ = ["RBACPermissionChecker", "ROLE_PERMISSIONS"]
