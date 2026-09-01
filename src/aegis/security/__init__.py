"""Security layer (layer 11): authentication, authorization, tenant isolation.

Cross-cutting: every higher layer trusts these primitives for identity, access
control, PII redaction, classification, secrets, and the audit trail. The layer
depends only on domain (01) and policy (08); implementations can be hardened
(real OAuth2, Vault/KMS) behind the ports without touching consumers.
"""

from .audit import InMemorySecretsProvider, MemoryAuditLogger
from .auth import HmacTokenAuthProvider
from .models import (
    AuditEntry,
    AuthContext,
    AuthMethod,
    Credentials,
    DataClassification,
    Permission,
    PIIMatch,
    PIIType,
    RedactedString,
)
from .override import can_override_gate
from .pii import DefaultClassificationAnnotator, RegexPIIDetector
from .ports import (
    AuditLogger,
    AuthProvider,
    ClassificationAnnotator,
    PermissionChecker,
    PIIDetector,
    SecretsProvider,
    TenantScopeGuard,
)
from .rbac import ROLE_PERMISSIONS, RBACPermissionChecker

__all__ = [
    "AuditEntry",
    "AuditLogger",
    "AuthContext",
    "AuthMethod",
    "AuthProvider",
    "ClassificationAnnotator",
    "Credentials",
    "DataClassification",
    "DefaultClassificationAnnotator",
    "HmacTokenAuthProvider",
    "InMemorySecretsProvider",
    "MemoryAuditLogger",
    "PIIMatch",
    "PIIDetector",
    "PIIType",
    "Permission",
    "PermissionChecker",
    "RBACPermissionChecker",
    "ROLE_PERMISSIONS",
    "RedactedString",
    "RegexPIIDetector",
    "SecretsProvider",
    "TenantScopeGuard",
    "can_override_gate",
]
